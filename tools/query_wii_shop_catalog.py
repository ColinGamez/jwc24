"""Query imported Shop metadata offline; no HTTP, account or install operations."""
import argparse
import json
from pathlib import Path

from jwc24.wii_shop_browse import Catalog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalog', type=Path)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--search', default='')
    parser.add_argument('--category', choices=('WiiWare', 'Virtual Console'))
    parser.add_argument('--demos', choices=('all', 'exclude', 'only'), default='all')
    parser.add_argument('--title-id', action='append', default=[])
    args = parser.parse_args(argv)
    if args.catalog.stat().st_size > 32*1024*1024:
        parser.error('Catalog exceeds input bound')
    catalog = Catalog(json.loads(args.catalog.read_text(encoding='utf-8'))['records'])
    result = catalog.query(offset=args.offset, limit=args.limit, search=args.search,
                           category=args.category, demos=args.demos, title_ids=args.title_id)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
