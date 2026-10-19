"""Audit every catalog restaurant without claiming complete provider coverage.

Writes a private coverage report; never launches Dolphin or submits orders.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_categories import exact_genre_mapping
from jwc24.demae_directory import DirectoryCategories
from jwc24.demae_area_registry import AreaRegistry
from tools.build_demae_directory_shops import build_directory_shops
from tools.demae_directory_image_store import image_index
from tools.verify_demae_xml_parser import verify_tree


def audit(catalogs, directory, staged, *, parser_source=None):
    images = image_index(catalogs)
    located = {row['id']: (municipality, code)
               for municipality, groups in directory.restaurants.items()
               for code, rows in groups.items() for row in rows}
    enabled = {identifier for group in staged for identifier in group['restaurant_ids']}
    report = {'prefectures': [], 'restaurants': [], 'large_groups': [],
              'native_batches_checked': 0, 'native_max_stack_bytes': 0,
              'source_image_downloads_verified': False,
              'nationwide_browsing_ready': False,
              'native_render_verified': False, 'ordering_supported': False,
              'scope': 'Available catalog snapshots; not all Hot Pepper restaurants'}
    for catalog in catalogs:
        counts = Counter()
        for row in catalog['restaurants']:
            identifier = row['id']
            code = exact_genre_mapping(row.get('genre'))
            issues = []
            if code is None:
                issues.append('unmapped_genre')
            elif identifier not in located:
                issues.append('unresolved_municipality')
            if not images[identifier]['source_url']:
                issues.append('missing_source_image')
            if code is not None:
                try:
                    build_directory_shops([row], code)
                except (ValueError, UnicodeError) as error:
                    issues.append('shop_xml: ' + str(error))
            if identifier not in enabled:
                issues.append('not_staged')
            counts.update(issues)
            counts['restaurants'] += 1
            report['restaurants'].append({'id': identifier,
                'prefecture': catalog['prefecture_id'], 'issues': issues})
        report['prefectures'].append({'id': catalog['prefecture_id'], **dict(counts)})
    for municipality, groups in directory.restaurants.items():
        for code, rows in groups.items():
            if len(rows) > 25:
                report['large_groups'].append({'municipality': municipality,
                    'category': code, 'restaurants': len(rows), 'needs_pagination': True})
            if parser_source is not None:
                # Audit every serializable row in bounded batches. These chunks
                # are test inputs, not an implementation of native pagination.
                valid = []
                for row in rows:
                    try:
                        build_directory_shops([row], code)
                    except (ValueError, UnicodeError):
                        continue
                    valid.append(row)
                for start in range(0, len(valid), 25):
                    state = verify_tree(parser_source, build_directory_shops(valid[start:start+25], code))
                    report['native_batches_checked'] += 1
                    report['native_max_stack_bytes'] = max(report['native_max_stack_bytes'], state['max_stack_bytes'])
    report['summary'] = dict(sum((Counter({k: v for k, v in p.items() if k != 'id'})
                                 for p in report['prefectures']), Counter()))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-parser', action='store_true')
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private/demae'
    catalogs = [json.loads(path.read_text(encoding='utf-8'))
                for path in sorted((private / 'hotpepper').glob('JP-*-catalog.json'))]
    if {c['prefecture_id'] for c in catalogs} != {f'JP-{n:02d}' for n in range(1, 48)}:
        raise ValueError('Audit requires all 47 prefecture snapshots')
    registry = AreaRegistry(json.loads((private / 'postal/replacement-area-registry.json').read_text(encoding='utf-8')))
    directory = DirectoryCategories(catalogs, registry, private / 'postal/postal.sqlite')
    staged = json.loads((private / 'fixtures/directory-shop-selection-v1.json').read_text(encoding='utf-8'))
    source = (private / 'fixtures/HCHJ-local-api.dol').read_bytes() if args.native_parser else None
    report = audit(catalogs, directory, staged, parser_source=source)
    output = private / 'directory-coverage-audit.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'prefectures': len(catalogs), **report['summary'],
        'groups_needing_pagination': len(report['large_groups']),
        'native_batches_checked': report['native_batches_checked'],
        'native_max_stack_bytes': report['native_max_stack_bytes']}))


if __name__ == '__main__':
    main()
