"""Inspect private News data locally; print counts and scope, never article text."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.news import (MAX_ENVELOPE_BYTES, MAX_RAW_BYTES, NewsFormatError,
                        inspect_news, inspect_news_envelope)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--raw', action='store_true', help='input is already decompressed')
    args = parser.parse_args(argv)
    try:
        maximum = MAX_RAW_BYTES if args.raw else MAX_ENVELOPE_BYTES
        with args.input.open('rb') as source:
            data = source.read(maximum + 1)
        result = (inspect_news if args.raw else inspect_news_envelope)(data)
    except (OSError, NewsFormatError):
        print(json.dumps({'structural_inspection_passed': False,
                          'error': 'Local News input failed bounded structural inspection'}))
        return 1
    print(json.dumps(dict(structural_inspection_passed=True, **result.metadata()), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
