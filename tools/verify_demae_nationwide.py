"""Verify every mapped catalog restaurant through local directory HTTP routes."""
import contextlib
import argparse
from http.client import HTTPConnection
import io
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_area_registry import AreaRegistry
from jwc24.demae_directory import DirectoryCategories
from tools.demae_fixture_server import create_server
from tools.verify_demae_xml_parser import verify_tree
from tools.verify_demae_shop_model import verify as verify_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', action='store_true', help='Verify the retained SQLite archive instead of source JSON')
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private/demae'
    catalogs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((private/'hotpepper').glob('JP-*-catalog.json'))]
    if args.database:
        from jwc24.demae_database import DemaeDatabase
        catalogs = DemaeDatabase(private/'demae.sqlite').catalogs()
    registry = AreaRegistry(json.loads((private/'postal/replacement-area-registry.json').read_text(encoding='utf-8')))
    directory = DirectoryCategories(catalogs, registry, private/'postal/postal.sqlite')
    source = (private/'fixtures/HCHJ-local-api.dol').read_bytes()
    biggest = {}
    for municipality, groups in directory.restaurants.items():
        for category, rows in groups.items():
            if len(rows) > biggest.get(municipality[:2], (0, None))[0]:
                biggest[municipality[:2]] = (len(rows), (municipality, category))
    selected = {key for _, key in biggest.values()}
    server = create_server(postal_database=private/'postal/postal.sqlite', town_registry=registry,
        directory_catalogs=None if args.database else catalogs, directory_all_shops=True,
        directory_database=private/'demae.sqlite' if args.database else None)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def get(action, **fields):
        connection = HTTPConnection(*server.server_address, timeout=10)
        try:
            connection.request('GET', '/nwapi.php?' + urlencode({'action': action, 'platform': 'wii', **fields}))
            response = connection.getresponse()
            body = response.read()
            if response.status != 200:
                raise ValueError('Nationwide directory route failed')
            return body, ET.fromstring(body)
        finally:
            connection.close()
    seen, categories, parser_checks, stack = set(), 0, 0, 0
    try:
        # Suppress thousands of fixed route log labels, never request values.
        with contextlib.redirect_stdout(io.StringIO()):
            for municipality, groups in directory.restaurants.items():
                _, towns = get('webApi_area_list', areaCode='M'+municipality)
                town = towns.findtext('areaList/container0/list/row/areaCode')
                if not town or registry.resolve(town)['municipality'] != municipality:
                    raise ValueError('Municipality town route differs')
                _, advertised = get('webApi_category_list', areaCode=town, reservationType='0')
                if {x.text for x in advertised.iter('CategoryCode')} != set(groups):
                    raise ValueError('Advertised category coverage differs')
                for category, rows in groups.items():
                    body, shops = get('webApi_shop_list', areaCode=town, categoryCode=category,
                                      isReservation='0', selectType='1')
                    actual = [x.text for x in shops.iter('shopCode')]
                    if actual != [row['id'] for row in rows] or seen.intersection(actual):
                        raise ValueError('Missing, duplicated or reordered restaurant')
                    seen.update(actual)
                    categories += 1
                    if (municipality, category) in selected:
                        state = verify_tree(source, body)
                        stack = max(stack, state['max_stack_bytes'])
                        parser_checks += 1
        model = verify_model(source, max(n for n, _ in biggest.values()))
        report = {'prefectures': len(biggest), 'municipalities': len(directory.restaurants),
            'persistent_database': args.database,
            'category_routes': categories, 'restaurant_rows_verified': len(seen),
            'native_largest_group_per_prefecture_verified': parser_checks,
            'native_xml_max_stack_bytes': stack, **model,
            'source_images_downloaded': False, 'ordering_supported': False}
        (private/'nationwide-route-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


if __name__ == '__main__':
    main()
