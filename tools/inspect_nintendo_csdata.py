"""Read-only HATJ CSData framing inspection; prints metadata, never catalog bytes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from jwc24.nintendo_csdata import MAX_COMPRESSED_BYTES, CSDataFormatError, inspect_csdata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open('rb') as source:
            payload = source.read(MAX_COMPRESSED_BYTES + 1)
        result = inspect_csdata(payload)
    except (OSError, CSDataFormatError):
        print('CSData input is unavailable or outside the supported framing subset', file=sys.stderr)
        return 1
    print(json.dumps(result.metadata(), sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
