#!/usr/bin/env python3
"""Inventory stock Wii WADs and unpacked NUS titles without modifying them."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ALIGNMENT = 0x40


def align(value: int) -> int:
    return (value + ALIGNMENT - 1) & ~(ALIGNMENT - 1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_tmd(data: bytes) -> dict[str, int | str]:
    if len(data) < 0x1E4:
        raise ValueError("TMD is too short")
    signature_type = struct.unpack_from(">I", data, 0)[0]
    signed_offsets = {0x00010000: 0x240, 0x00010001: 0x140, 0x00010002: 0x80}
    signed = signed_offsets.get(signature_type)
    if signed is None:
        raise ValueError(f"unsupported TMD signature type 0x{signature_type:08x}")
    if len(data) < signed + 0xA4:
        raise ValueError("TMD signed payload is too short")
    title_id = struct.unpack_from(">Q", data, signed + 0x4C)[0]
    title_version = struct.unpack_from(">H", data, signed + 0x9C)[0]
    content_count = struct.unpack_from(">H", data, signed + 0x9E)[0]
    boot_index = struct.unpack_from(">H", data, signed + 0xA0)[0]
    ios = struct.unpack_from(">Q", data, signed + 0x44)[0]
    return {
        "title_id": f"{title_id:016X}",
        "title_version": title_version,
        "content_count": content_count,
        "boot_index": boot_index,
        "required_ios": ios & 0xFFFFFFFF,
    }


def wad_tmd(path: Path) -> bytes:
    header = path.read_bytes()[:0x20]
    if len(header) != 0x20:
        raise ValueError("WAD header is too short")
    header_size, _wad_type, _version, cert_size, crl_size, ticket_size, tmd_size = (
        struct.unpack_from(">IHHIIII", header, 0)
    )
    offset = align(header_size)
    offset += align(cert_size)
    offset += align(crl_size)
    offset += align(ticket_size)
    with path.open("rb") as source:
        source.seek(offset)
        data = source.read(tmd_size)
    if len(data) != tmd_size:
        raise ValueError("WAD contains a truncated TMD")
    return data


def inventory_wad(path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "kind": "wad",
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": sha256(path),
    }
    try:
        result.update(parse_tmd(wad_tmd(path)))
    except (OSError, ValueError, struct.error) as error:
        result["error"] = str(error)
    return result


def inventory_nus_title(path: Path) -> dict[str, object]:
    tmd_path = path / "tmd"
    result: dict[str, object] = {
        "kind": "nus-title",
        "path": str(path),
        "files": [
            {
                "name": item.name,
                "size": item.stat().st_size,
                "sha256": sha256(item),
            }
            for item in sorted(path.iterdir())
            if item.is_file()
        ],
    }
    try:
        result.update(parse_tmd(tmd_path.read_bytes()))
    except (OSError, ValueError, struct.error) as error:
        result["error"] = str(error)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wads", type=Path, required=True, help="directory of stock WADs")
    parser.add_argument("--nus-title", type=Path, action="append", default=[])
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    records = [inventory_wad(path) for path in sorted(args.wads.glob("*.wad"))]
    records.extend(inventory_nus_title(path) for path in args.nus_title)
    if args.json:
        print(json.dumps(records, indent=2, ensure_ascii=False))
    else:
        for record in records:
            if "error" in record:
                print(f"ERROR  {record.get('name', record.get('path'))}: {record['error']}")
                continue
            print(
                f"{record['title_id']} v{record['title_version']:<4} "
                f"IOS{record['required_ios']:<3} {record['content_count']:>2} contents  "
                f"{record.get('name', record.get('path'))}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
