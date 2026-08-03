#!/usr/bin/env python3
"""Decrypt a local Wii WAD into an explicitly private research directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from libWiiPy.title.content import ContentRegion
from libWiiPy.title.ticket import Ticket
from libWiiPy.title.tmd import TMD
from libWiiPy.title.wad import WAD


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wad", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    output = args.output.resolve()
    private_root = (Path.cwd() / "private").resolve()
    if private_root != output and private_root not in output.parents:
        parser.error(f"output must be inside {private_root}")
    if output.exists() and any(output.iterdir()):
        parser.error(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    wad_bytes = args.wad.read_bytes()
    wad = WAD()
    wad.load(wad_bytes)
    ticket = Ticket()
    ticket.load(wad.get_ticket_data())
    tmd = TMD()
    tmd.load(wad.get_tmd_data())
    region = ContentRegion()
    region.load(wad.get_content_data(), tmd.content_records)
    title_key = ticket.get_title_key()

    manifest: dict[str, object] = {
        "source": str(args.wad.resolve()),
        "source_size": len(wad_bytes),
        "source_sha256": sha256(wad_bytes),
        "title_id": ticket.get_title_id().upper(),
        "title_version": tmd.title_version,
        "contents": [],
    }
    contents: list[dict[str, object]] = []
    for position, record in enumerate(tmd.content_records):
        data = region.get_content_by_index(position, title_key)
        name = f"{record.index:04x}-{record.content_id:08x}.app"
        (output / name).write_bytes(data)
        contents.append(
            {
                "position": position,
                "index": record.index,
                "content_id": f"{record.content_id:08X}",
                "type": record.content_type,
                "size": len(data),
                "sha256": sha256(data),
                "file": name,
            }
        )
    manifest["contents"] = contents
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Extracted {len(contents)} verified contents to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
