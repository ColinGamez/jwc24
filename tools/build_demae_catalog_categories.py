"""Audit cached listings and write offline category fixtures without refetching."""
import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_catalog_categories import classify_restaurants
from tools.build_demae_category_fixture import build_categories
from tools.asset_publication import publish_assets


def build_catalog_categories(root):
    root = Path(root)
    reports = {}
    fixtures = {}
    total = mapped = 0
    source_checks = []
    for path in sorted((root / 'hotpepper').glob('JP-*-catalog.json')):
        captured = path.read_bytes()
        source_checks.append((path, captured))
        document = json.loads(captured)
        report = classify_restaurants(document['restaurants'])
        identity = document['prefecture_id']
        if not isinstance(identity, str) or path.name != identity + '-catalog.json' or identity in reports:
            raise ValueError('Catalog prefecture identity mismatch')
        codes = [code for code, value in report['categories'].items() if value['restaurant_ids']]
        total += report['restaurants']
        mapped += report['restaurants'] - len(report['unmapped_restaurant_ids'])
        reports[identity] = report
        if codes:
            fixtures[identity] = build_categories(codes)
    if set(reports) != {f'JP-{number:02d}' for number in range(1, 48)}:
        raise ValueError('All prefecture catalogs are required')
    summary = {'prefectures': len(reports), 'listings_checked': total, 'exact_label_matches': mapped,
               'unmapped_listings': total - mapped, 'native_verified': False, 'ordering_supported': False}
    manifest = {'schema_version': 1, 'native_verified': False,
                'active_fixtures': {identity: {'filename': identity + '.xml',
                   'sha256': hashlib.sha256(data).hexdigest()} for identity, data in fixtures.items()}}
    output = root / 'fixtures/catalog-categories'
    assets = [(output / (identity + '.xml'), data) for identity, data in fixtures.items()]
    assets.append((output / 'manifest.json', json.dumps(manifest, indent=2).encode()))
    assets.append((root / 'hotpepper/category-audit.json',
                   json.dumps({'summary': summary, 'regions': reports}, ensure_ascii=False).encode('utf-8')))
    publish_assets(assets, source_checks=source_checks)
    return summary


def main():
    summary = build_catalog_categories(Path(__file__).resolve().parents[1] / 'private/demae')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
