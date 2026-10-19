#!/usr/bin/env python3
"""Explicitly fetch one Hot Pepper page and atomically cache a private catalog."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.hotpepper import HotPepperError, fetch_catalog
from tools.asset_publication import atomic_write


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keyword', default='')
    parser.add_argument('--large-area', help='Provider prefecture code from the area master, e.g. Z011')
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--output', type=Path, default=Path('private/demae/hotpepper/catalog.json'))
    args = parser.parse_args(argv)
    output = args.output.resolve()
    private_root = (Path(__file__).resolve().parents[1] / 'private').resolve()
    if private_root not in output.parents:
        parser.error('catalog output must be inside the project private directory')
    try:
        catalog = fetch_catalog(args.keyword, large_area=args.large_area, start=args.start, count=args.count)
        catalog['fetched_at'] = datetime.now(timezone.utc).isoformat()
        payload = (json.dumps(catalog, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(output, payload)
    except (HotPepperError, OSError):
        print('Catalog import failed; check API configuration, response and output access', file=sys.stderr)
        return 1
    print(f'Cached {len(catalog["restaurants"])} restaurants; ordering is unsupported')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
