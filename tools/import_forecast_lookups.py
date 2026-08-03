#!/usr/bin/env python3
"""Convert archival Forecast lookup tables to normalized Japanese JSON."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog_xml", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    if args.output_json.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_json}")
    root = ET.parse(args.catalog_xml).getroot()

    conditions = []
    for item in root.findall("./conditions/condition"):
        text = item.find("name").get("jpn")
        conditions.extend(
            (
                {
                    "code_primary": int(item.findtext("code_1"), 16),
                    "code_secondary": int(item.findtext("code_2"), 16),
                    "text": text,
                },
                {
                    "code_primary": int(item.findtext("japanese_code_1"), 16),
                    "code_secondary": int(item.findtext("japanese_code_2"), 16),
                    "text": text,
                },
            )
        )

    def indices(tag: str, *, enumerate_codes: bool = False) -> list[dict]:
        output = []
        for position, item in enumerate(root.findall(tag)):
            name = item.find("name")
            text = name.get("jpn") if name.attrib else name.text
            output.append(
                {
                    "code": position if enumerate_codes else int(item.findtext("code")),
                    "text": text.strip(),
                }
            )
        return output

    document = {
        "conditions": conditions,
        "uv": indices("uv", enumerate_codes=True),
        "laundry": indices("laundry"),
        "pollen": indices("pollen"),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {args.output_json}: {len(conditions)} conditions, "
        f"{len(document['uv'])} UV, {len(document['laundry'])} laundry, "
        f"{len(document['pollen'])} pollen entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
