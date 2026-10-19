from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest
import json
import xml.etree.ElementTree as ET

from test_japan_post import source
from jwc24.japan_post import build_database
from jwc24.demae_area_registry import AreaRegistry, area_identity, assign_area_codes
from jwc24.demae_directory import DirectoryCategories
from jwc24.demae_response import inspect_area_response
from tools.demae_fixture_server import create_server


class DirectoryCategoryTests(unittest.TestCase):
    def test_verified_old_ward_alias_is_used_only_for_routing(self):
        from jwc24.demae_directory import _address
        original = '静岡県浜松市中区田町325-38'
        self.assertEqual(_address(original), '静岡県浜松市中央区田町325-38')
        self.assertEqual(original, '静岡県浜松市中区田町325-38')
        self.assertEqual(_address('静岡県浜松市北区田町'), '静岡県浜松市北区田町')

    def test_all_directory_mode_serves_every_row_without_preview_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, registry, code, catalogs = self.fixture(Path(temporary))
            original = catalogs[0]['restaurants'][0]
            catalogs[0]['restaurants'] = [dict(original, id=f'hotpepper:J{n:09d}') for n in range(30)]
            server = create_server(postal_database=database, town_registry=registry,
                                   directory_catalogs=catalogs, directory_all_shops=True)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/nwapi.php?action=webApi_shop_list&platform=wii&areaCode='
                    + code + '&categoryCode=04&isReservation=0&selectType=1')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                rows = ET.fromstring(response.read()).findall('.//ShopList/row/shopCode')
                self.assertEqual([r.text for r in rows], [r['id'] for r in catalogs[0]['restaurants']])
                connection.close()
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/health')
                response = connection.getresponse()
                health = json.loads(response.read())
                self.assertTrue(health['directory_all_shops'])
                self.assertEqual(health['directory_restaurants'], 30)
                self.assertFalse(health['ordering_supported'])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_all_directory_mode_rejects_ambiguous_or_missing_inputs(self):
        with self.assertRaises(ValueError):
            create_server(directory_all_shops=True)
        with tempfile.TemporaryDirectory() as temporary:
            database, registry, code, catalogs = self.fixture(Path(temporary))
            with self.assertRaises(ValueError):
                create_server(postal_database=database, town_registry=registry,
                    directory_catalogs=catalogs, directory_all_shops=True,
                    directory_shop_previews=[])

    def fixture(self, root):
        database = root / 'postal.sqlite'
        rows = [(f'{n:02d}001', f'{n:02d}00001', f'Prefecture{n}', f'City{n}', 'Town') for n in range(1, 48)]
        build_database(source(*rows), database)
        registry = AreaRegistry(assign_area_codes({}, [area_identity(row[0], row[1], row[4]) for row in rows]))
        code = registry.code_for('10001', '1000001', 'Town')
        catalogs = [{'provider': 'hotpepper', 'prefecture_id': 'JP-10', 'restaurants': [
            {'id': 'hotpepper:J000000001', 'address': 'Prefecture10 City10 1-2', 'genre': '\u548c\u98df'},
            {'id': 'hotpepper:J000000002', 'address': 'Prefecture10 OtherCity 1-2', 'genre': '\u4e2d\u83ef'},
            {'id': 'hotpepper:J000000003', 'address': 'Prefecture10 City10 1-3', 'genre': 'unknown'}]}]
        for row in catalogs[0]['restaurants']:
            row.update(name='Source restaurant', catchphrase='Source description')
        return database, registry, code, catalogs

    def test_explicit_shop_http_preview_and_order_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            database, registry, code, catalogs = self.fixture(Path(directory))
            # A real category in the source snapshot can still lack a staged
            # shop response; the preview UI must not offer that dead end.
            catalogs[0]['restaurants'][1]['address'] = 'Prefecture10 City10 1-4'
            manifest = [{'municipality': '10001', 'category_code': '04',
                         'restaurant_ids': ['hotpepper:J000000001']}]
            server = create_server(postal_database=database, town_registry=registry,
                                   directory_catalogs=catalogs, directory_shop_previews=manifest)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/nwapi.php?action=webApi_category_list&platform=wii&areaCode='
                                   + code + '&reservationType=0')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                category_xml = ET.fromstring(response.read())
                self.assertEqual([row.text for row in category_xml.iter('CategoryCode')], ['04'])
                connection.close()
                base = ('/nwapi.php?action=webApi_shop_list&platform=wii&areaCode='+code
                        +'&categoryCode=04&isReservation=0&selectType=1')
                paths = [(base, 200), (base.replace('isReservation=0', 'isReservation=1'), 400),
                         (base.replace('selectType=1', 'selectType=0'), 400),
                         (base.replace('categoryCode=04', 'categoryCode=05'), 400),
                         (base+'&categoryCode=04', 400), (base+'&extra=1', 400)]
                for path, expected in paths:
                    connection = HTTPConnection(*server.server_address, timeout=3)
                    connection.request('GET', path)
                    response = connection.getresponse()
                    data = response.read()
                    connection.close()
                    self.assertEqual(response.status, expected)
                    if expected == 200:
                        root = ET.fromstring(data)
                        self.assertEqual(root.findtext('.//ShopList/row/name'), 'Source restaurant')
                        self.assertEqual(len(root.find('.//paymentList')), 0)
                        self.assertIsNone(root.find('.//minPrice'))
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/health')
                health = json.loads(connection.getresponse().read())
                connection.close()
                self.assertTrue(health['directory_shop_preview'])
                self.assertFalse(health['restaurant_navigation'])
                self.assertFalse(health['ordering_supported'])
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('POST', '/nwapi.php', b'action=webApi_order_done')
                response = connection.getresponse()
                response.read()
                connection.close()
                self.assertEqual(response.status, 405)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_shop_manifest_cannot_select_other_area_or_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            database, registry, _, catalogs = self.fixture(Path(directory))
            valid = {'municipality': '10001', 'category_code': '04',
                     'restaurant_ids': ['hotpepper:J000000001']}
            for manifest in [[dict(valid, municipality='11001')],
                             [dict(valid, restaurant_ids=['hotpepper:J000000002'])],
                             [dict(valid, restaurant_ids=['hotpepper:J000000001']*2)],
                             [valid, valid], [dict(valid, extra='bad')]]:
                with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                    create_server(postal_database=database, town_registry=registry,
                                  directory_catalogs=catalogs, directory_shop_previews=manifest)

    def test_only_known_municipality_and_known_genres_are_used(self):
        with tempfile.TemporaryDirectory() as directory:
            database, registry, code, catalogs = self.fixture(Path(directory))
            snapshot = DirectoryCategories(catalogs, registry, database)
            database.unlink()
            self.assertEqual(snapshot.codes_for(code), ('04',))
            selected = snapshot.restaurants_for(code, '04')
            self.assertEqual([row['id'] for row in selected], ['hotpepper:J000000001'])
            selected[0]['genre'] = 'changed by caller'
            self.assertEqual(snapshot.restaurants_for(code, '04')[0]['genre'], '\u548c\u98df')
            self.assertEqual(snapshot.restaurants_for(code, '05'), ())
            self.assertEqual(snapshot.codes_for('99999999999'), ())
            other = registry.code_for('11001', '1100001', 'Town')
            self.assertEqual(snapshot.codes_for(other), ())

    def test_catalog_identity_and_duplicate_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            database, registry, _, catalogs = self.fixture(Path(directory))
            with self.assertRaises(ValueError):
                DirectoryCategories(catalogs*2, registry, database)
            catalogs[0]['restaurants'].append(catalogs[0]['restaurants'][0])
            with self.assertRaises(ValueError):
                DirectoryCategories(catalogs, registry, database)

    def test_directory_route_requires_explicit_dependencies(self):
        with self.assertRaises(ValueError):
            create_server(directory_catalogs=[])

    def test_http_category_contract_and_rejection_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            database, registry, code, catalogs = self.fixture(Path(directory))
            server = create_server(postal_database=database, town_registry=registry, directory_catalogs=catalogs)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = '/nwapi.php?action=webApi_category_list&platform=wii&areaCode='
                for suffix, expected in [(code+'&reservationType=0', 200),
                                         (code+'&reservationType=1', 400),
                                         ('99999999999&reservationType=0', 400),
                                         (code+'&reservationType=0&areaCode='+code, 400)]:
                    connection = HTTPConnection(*server.server_address, timeout=3)
                    connection.request('GET', base+suffix)
                    response = connection.getresponse()
                    data = response.read()
                    connection.close()
                    self.assertEqual(response.status, expected)
                    if expected == 200:
                        report = inspect_area_response(data, variant='categories')
                        self.assertEqual(report['category_count'], 1)
                        self.assertIn(b'<![CDATA[04]]>', data)
                        self.assertNotIn(b'paymentList', data)
                empty_code = registry.code_for('01001', '0100001', 'Town')
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', base + empty_code + '&reservationType=0')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(inspect_area_response(response.read(), variant='categories')['category_count'], 0)
                connection.close()
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/nwapi.php?action=webApi_shop_list&platform=wii')
                response = connection.getresponse()
                response.read()
                connection.close()
                self.assertEqual(response.status, 400)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
