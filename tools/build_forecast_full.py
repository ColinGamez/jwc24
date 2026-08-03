#!/usr/bin/env python3
"""Build forecast.bin from normalized location and forecast JSON documents."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from jwc24.forecast import (
    ForecastDay,
    ForecastLocation,
    ForecastWeekDay,
    CompactLocationForecast,
    LocationForecast,
    WeatherConditionText,
    WeatherIndexText,
    build_location_forecast_payload,
)


def _day(value: dict) -> ForecastDay:
    value = dict(value)
    value["six_hour_condition_codes"] = tuple(value["six_hour_condition_codes"])
    value["precipitation"] = tuple(value["precipitation"])
    return ForecastDay(**value)


def _forecast(value: dict) -> LocationForecast:
    return LocationForecast(
        country_code=value["country_code"],
        region_code=value["region_code"],
        location_code=value["location_code"],
        local_unix_timestamp=value["local_unix_timestamp"],
        today=_day(value["today"]),
        tomorrow=_day(value["tomorrow"]),
        week=tuple(ForecastWeekDay(**item) for item in value["week"]),
    )


def _short_forecast(value: dict) -> CompactLocationForecast:
    return CompactLocationForecast(
        country_code=value["country_code"],
        region_code=value["region_code"],
        location_code=value["location_code"],
        local_unix_timestamp=value["local_unix_timestamp"],
        today=_day(value["today"]),
        tomorrow=_day(value["tomorrow"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locations_json", type=Path)
    parser.add_argument("forecasts_json", type=Path)
    parser.add_argument("output_lz10", type=Path)
    parser.add_argument("--lookups-json", type=Path)
    parser.add_argument("--short-forecasts-json", type=Path)
    parser.add_argument("--timestamp", type=int, default=None, help="Unix timestamp")
    args = parser.parse_args()
    if args.output_lz10.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_lz10}")

    raw_locations = json.loads(args.locations_json.read_text(encoding="utf-8"))
    raw_forecasts = json.loads(args.forecasts_json.read_text(encoding="utf-8"))
    raw_short_forecasts = (
        json.loads(args.short_forecasts_json.read_text(encoding="utf-8"))
        if args.short_forecasts_json
        else []
    )
    lookups = (
        json.loads(args.lookups_json.read_text(encoding="utf-8"))
        if args.lookups_json
        else {}
    )
    if not isinstance(raw_locations, list) or not isinstance(raw_forecasts, list):
        parser.error("both JSON documents must contain lists")
    payload = build_location_forecast_payload(
        [ForecastLocation(**item) for item in raw_locations],
        forecasts=[_forecast(item) for item in raw_forecasts],
        short_forecasts=[_short_forecast(item) for item in raw_short_forecasts],
        condition_texts=[
            WeatherConditionText(**item) for item in lookups.get("conditions", [])
        ],
        uv_texts=[WeatherIndexText(**item) for item in lookups.get("uv", [])],
        laundry_texts=[
            WeatherIndexText(**item) for item in lookups.get("laundry", [])
        ],
        pollen_texts=[WeatherIndexText(**item) for item in lookups.get("pollen", [])],
        generated_unix_timestamp=args.timestamp or int(time.time()),
    )
    args.output_lz10.parent.mkdir(parents=True, exist_ok=True)
    args.output_lz10.write_bytes(payload)
    print(
        f"wrote {args.output_lz10} with {len(raw_locations)} locations and "
        f"{len(raw_forecasts)} long forecasts and "
        f"{len(raw_short_forecasts)} short forecasts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
