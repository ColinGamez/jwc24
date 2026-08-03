#!/usr/bin/env python3
"""Build an unsigned forecast.bin body from a normalized location JSON file."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from jwc24.forecast import ForecastLocation, build_location_forecast_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locations_json", type=Path)
    parser.add_argument("output_lz10", type=Path)
    parser.add_argument("--timestamp", type=int, default=None, help="Unix timestamp")
    args = parser.parse_args()
    if args.output_lz10.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_lz10}")

    document = json.loads(args.locations_json.read_text(encoding="utf-8"))
    if not isinstance(document, list):
        parser.error("location JSON must be a list")
    locations = [ForecastLocation(**record) for record in document]
    payload = build_location_forecast_payload(
        locations,
        generated_unix_timestamp=args.timestamp or int(time.time()),
    )
    args.output_lz10.parent.mkdir(parents=True, exist_ok=True)
    args.output_lz10.write_bytes(payload)
    print(f"wrote {args.output_lz10} with {len(locations)} locations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
