#!/usr/bin/env python3
"""Extract the normalized location catalog from a signed Forecast payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jwc24.forecast import FORECAST_HEADER, LOCATION, unwrap_signed_payload


def text_at(raw: bytes, offset: int) -> str:
    if offset == 0:
        return ""
    if offset < FORECAST_HEADER.size or offset >= len(raw):
        raise ValueError(f"text offset outside payload: {offset}")
    end = offset
    while end + 1 < len(raw) and raw[end : end + 2] != b"\0\0":
        end += 2
    if end + 1 >= len(raw):
        raise ValueError(f"unterminated UTF-16 text at {offset}")
    return raw[offset:end].decode("utf-16-be")


def coordinate(value: int) -> float:
    return value * 45 / 8192


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("forecast_bin", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    if args.output_json.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_json}")

    raw = unwrap_signed_payload(args.forecast_bin.read_bytes())
    header = FORECAST_HEADER.unpack_from(raw)
    count, offset = header[23], header[24]
    if offset + count * LOCATION.size > len(raw):
        raise ValueError("location table lies outside payload")

    records = []
    keys = set()
    for index in range(count):
        row = LOCATION.unpack_from(raw, offset + index * LOCATION.size)
        key = row[:3]
        if key in keys:
            raise ValueError(f"duplicate location key: {key}")
        keys.add(key)
        records.append(
            {
                "country_code": row[0],
                "region_code": row[1],
                "location_code": row[2],
                "city": text_at(raw, row[3]),
                "region": text_at(raw, row[4]),
                "country": text_at(raw, row[5]),
                "latitude": coordinate(row[6]),
                "longitude": coordinate(row[7]),
                "zoom_near": row[8],
                "zoom_far": row[9],
            }
        )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output_json} with {len(records)} locations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
