#!/usr/bin/env python3
"""Find likely network and service strings in decrypted channel contents."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ASCII_STRING = re.compile(rb"[\x20-\x7e]{4,}")
INTERESTING = re.compile(
    r"(?i)(https?://|\.cgi(?:\b|/|\?)|\.xml(?:\b|/|\?)|\.bin(?:\b|/|\?)|"
    r"\.dat(?:\b|/|\?)|host:|user-agent:|content-type:|nintendo|wii\.com|"
    r"socket|connect24|download|upload|server)"
)


def scan(path: Path) -> list[dict[str, object]]:
    data = path.read_bytes()
    hits: list[dict[str, object]] = []
    for match in ASCII_STRING.finditer(data):
        value = match.group().decode("ascii")
        if INTERESTING.search(value):
            hits.append({"offset": f"0x{match.start():08X}", "value": value})
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    records = []
    for path in sorted(args.directory.glob("*.app")):
        hits = scan(path)
        if hits:
            records.append({"file": path.name, "hits": hits})
    if args.json:
        print(json.dumps(records, indent=2, ensure_ascii=False))
    else:
        for record in records:
            print(f"[{record['file']}]")
            for hit in record["hits"]:
                print(f"{hit['offset']}  {hit['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
