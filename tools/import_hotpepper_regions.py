"""Explicit nationwide first-page import, with resumable per-prefecture caches."""
import json
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_regions import match_provider_areas
from jwc24.hotpepper import KEY_ENV, MAX_RESPONSE_BYTES, HotPepperError, fetch_catalog
from tools.asset_publication import atomic_write


def save(path, document):
    atomic_write(path, (json.dumps(document, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


def reusable_page(document, area, start):
    """A cache filename alone does not establish its region or pagination."""
    if not isinstance(document, dict):
        return False
    query = document.get('query')
    rows = document.get('restaurants')
    if (not isinstance(query, dict) or query.get('large_area') != area
            or type(query.get('start')) is not int or query['start'] != start
            or query.get('count') != 100 or not isinstance(rows, list) or len(rows) > 100):
        return False
    pagination = document.get('pagination', {})
    if not isinstance(pagination, dict):
        return False
    for field, maximum in (('results_available', 1000000), ('results_returned', 100),
                           ('results_start', 1000000)):
        value = pagination.get(field)
        if value is not None and (type(value) is not int or not 0 <= value <= maximum):
            return False
    if pagination.get('results_start') not in (None, start):
        return False
    returned = pagination.get('results_returned')
    if returned is not None and len(rows) > returned:
        return False
    return all(isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'] for row in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages', type=int, default=2, help='Maximum pages per prefecture, 1–100 (default: 2)')
    parser.add_argument('--prefecture', choices=[f'JP-{n:02d}' for n in range(1, 48)],
                        help='Refresh only this prefecture; preserve nationwide summary')
    parser.add_argument('--upgrade-schema', action='store_true',
                        help='Refetch valid caches older than adapter schema 2')
    args = parser.parse_args(argv)
    if not 1 <= args.pages <= 100:
        parser.error('pages must be between 1 and 100')
    root = Path(__file__).resolve().parents[1] / 'private/demae/hotpepper'
    root.mkdir(parents=True, exist_ok=True)
    try:
        key = os.environ.get(KEY_ENV) or (root / 'api-key.txt').read_text(encoding='utf-8').strip()
        url = 'https://webservice.recruit.co.jp/hotpepper/large_area/v1/?' + urlencode({'key': key, 'format': 'json'})
        with urlopen(Request(url, headers={'User-Agent': 'JWC24-catalog-import/1.0'}), timeout=30) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError('Oversized area master')
        master = json.loads(data)
        regions = match_provider_areas(master['results']['large_area'])
        if args.prefecture:
            regions = [region for region in regions if region['id'] == args.prefecture]
        save(root / 'areas.json', master)
        total = 0
        for region in regions:
            rows = {}
            complete = False
            for page in range(1, args.pages + 1):
                start = (page - 1) * 100 + 1
                path = root / (region['id'] + f'-page{page}.json')
                try:
                    cached = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
                except (ValueError, UnicodeError):
                    cached = None
                needs_upgrade = args.upgrade_schema and (not isinstance(cached, dict) or cached.get('schema_version') != 2)
                if not reusable_page(cached, region['provider_area_code'], start) or needs_upgrade:
                    cached = fetch_catalog(large_area=region['provider_area_code'], start=start, api_key=key)
                    if not reusable_page(cached, region['provider_area_code'], start):
                        raise ValueError('Provider page does not match the requested region and offset')
                    if args.upgrade_schema and cached.get('schema_version') != 2:
                        raise ValueError('Provider adapter did not return the requested schema')
                    cached['fetched_at'] = datetime.now(timezone.utc).isoformat()
                    cached['prefecture_id'] = region['id']
                    cached['coverage'] = 'provider page; not delivery eligibility'
                    save(path, cached)
                    time.sleep(1)
                for row in cached['restaurants']:
                    rows.setdefault(row['id'], row)
                meta = cached.get('pagination', {})
                available = meta.get('results_available')
                returned = meta.get('results_returned')
                if available is not None and returned is not None and start + returned > available:
                    complete = True
                    break
            size = len(rows)
            save(root / (region['id'] + '-catalog.json'), {'prefecture_id': region['id'],
                 'provider': 'hotpepper', 'attribution': cached.get('attribution'),
                 'restaurants': list(rows.values()), 'complete_at_fetch': complete,
                 'ordering_supported': False})
            total += size
            region['catalog_status'] = 'provider_pages_complete' if complete else 'partial_pages_cached'
            region['cached_pages'] = page
            region['cached_restaurants'] = size
            print(f'{region["id"]}: {size} restaurants', flush=True)
        summary_path = root / ('last-prefecture-import.json' if args.prefecture else 'regions.json')
        save(summary_path, {'schema_version': 1, 'regions': regions,
             'cached_restaurants': total, 'coverage': 'bounded provider pages per prefecture',
             'native_coverage_verified': False, 'ordering_supported': False})
        print(f'Cached {total} listings across {len(regions)} prefectures')
        return 0
    except Exception:
        # Transport exceptions can contain credential-bearing URLs.
        print('Nationwide import stopped; key and request details withheld. Completed caches retained.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
