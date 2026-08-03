#!/usr/bin/env python3
"""Rebuild a private installable WAD from a Dolphin NAND title."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from libWiiPy.title.content import ContentRegion
from libWiiPy.title.ticket import Ticket
from libWiiPy.title.tmd import TMD
from libWiiPy.title.wad import WAD


def _shared_map(shared_dir: Path) -> dict[str, Path]:
    data = (shared_dir / "content.map").read_bytes()
    if len(data) % 28:
        raise ValueError("Dolphin shared content map has an invalid length")
    return {
        data[pos + 8 : pos + 28].hex(): shared_dir / (data[pos : pos + 8].decode("ascii") + ".app")
        for pos in range(0, len(data), 28)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nand_root", type=Path)
    parser.add_argument("title_id", help="16 hexadecimal digits")
    parser.add_argument("certificate_donor_wad", type=Path)
    parser.add_argument("output_wad", type=Path)
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="INDEX=FILE",
        help="replace a TMD content index (hexadecimal) with a decrypted file",
    )
    args = parser.parse_args()
    if args.output_wad.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_wad}")
    if len(args.title_id) != 16:
        parser.error("title ID must contain exactly 16 hexadecimal digits")

    replacements: dict[int, Path] = {}
    for value in args.replace:
        index, separator, filename = value.partition("=")
        if not separator:
            parser.error(f"invalid replacement: {value}")
        replacements[int(index, 16)] = Path(filename)

    high, low = args.title_id[:8].lower(), args.title_id[8:].lower()
    content_dir = args.nand_root / "title" / high / low / "content"
    ticket_path = args.nand_root / "ticket" / high / f"{low}.tik"
    tmd = TMD()
    tmd.load((content_dir / "title.tmd").read_bytes())
    ticket = Ticket()
    ticket.load(ticket_path.read_bytes())
    title_key = ticket.get_title_key()
    shared = _shared_map(args.nand_root / "shared1")

    region = ContentRegion()
    region.content_records = tmd.content_records
    region.num_contents = len(tmd.content_records)
    region.content_list = [b""] * region.num_contents
    for position, record in enumerate(tmd.content_records):
        replacement = replacements.get(record.index)
        if replacement is not None:
            content = replacement.read_bytes()
        else:
            local = content_dir / f"{record.content_id:08x}.app"
            source = local if local.exists() else shared.get(record.content_hash.decode())
            if source is None or not source.exists():
                raise FileNotFoundError(
                    f"content {record.content_id:08x} (index {record.index:04x}) was not found"
                )
            content = source.read_bytes()
        region.set_content(content, position, title_key)

    tmd.fakesign()
    content_data, content_size = region.dump()
    donor = WAD()
    donor.load(args.certificate_donor_wad.read_bytes())
    wad = WAD()
    wad.set_cert_data(donor.get_cert_data())
    wad.set_crl_data(donor.get_crl_data())
    wad.set_ticket_data(ticket.dump())
    wad.set_tmd_data(tmd.dump())
    wad.set_content_data(content_data, content_size)
    wad.set_meta_data(b"")
    output = wad.dump()
    args.output_wad.parent.mkdir(parents=True, exist_ok=True)
    args.output_wad.write_bytes(output)
    print(f"wrote {args.output_wad} ({len(output)} bytes)")
    print(f"SHA-256 {hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
