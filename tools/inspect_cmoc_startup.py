"""Read-only CMOC FD record inspection; no HTTP/authentication success claim."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from jwc24.cmoc import CMOCFormatError, DEFAULT_MAX_BYTES
from jwc24.cmoc_startup import MAX_NATIVE_CAST_SIZE, decode_first_data_record, inspect_first_data_response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--record', action='store_true', help='inspect a single FD record, without its 32-byte response header')
    args = parser.parse_args(argv)
    limit = MAX_NATIVE_CAST_SIZE if args.record else DEFAULT_MAX_BYTES
    try:
        with args.input.open('rb') as source:
            payload = source.read(limit + 1)
        result = decode_first_data_record(payload) if args.record else inspect_first_data_response(payload)
    except (OSError, CMOCFormatError):
        print('FD input is unavailable or outside the supported first-data subset', file=sys.stderr)
        return 1
    print(json.dumps(result.metadata(), sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
