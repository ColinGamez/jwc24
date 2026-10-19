"""Build a private read-only shop-list preview for a reviewed directory client.

Not compatible with the stock payment filter; does not enable ordering.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_demae_area_fixture import native_xml
from tools.asset_publication import publish_assets
from jwc24.demae_categories import native_categories, exact_genre_mapping
from jwc24.hotpepper import ATTRIBUTION


def build_directory_shops(restaurants, category_code, *, max_restaurants=25):
    if type(max_restaurants) is not int or not 1 <= max_restaurants <= 1000:
        raise ValueError('Invalid directory response row bound')
    if category_code not in {row['code'] for row in native_categories()}:
        raise ValueError('Unknown native directory category')
    restaurants = list(restaurants)
    if not 1 <= len(restaurants) <= 1000:
        raise ValueError('Invalid directory source count')
    seen = set()
    for row in restaurants:
        identifier = row.get('id') if isinstance(row, dict) else None
        if not isinstance(identifier, str) or not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier) or identifier in seen:
            raise ValueError('Invalid or duplicate directory identity')
        seen.add(identifier)
        if exact_genre_mapping(row.get('genre')) != category_code:
            raise ValueError('Source genre does not establish this directory category')
        for field in ('name', 'address', 'catchphrase'):
            value = row.get(field)
            if field == 'catchphrase' and value is None:
                continue
            if (not isinstance(value, str) or (field != 'catchphrase' and not value.strip())
                    or len(value.encode('utf-16-be')) > 1024):
                raise ValueError('Missing or oversized source display field')
            value.encode('cp932', errors='strict')
    if len(restaurants) > max_restaurants:
        raise ValueError('Directory response exceeds configured row bound; no silent truncation')
    root = ET.Element('response')
    group = ET.SubElement(root, 'container0')
    ET.SubElement(group, 'LargeCategoryName').text = '\u98df\u4e8b'
    category = ET.SubElement(ET.SubElement(group, 'CategoryList'), 'row')
    ET.SubElement(category, 'CategoryCode').text = category_code
    shops = ET.SubElement(category, 'ShopList')
    for row in restaurants:
        shop = ET.SubElement(shops, 'row')
        fields = {'shopCode': row['id'], 'homeCode': row['id'], 'name': row['name'],
                  'catchphrase': '\u5e97\u8217\u60c5\u5831\uff08\u6ce8\u6587\u672a\u5bfe\u5fdc\uff09\n' + row['name']
                                 + '\n' + row['address']
                                 + ('\n' + row['catchphrase'] if row.get('catchphrase') else '')
                                 + '\n' + ATTRIBUTION['text'] + ' ' + ATTRIBUTION['url'],
                  # These are this replacement service's restrictions, not
                  # provider hours, reservations or payment capabilities.
                  'yoyaku': '0', 'activate': 'stop'}
        if len(fields['catchphrase'].encode('utf-16-be')) // 2 > 256:
            raise ValueError('Directory information exceeds conservative modal preview capacity')
        for name, value in fields.items():
            ET.SubElement(shop, name).text = value
        ET.SubElement(shop, 'paymentList')  # No invented cash-on-delivery support.
        ET.SubElement(ET.SubElement(shop, 'shopStatus'), 'status')
        # No minimum price, wait time, or provider open-status claims.
    ET.SubElement(ET.SubElement(root, 'apiStatus'), 'code').text = '0'
    data = native_xml(root)
    if len(data) > 256 * 1024:
        raise ValueError('Directory preview exceeds conservative response limit')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--restaurant-id', action='append', required=True)
    parser.add_argument('--category-code', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output.resolve().is_relative_to(private.resolve()):
        parser.error('Preview must remain private')
    snapshot = args.catalog.read_bytes()
    catalog = json.loads(snapshot)
    if catalog.get('provider') != 'hotpepper':
        parser.error('Expected a Hot Pepper directory catalog')
    rows = {row['id']: row for row in catalog['restaurants']}
    if any(identifier not in rows for identifier in args.restaurant_id):
        parser.error('Requested restaurant is absent from the source catalog')
    data = build_directory_shops([rows[identifier] for identifier in args.restaurant_id], args.category_code)
    metadata = {'source_sha256': hashlib.sha256(snapshot).hexdigest(),
                'rows': len(args.restaurant_id), 'restaurant_ids': args.restaurant_id,
                'category_code': args.category_code, 'requires_directory_client': True,
                'ordering_supported': False, 'native_render_verified': False}
    publish_assets([(args.output, data),
                    (args.output.with_suffix('.metadata.json'), json.dumps(metadata, indent=2).encode())],
                   source_check=(args.catalog, snapshot))
    print('Built private directory shop-list preview; not served, installed or launched')


if __name__ == '__main__':
    main()
