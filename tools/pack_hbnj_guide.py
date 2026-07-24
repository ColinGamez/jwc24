from __future__ import annotations

import argparse
import json
import struct
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT_NAME = b"main\0"
WII_EPOCH = datetime(2000, 1, 1)
TERRESTRIAL_DIGITAL = 9
GENRE_NAMES = (
    "ニュース／報道",
    "スポーツ",
    "情報／ワイドショー",
    "ドラマ",
    "音楽",
    "バラエティ",
    "映画",
    "アニメ／特撮",
    "ドキュメンタリー／教養",
    "劇場／公演",
    "趣味／教育",
    "福祉",
)


def align(value: int, amount: int = 4) -> int:
    return (value + amount - 1) & ~(amount - 1)


def put_u32(data: bytearray, offset: int, value: int, relocs: set[int] | None = None) -> None:
    struct.pack_into(">I", data, offset, value & 0xFFFFFFFF)
    if relocs is not None:
        relocs.add(offset)


def put_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into(">H", data, offset, value & 0xFFFF)


def cstr(text: str) -> bytes:
    return text.encode("utf-16-be", errors="strict") + b"\0\0"


def wii_seconds(value: str) -> int:
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=None)
    seconds = int((timestamp - WII_EPOCH).total_seconds())
    if not 0 <= seconds <= 0xFFFFFFFF:
        raise ValueError(f"timestamp is outside Wii range: {value}")
    return seconds


def make_hdpk(data: bytes | bytearray, relocs: set[int]) -> bytes:
    data = bytes(data)
    padding = b"\0" * (align(len(data)) - len(data))
    reloc_table = b"".join(struct.pack(">I", offset) for offset in sorted(relocs))
    roots = struct.pack(">II", 0, 0)
    total_size = 0x20 + len(data) + len(padding) + len(reloc_table) + len(roots) + len(ROOT_NAME)
    header = bytearray(0x20)
    header[:8] = b"HDPK001B"
    struct.pack_into(">IIIII", header, 0x08, total_size, len(data), len(relocs), 1, len(ROOT_NAME))
    return bytes(header) + data + padding + reloc_table + roots + ROOT_NAME


def station_maps(channels: list[dict]) -> tuple[dict[int, dict], dict[int, int]]:
    by_id = {int(channel["id"]): channel for channel in channels}
    if len(by_id) != len(channels):
        raise ValueError("duplicate channel IDs")
    keys = {
        channel_id: (TERRESTRIAL_DIGITAL << 16) | index
        for index, channel_id in enumerate(by_id, start=1)
    }
    return by_id, keys


