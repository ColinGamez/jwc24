#!/usr/bin/env python3
"""Inspect local CMOC response framing; print metadata without Mii payloads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.cmoc import CMOCFormatError, DEFAULT_MAX_BYTES, inspect_response


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('response', type=Path)
    args = parser.parse_args(argv)
    try:
        # Read at most the supported limit plus one byte, even if the file grows.
        with args.response.open('rb') as stream:
            data = stream.read(DEFAULT_MAX_BYTES + 1)
        result = inspect_response(data)
    except (OSError, CMOCFormatError) as error:
        print(f'Cannot inspect response: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result.metadata(), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
