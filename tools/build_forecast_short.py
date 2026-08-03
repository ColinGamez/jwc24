#!/usr/bin/env python3
"""Build an unsigned short.bin body from normalized current-weather JSON."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from jwc24.forecast import CurrentWeatherRecord, build_short_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("weather_json", type=Path)
    parser.add_argument("output_lz10", type=Path)
    parser.add_argument("--timestamp", type=int, default=None, help="Unix timestamp")
    args = parser.parse_args()
    if args.output_lz10.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_lz10}")

    document = json.loads(args.weather_json.read_text(encoding="utf-8"))
    if not isinstance(document, list):
        parser.error("weather JSON must be a list")
    records = [CurrentWeatherRecord(**record) for record in document]
    payload = build_short_payload(
        records,
        generated_unix_timestamp=args.timestamp or int(time.time()),
    )
    args.output_lz10.parent.mkdir(parents=True, exist_ok=True)
    args.output_lz10.write_bytes(payload)
    print(f"wrote {args.output_lz10} with {len(records)} current forecasts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