def ordered_program_rows(
    document: dict,
    channel_by_id: dict[int, dict],
) -> tuple[dict[int, list[dict]], list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for program in document["programs"]:
        channel_id = int(program["channel_id"])
        if channel_id not in channel_by_id:
            raise ValueError(f"program references missing channel {channel_id}")
        grouped[channel_id].append(program)
    if set(grouped) != set(channel_by_id):
        raise ValueError("every channel must have at least one program")

    programs: list[dict] = []
    for channel_id in channel_by_id:
        rows = sorted(grouped[channel_id], key=lambda row: row["start"])
        for previous, current in zip(rows, rows[1:]):
            if datetime.fromisoformat(current["start"]) < datetime.fromisoformat(previous["end"]):
                raise ValueError(f"overlapping programs on channel {channel_id}")
        grouped[channel_id] = rows
        programs.extend(rows)
    return grouped, programs


def make_header(document: dict, channel_by_id: dict[int, dict], keys: dict[int, int]) -> bytes:
    channels = list(channel_by_id.values())
    areas = document["areas"]
    root_size = 0x78
    station_table = root_size
    area_table = station_table + len(channels) * 0x0C
    cursor = area_table + len(areas) * 0x10
    member_tables = []
    for area in areas:
        member_tables.append(cursor)
        cursor += len(area["channel_ids"]) * 0x0C

    genre_table = cursor
    cursor += len(GENRE_NAMES) * 8
    station_names = []
    for channel in channels:
        encoded = cstr(str(channel["name"]))
        station_names.append((cursor, encoded))
        cursor += len(encoded)
    station_aux = cursor
    cursor += len(cstr("station"))
    area_names = []
    for area in areas:
        encoded = cstr(str(area["name"]))
        area_names.append((cursor, encoded))
        cursor += len(encoded)
    genre_names = []
    for name in GENRE_NAMES:
        encoded = cstr(name)
        genre_names.append((cursor, encoded))
        cursor += len(encoded)

    data = bytearray(cursor)
    relocs: set[int] = set()
    put_u32(data, 0x00, 1)  # HeaderDownload preflight status.
    put_u32(data, 0x34, len(channels))
    put_u32(data, 0x38, station_table, relocs)
    for index, channel in enumerate(channels):
        entry = station_table + index * 0x0C
        put_u32(data, entry, keys[int(channel["id"])])
        put_u32(data, entry + 4, station_names[index][0], relocs)
        data[entry + 8] = TERRESTRIAL_DIGITAL

    put_u32(data, 0x3C, len(areas))
    put_u32(data, 0x40, area_table, relocs)
    for index, area in enumerate(areas):
        entry = area_table + index * 0x10
        members = [int(value) for value in area["channel_ids"]]
        missing = set(members) - channel_by_id.keys()
        if missing:
            raise ValueError(f"area {area['id']} references missing channels")
        put_u16(data, entry, int(area["id"]))
        data[entry + 2] = int(area["prefecture_raw"])
        put_u32(data, entry + 4, area_names[index][0], relocs)
        put_u32(data, entry + 8, len(members))
        put_u32(data, entry + 0x0C, member_tables[index], relocs)
        for member_index, channel_id in enumerate(members):
            member = member_tables[index] + member_index * 0x0C
            put_u32(data, member, keys[channel_id])
            put_u16(data, member + 4, member_index + 1)
            put_u16(data, member + 6, member_index + 1)
            put_u32(data, member + 8, 1)

    # Genre records are ordered exactly like the one-based genre IDs stored in
    # EPG details. Their main positions are zero-based; this broad-category
    # table has one sub-entry (position zero) under each main category.
    put_u32(data, 0x44, len(GENRE_NAMES))
    put_u32(data, 0x48, genre_table, relocs)
    for index, (text_offset, _) in enumerate(genre_names):
        entry = genre_table + index * 8
        data[entry] = index
        data[entry + 1] = 0
        put_u32(data, entry + 4, text_offset, relocs)

    for offset, encoded in station_names + area_names + genre_names:
        data[offset:offset + len(encoded)] = encoded
    data[station_aux:station_aux + len(cstr("station"))] = cstr("station")
    return make_hdpk(data, relocs)


def make_epg(document: dict, channel_by_id: dict[int, dict], keys: dict[int, int]) -> bytes:
    grouped, programs = ordered_program_rows(document, channel_by_id)
    ordered_channels = list(channel_by_id)

    root_size = 0x2C
    station_table = root_size
    refs = station_table + len(ordered_channels) * 0x0C
    details = refs + len(programs) * 0x08
    cursor = details + len(programs) * 0x18
    titles = []
    for program in programs:
        encoded = cstr(str(program["title"]))
        titles.append((cursor, encoded))
        cursor += len(encoded)

    data = bytearray(cursor)
    relocs: set[int] = set()
    starts = [wii_seconds(program["start"]) for program in programs]
    ends = [wii_seconds(program["end"]) for program in programs]
    put_u32(data, 0x10, min(starts))
    put_u32(data, 0x14, max(ends))
    put_u32(data, 0x1C, len(ordered_channels))
    put_u32(data, 0x20, station_table, relocs)

    program_index = 0
    for station_index, channel_id in enumerate(ordered_channels):
        rows = sorted(grouped[channel_id], key=lambda row: row["start"])
        station = station_table + station_index * 0x0C
        put_u32(data, station, keys[channel_id])
        put_u32(data, station + 4, len(rows))
        put_u32(data, station + 8, refs + program_index * 8, relocs)
        for program in rows:
            ref = refs + program_index * 8
            detail = details + program_index * 0x18
            put_u32(data, ref, int(program["id"]))
            put_u32(data, ref + 4, detail, relocs)
            put_u32(data, detail, wii_seconds(program["start"]))
            put_u32(data, detail + 4, wii_seconds(program["end"]))
            put_u32(data, detail + 8, titles[program_index][0], relocs)
            genre_id = int(program.get("genre_id", 0))
            if not 0 <= genre_id <= 0xFF:
                raise ValueError(f"invalid genre ID {genre_id} for program {program['id']}")
            data[detail + 0x0C] = genre_id
            put_u32(data, detail + 0x14, program_index + 1)
            program_index += 1

    for offset, encoded in titles:
        data[offset:offset + len(encoded)] = encoded
    return make_hdpk(data, relocs)


def make_string(document: dict, channel_by_id: dict[int, dict]) -> bytes:
    _, programs = ordered_program_rows(document, channel_by_id)
    root_size = 0x20
    table = root_size
    cursor = table + len(programs) * 8
    descriptions: list[tuple[int, bytes] | None] = []
    for program in programs:
        description = str(program.get("description", "")).strip()
        if description:
            encoded = cstr(description)
            descriptions.append((cursor, encoded))
            cursor += len(encoded)
        else:
            descriptions.append(None)

    data = bytearray(cursor)
    relocs: set[int] = set()
    put_u32(data, 0x18, len(programs))
    put_u32(data, 0x1C, table, relocs)
    for index, description in enumerate(descriptions):
        if description is None:
            continue
        offset, encoded = description
        put_u32(data, table + index * 8, offset, relocs)
        data[offset:offset + len(encoded)] = encoded
    return make_hdpk(data, relocs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack strict JWC24 guide JSON into native HBNJ HDPK.")
    parser.add_argument("guide", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.guide.read_text(encoding="utf-8"))
    if document.get("format") != "jwc24_hbnj_guide_v1":
        raise SystemExit("unsupported guide format")
    channel_by_id, keys = station_maps(document["channels"])
    files = {
        "header.hdpk": make_header(document, channel_by_id, keys),
        "epg.hdpk": make_epg(document, channel_by_id, keys),
        "string.hdpk": make_string(document, channel_by_id),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        (args.out_dir / name).write_bytes(payload)
        print(f"{name}: {len(payload)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
