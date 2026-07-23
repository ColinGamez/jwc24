from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def parse_hdpk(path: Path) -> tuple[bytearray, list[int], str]:
    raw = path.read_bytes()
    if raw[:8] != b"HDPK001B":
        raise ValueError(f"{path}: not raw HDPK001B")
    total, data_len, reloc_count, root_count, names_len = struct.unpack_from(">IIIII", raw, 8)
    if total != len(raw) or root_count != 1:
        raise ValueError(f"{path}: invalid size/root count")
    reloc_base = 0x20 + ((data_len + 3) & ~3)
    roots_base = reloc_base + reloc_count * 4
    names_base = roots_base + root_count * 8
    if names_base + names_len != len(raw):
        raise ValueError(f"{path}: malformed tables")
    data = bytearray(raw[0x20:0x20 + data_len])
    relocs = [u32(raw, reloc_base + index * 4) for index in range(reloc_count)]
    if relocs != sorted(set(relocs)):
        raise ValueError(f"{path}: relocation offsets are not sorted and unique")
    for offset in relocs:
        if offset + 4 > len(data) or u32(data, offset) >= len(data):
            raise ValueError(f"{path}: invalid relocation at 0x{offset:x}")
    root_offset, root_name_offset = struct.unpack_from(">II", raw, roots_base)
    if root_offset != 0 or root_name_offset >= names_len:
        raise ValueError(f"{path}: invalid root record")
    root = raw[names_base + root_name_offset:names_base + names_len].split(b"\0", 1)[0].decode("ascii")
    if root != "main":
        raise ValueError(f"{path}: expected root main, got {root!r}")
    return data, relocs, root


def read_text(data: bytearray, offset: int) -> str:
    if offset >= len(data) or offset & 1:
        raise ValueError("string pointer out of range")
    end = offset
    while end + 1 < len(data) and data[end:end + 2] != b"\0\0":
        end += 2
    if end + 1 >= len(data):
        raise ValueError("unterminated UTF-16BE string")
    return bytes(data[offset:end]).decode("utf-16-be", errors="strict")


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently validate native HBNJ payloads.")
    parser.add_argument("guide", type=Path)
    parser.add_argument("payload_dir", type=Path)
    args = parser.parse_args()
    guide = json.loads(args.guide.read_text(encoding="utf-8"))

    header, _, _ = parse_hdpk(args.payload_dir / "header.hdpk")
    epg, _, _ = parse_hdpk(args.payload_dir / "epg.hdpk")
    string, string_relocs, _ = parse_hdpk(args.payload_dir / "string.hdpk")
    if u32(header, 0) != 1:
        raise ValueError("header preflight status is not 1")
    string_count = u32(string, 0x18)
    string_table = u32(string, 0x1C)
    if string_count != len(guide["programs"]) or not string_table:
        raise ValueError("string table count does not match guide")

    station_count = u32(header, 0x34)
    station_table = u32(header, 0x38)
    header_keys = []
    for index in range(station_count):
        entry = station_table + index * 0x0C
        key = u32(header, entry)
        if key >> 16 != 9:
            raise ValueError("non-terrestrial station key")
        read_text(header, u32(header, entry + 4))
        header_keys.append(key)
    if station_count != len(guide["channels"]) or len(set(header_keys)) != station_count:
        raise ValueError("header station table does not match guide")

    area_count = u32(header, 0x3C)
    area_table = u32(header, 0x40)
    memberships = 0
    for index in range(area_count):
        entry = area_table + index * 0x10
        read_text(header, u32(header, entry + 4))
        count = u32(header, entry + 8)
        table = u32(header, entry + 0x0C)
        if not count or not u16(header, entry) or not header[entry + 2]:
            raise ValueError("invalid area entry")
        for member_index in range(count):
            key = u32(header, table + member_index * 0x0C)
            if key not in header_keys:
                raise ValueError("area references missing station key")
        memberships += count
    expected_memberships = sum(len(area["channel_ids"]) for area in guide["areas"])
    if area_count != len(guide["areas"]) or memberships != expected_memberships:
        raise ValueError("area table does not match guide")

    epg_station_count = u32(epg, 0x1C)
    epg_station_table = u32(epg, 0x20)
    epg_keys = []
    program_ids = []
    string_positions = []
    guide_programs = {int(program["id"]): program for program in guide["programs"]}
    for index in range(epg_station_count):
        entry = epg_station_table + index * 0x0C
        key, count, refs = u32(epg, entry), u32(epg, entry + 4), u32(epg, entry + 8)
        epg_keys.append(key)
        if not count:
            raise ValueError("EPG station has no programs")
        previous_end = None
        for program_index in range(count):
            ref = refs + program_index * 8
            program_id, detail = u32(epg, ref), u32(epg, ref + 4)
            start, end, title = u32(epg, detail), u32(epg, detail + 4), u32(epg, detail + 8)
            if end <= start or (previous_end is not None and start < previous_end):
                raise ValueError("invalid or overlapping native program window")
            read_text(epg, title)
            program_ids.append(program_id)
            position = u32(epg, detail + 0x14)
            if not 1 <= position <= string_count:
                raise ValueError("EPG program has invalid string-table position")
            record = string_table + (position - 1) * 8
            first, second = u32(string, record), u32(string, record + 4)
            expected_description = str(guide_programs[program_id].get("description", "")).strip()
            if (read_text(string, first) if first else "") != expected_description:
                raise ValueError("native program description does not match guide")
            if second:
                read_text(string, second)
            string_positions.append(position)
            previous_end = end
    if epg_keys != header_keys:
        raise ValueError("header and EPG station keys differ")
    if len(program_ids) != len(guide["programs"]) or len(set(program_ids)) != len(program_ids):
        raise ValueError("native program table count/IDs are invalid")
    if set(program_ids) != {int(program["id"]) for program in guide["programs"]}:
        raise ValueError("native program IDs do not match guide")
    if sorted(string_positions) != list(range(1, string_count + 1)):
        raise ValueError("EPG string-table positions are not a complete unique sequence")

    print(
        f"valid native HBNJ payloads: stations={station_count} areas={area_count} "
        f"memberships={memberships} programs={len(program_ids)} "
        f"range={u32(epg, 0x10)}..{u32(epg, 0x14)} root=main status=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
