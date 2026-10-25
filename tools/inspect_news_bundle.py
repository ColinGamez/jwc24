"""Inspect 24 explicit private News files; no task mapping, acquisition or upload."""
import argparse
import json
from pathlib import Path

from jwc24.news import MAX_ENVELOPE_BYTES, MAX_RAW_BYTES, NewsFormatError
from jwc24.news_bundle import MAX_BUNDLE_BYTES, SLOT_COUNT, inspect_news_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path, nargs='+')
    parser.add_argument('--raw', action='store_true')
    args = parser.parse_args(argv)
    try:
        if len(args.inputs) != SLOT_COUNT:
            raise NewsFormatError('Expected 24 explicit News files')
        buffers, used = [], 0
        maximum = MAX_RAW_BYTES if args.raw else MAX_ENVELOPE_BYTES
        for path in args.inputs:
            with path.open('rb') as source:
                value = source.read(min(maximum, MAX_BUNDLE_BYTES - used) + 1)
            used += len(value)
            if len(value) > maximum or used > MAX_BUNDLE_BYTES:
                raise NewsFormatError('News bundle exceeds local input bounds')
            buffers.append(value)
        result = inspect_news_bundle(buffers, enveloped=not args.raw)
    except (OSError, NewsFormatError):
        print(json.dumps({'bundle_inspection_passed': False,
                          'error': 'Explicit News buffer set failed bounded inspection'}))
        return 1
    print(json.dumps(dict(bundle_inspection_passed=True, **result.metadata()), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
