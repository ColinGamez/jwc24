"""Check real preview data through local HTTP and native area URL construction.

This does not launch Dolphin or verify native rendering, saves or ordering.
"""
import json
import hashlib
from pathlib import Path
import sys
import threading
from http.client import HTTPConnection
from urllib.parse import urlsplit, urlencode
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_area_registry import AreaRegistry
from tools.demae_fixture_server import create_server
from tools.verify_demae_area_request import verify
from tools.cache_demae_directory_images import load_images
from tools.verify_demae_xml_parser import verify_tree


def main():
    private = Path(__file__).resolve().parents[1] / 'private/demae'
    client = private / 'phone-native/HCHJ-directory-modal-candidate-v7.dol'
    source = client.read_bytes()
    parser_source = (private / 'fixtures/HCHJ-local-api.dol').read_bytes()
    parser_checks = []
    metadata = json.loads(client.with_suffix('.metadata.json').read_bytes())
    source_sha = hashlib.sha256(source).hexdigest()
    if source_sha != metadata['output_sha256'] or metadata.get('local_directory_images') is not True:
        raise ValueError('Preview client fingerprint or image capabilities mismatch')
    registry = AreaRegistry(json.loads((private / 'postal/replacement-area-registry.json').read_text(encoding='utf-8')))
    catalogs = [json.loads(path.read_text(encoding='utf-8'))
                for path in sorted((private / 'hotpepper').glob('JP-*-catalog.json'))]
    manifest = json.loads((private / 'fixtures/directory-shop-selection-v1.json').read_text(encoding='utf-8'))
    image_directory = private / 'directory-images-v1'
    image_directory = image_directory if image_directory.exists() else None
    images = load_images(image_directory, {identifier for group in manifest for identifier in group['restaurant_ids']}) if image_directory else {}
    server = create_server(postal_database=private / 'postal/postal.sqlite', town_registry=registry,
                           directory_catalogs=catalogs, directory_shop_previews=manifest,
                           directory_images=image_directory)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    def get(path):
        connection = HTTPConnection(*server.server_address, timeout=5)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            body = response.read()
            if response.status != 200:
                raise ValueError(f'Preview route failed with HTTP {response.status}')
            parsed = verify_tree(parser_source, body)
            parser_checks.append(parsed['max_stack_bytes'])
            return ET.fromstring(body)
        finally:
            connection.close()
    def native_area(code):
        url = urlsplit(verify(source, code, expected_sha256=source_sha))
        return get(url.path + '?' + url.query)
    try:
        root = native_area('0')
        checked = 0
        shops = 0
        image_count = 0
        for selection in manifest:
            municipality = selection['municipality']
            expected_code = 'M' + municipality
            rows = root.findall('areaList/TEST-JP-' + municipality[:2] + '/list/row')
            if not any(row.findtext('areaCode') == expected_code for row in rows):
                raise ValueError('Staged municipality absent from root selection response')
            town = native_area(expected_code).findtext('areaList/container0/list/row/areaCode')
            if not town or registry.resolve(town)['municipality'] != municipality:
                raise ValueError('Town route lost its source municipality')
            category = selection['category_code']
            categories = get('/nwapi.php?' + urlencode(dict(action='webApi_category_list',
                             platform='wii', areaCode=town, reservationType='0')))
            if category not in [node.text for node in categories.iter('CategoryCode')]:
                raise ValueError('Staged shop category is not advertised')
            listing = get('/nwapi.php?' + urlencode(dict(action='webApi_shop_list', platform='wii',
                          areaCode=town, categoryCode=category, isReservation='0', selectType='1')))
            identifiers = [node.text for node in listing.iter('shopCode')]
            if identifiers != selection['restaurant_ids']:
                raise ValueError('Shop route differs from explicit source selection')
            checked += 1
            shops += len(identifiers)
            for identifier in identifiers:
                if identifier not in images:
                    continue
                connection = HTTPConnection(*server.server_address, timeout=5)
                try:
                    image_url = urlsplit(verify(source, identifier, logo=True, expected_sha256=source_sha))
                    if image_url.scheme != 'http' or image_url.netloc != '127.0.0.1:18085':
                        raise ValueError('Native image URL is not local HTTP')
                    connection.request('GET', image_url.path)
                    response = connection.getresponse()
                    if (response.status != 200 or response.getheader('Content-Type') != 'image/jpeg'
                            or response.read() != images[identifier]):
                        raise ValueError('Local source JPEG route differs from validated cache')
                    image_count += 1
                finally:
                    connection.close()
        print(json.dumps({'verified_preview_routes': checked, 'restaurant_rows': shops,
                          'source_images_served_byte_identically': image_count,
                          'native_area_url_bytes_executed': True, 'native_render_verified': False,
                          'native_logo_url_bytes_executed': True,
                          'native_xml_responses_verified': len(parser_checks),
                          'native_xml_max_stack_bytes': max(parser_checks),
                          'orders_submitted': 0}))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


if __name__ == '__main__':
    main()
