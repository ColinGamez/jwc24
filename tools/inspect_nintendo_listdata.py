"""Read-only partial Nintendo Channel ListData inspection; never prints titles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.nintendo_listdata import MAX_INPUT_BYTES, ListDataFormatError, inspect_listdata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open('rb') as source:
            payload = source.read(MAX_INPUT_BYTES + 1)
        result = inspect_listdata(payload)
    except (OSError, ListDataFormatError):
        print('Nintendo list input is unavailable or outside the supported partial schema', file=sys.stderr)
        return 1
    print(json.dumps(result.metadata(), sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
