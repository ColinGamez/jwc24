#!/usr/bin/env python3
"""Check paired Forecast files without publishing data or changing a profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from jwc24.forecast_bundle import MAX_SIGNED_PAYLOAD_BYTES, validate_forecast_bundle


def _read_payload(path: Path) -> bytes:
    with path.open('rb') as source:
        payload = source.read(MAX_SIGNED_PAYLOAD_BYTES + 1)
    if len(payload) > MAX_SIGNED_PAYLOAD_BYTES:
        raise ValueError('Forecast bundle input exceeds the local byte limit')
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('forecast', type=Path)
    parser.add_argument('short', type=Path)
    parser.add_argument('--public-key', type=Path, help='matching JWC24 RSA public key; enables signature checks')
    parser.add_argument('--require-current', action='store_true')
    args = parser.parse_args(argv)
    result = validate_forecast_bundle(
        _read_payload(args.forecast), _read_payload(args.short),
        public_key=args.public_key,
        current_unix_timestamp=int(time.time()) if args.require_current else None,
    )
    print(json.dumps(result.metadata(), sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
