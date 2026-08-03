#!/usr/bin/env python3
"""Rebuild a private WAD from an immutable source WAD with content replacements."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from libWiiPy.title.content import ContentRegion
from libWiiPy.title.ticket import Ticket
from libWiiPy.title.tmd import TMD
from libWiiPy.title.wad import WAD


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_wad", type=Path)
    parser.add_argument("output_wad", type=Path)
    parser.add_argument("--replace", action="append", default=[], metavar="INDEX=FILE")
    args = parser.parse_args()
    if args.output_wad.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_wad}")
    replacements: dict[int, Path] = {}
    for value in args.replace:
        index, separator, filename = value.partition("=")
        if not separator:
            parser.error(f"invalid replacement: {value}")
        replacements[int(index, 16)] = Path(filename)

    source = WAD()
    source.load(args.source_wad.read_bytes())
    ticket = Ticket()
    ticket.load(source.get_ticket_data())
    tmd = TMD()
    tmd.load(source.get_tmd_data())
    title_key = ticket.get_title_key()
    original = ContentRegion()
    original.load(source.get_content_data(), tmd.content_records)

    region = ContentRegion()
    region.content_records = tmd.content_records
    region.num_contents = len(tmd.content_records)
    region.content_list = [b""] * region.num_contents
    for position, record in enumerate(tmd.content_records):
        replacement = replacements.get(record.index)
        content = (
            replacement.read_bytes()
            if replacement is not None
            else original.get_content_by_index(position, title_key)
        )
        region.set_content(content, position, title_key)

    tmd.fakesign()
    content_data, content_size = region.dump()
    output = WAD()
    output.set_cert_data(source.get_cert_data())
    output.set_crl_data(source.get_crl_data())
    output.set_ticket_data(ticket.dump())
    output.set_tmd_data(tmd.dump())
    output.set_content_data(content_data, content_size)
    output.set_meta_data(source.get_meta_data())
    result = output.dump()
    args.output_wad.parent.mkdir(parents=True, exist_ok=True)
    args.output_wad.write_bytes(result)
    print(f"wrote {args.output_wad} ({len(result)} bytes)")
    print(f"SHA-256 {hashlib.sha256(result).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
