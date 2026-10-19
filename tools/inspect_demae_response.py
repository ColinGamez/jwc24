"""Inspect local HCHJ area XML without printing its address or record content."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.demae_response import MAX_XML_BYTES, ResponseFormatError, inspect_area_response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xml', type=Path)
    parser.add_argument('--variant', choices=('address', 'list', 'postal-fallback', 'auth', 'documents'), default='address')
    parser.add_argument('--http-status', type=int, default=200)
    args = parser.parse_args(argv)
    try:
        with args.xml.open('rb') as source:
            data = source.read(MAX_XML_BYTES + 1)
        report = inspect_area_response(data, variant=args.variant, http_status=args.http_status)
    except (OSError, ResponseFormatError):
        print('Area response failed offline inspection; content withheld', file=sys.stderr)
        return 1
    print(json.dumps(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
