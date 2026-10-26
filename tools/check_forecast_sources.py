"""Check private normalized weather/source-time receipts; never build or publish."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.forecast_freshness import (MAX_DOCUMENT_BYTES, ForecastSourceError,
                                     _json, check_forecast_sources)


def _read(path):
    with path.open('rb') as stream:
        return stream.read(MAX_DOCUMENT_BYTES + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--long', type=Path, required=True)
    parser.add_argument('--compact', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--max-source-age-seconds', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        documents = {name: _read(getattr(args, name)) for name in ('current', 'long', 'compact')}
        report = check_forecast_sources(documents, _json(_read(args.receipts)),
                                        now=int(time.time()),
                                        max_source_age_seconds=args.max_source_age_seconds)
    except (OSError, ForecastSourceError):
        print('Forecast source-time checks failed; private inputs remain unchanged', file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
