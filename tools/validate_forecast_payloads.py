#!/usr/bin/env python3
"""Validate signed Forecast Channel forecast.bin and optional short.bin."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from jwc24.forecast import unix_to_wii_minutes, validate_forecast, validate_short


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("forecast", type=Path)
    parser.add_argument("short", type=Path, nargs="?")
    parser.add_argument(
        "--require-current", action="store_true",
        help="reject files outside their validity window at the current time",
    )
    parser.add_argument(
        "--find-location",
        help="require a case-sensitive substring in a city or region name",
    )
    args = parser.parse_args()
    current_minute = unix_to_wii_minutes(int(time.time())) if args.require_current else None
    forecast = validate_forecast(args.forecast.read_bytes())
    if current_minute is not None and not forecast.open_timestamp <= current_minute < forecast.close_timestamp:
        raise ValueError("forecast.bin is outside its current validity window")
    print(
        f"forecast.bin: {forecast.file_size} bytes, {forecast.locations} locations, "
        f"country={forecast.country_code:03d}, language={forecast.language_code}"
    )
    if args.short:
        short = validate_short(args.short.read_bytes())
        if current_minute is not None and not short.open_timestamp <= current_minute < short.close_timestamp:
            raise ValueError("short.bin is outside its current validity window")
        if (forecast.country_code, forecast.language_code) != (
            short.country_code,
            short.language_code,
        ):
            raise ValueError("forecast.bin and short.bin locale fields differ")
        print(
            f"short.bin: {short.file_size} bytes, "
            f"{short.current_forecasts} current forecasts"
        )
    if args.find_location:
        matches = [
            record
            for record in forecast.location_records
            if args.find_location in record.city or args.find_location in record.region
        ]
        if not matches:
            raise ValueError(f"location not present: {args.find_location}")
        for record in matches:
            print(
                f"location: {record.country}/{record.region}/{record.city} "
                f"key={record.country_code:03d}/{record.region_code:03d}/{record.location_code:03d} "
                f"lat={record.latitude:.4f} lon={record.longitude:.4f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
