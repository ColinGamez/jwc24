#!/usr/bin/env python3
"""Convert an archival Forecast Channel XML catalog to normalized JSON."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog_xml", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--country", default="Japan", help="English country name")
    parser.add_argument("--country-code", type=int, default=1)
    args = parser.parse_args()
    if args.output_json.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_json}")

    root = ET.parse(args.catalog_xml).getroot()
    country = next(
        (
            item
            for item in root.findall("country")
            if (item.find("name") is not None)
            and item.find("name").get("eng") == args.country
        ),
        None,
    )
    if country is None:
        parser.error(f"country not found: {args.country}")

    country_name = country.find("name").get("jpn") or args.country
    region_codes: dict[str, int] = {}
    location_counts: dict[str, int] = {}
    records = []
    for city in country.findall("city"):
        province = city.find("province")
        if province is None:
            parser.error(f"city has no province: {city.get('eng')}")
        region_key = province.get("eng") or province.get("jpn") or ""
        if region_key not in region_codes:
            region_codes[region_key] = len(region_codes) + 1
            location_counts[region_key] = 0
        location_counts[region_key] += 1
        records.append(
            {
                "country_code": args.country_code,
                "region_code": region_codes[region_key],
                "location_code": location_counts[region_key],
                "city": city.get("jpn") or city.get("eng"),
                "region": province.get("jpn") or province.get("eng"),
                "country": country_name,
                "latitude": float(city.findtext("latitude")),
                "longitude": float(city.findtext("longitude")),
                "zoom_near": int(city.findtext("zoom1")),
                "zoom_far": int(city.findtext("zoom2")),
            }
        )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {args.output_json}: {len(records)} locations across "
        f"{len(region_codes)} regions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
