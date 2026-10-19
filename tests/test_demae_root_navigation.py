import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from jwc24.demae_response import inspect_area_response, ResponseFormatError
from jwc24.japan_post import build_database
from test_japan_post import source
from tools.build_demae_area_fixture import build_root_fixture, native_xml


class RootNavigationTests(unittest.TestCase):
    def test_prefecture_selection_contains_native_municipality_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'postal.sqlite'
            rows = [(f'{n:02d}001', f'{n:02d}00001', f'Prefecture {n}',
                     f'City {n}', 'Town') for n in range(1, 48)]
            build_database(source(*rows), database)
            xml = build_root_fixture(database)
            self.assertEqual(inspect_area_response(xml, variant='root')['row_count'], 47)
            root = ET.fromstring(xml)
            gunma = root.find('areaList/TEST-JP-10')
            self.assertEqual(gunma.findtext('segment'), '\u7fa4\u99ac\u770c')
            self.assertEqual(gunma.findtext('list/row/areaName'), 'City 10')
            self.assertEqual(gunma.findtext('list/row/areaCode'), 'M10001')
            # Missing fields must fail our inspector rather than reach native95.
            city = gunma.find('list/row')
            city.remove(city.find('areaName'))
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(native_xml(root), variant='root')

    @unittest.skipUnless(importlib.util.find_spec('unicorn'), 'Optional Unicorn dependency')
    def test_actual_native_wrapper_preserves_preview_route_identifiers(self):
        path = Path(__file__).resolve().parents[1] / 'private/demae/fixtures/HCHJ-local-api.dol'
        if not path.exists():
            self.skipTest('Private native source unavailable')
        from tools.verify_demae_area_request import verify
        from urllib.parse import urlsplit, parse_qs
        for code in ('0', 'TEST-JP-10', 'M10202', 'M47382'):
            url = verify(path.read_bytes(), code)
            self.assertEqual(parse_qs(urlsplit(url).query)['areaCode'], [code])
        # Record the old failure using executed native bytes, not a Python slice.
        url = verify(path.read_bytes(), 'TEST-M-10202')
        self.assertEqual(parse_qs(urlsplit(url).query)['areaCode'], ['TEST-M-102'])
