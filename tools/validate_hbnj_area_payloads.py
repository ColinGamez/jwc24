from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_hbnj_payloads import parse_hdpk, read_text, u32

LZ10_MAX_INPUT = 0xFFFFFF
VFF_CAPACITY = 4 * 1024 * 1024


def literal_lz10_size(raw_size: int) -> int:
    if not 0 < raw_size <= LZ10_MAX_INPUT:
        raise ValueError(f"payload cannot be represented by Nintendo LZ10: {raw_size} bytes")
    return 4 + raw_size + (raw_size + 7) // 8


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate all area-specific native HBNJ EPGs.")
    parser.add_argument("guide", type=Path)
    parser.add_argument("area_dir", type=Path)
    args = parser.parse_args()
    guide = json.loads(args.guide.read_text(encoding="utf-8"))
    header_path = args.area_dir.parent / "header.hdpk"
    header_size = header_path.stat().st_size
    channel_order = [int(channel["id"]) for channel in guide["channels"]]
    key_by_channel = {
        channel_id: (9 << 16) | index
        for index, channel_id in enumerate(channel_order, start=1)
    }
    program_ids_by_channel: dict[int, set[int]] = {}
    for program in guide["programs"]:
        program_ids_by_channel.setdefault(int(program["channel_id"]), set()).add(
            int(program["id"])
        )

    total_bytes = 0
    for area in guide["areas"]:
        area_id = int(area["id"])
        epg_path = args.area_dir / str(area_id) / "epg.hdpk"
        string_path = args.area_dir / str(area_id) / "string.hdpk"
        epg, _, _ = parse_hdpk(epg_path)
        string, _, _ = parse_hdpk(string_path)

        expected_channels = [int(value) for value in area["channel_ids"]]
        expected_keys = [key_by_channel[channel_id] for channel_id in expected_channels]
        expected_program_ids = {
            program_id
            for channel_id in expected_channels
            for program_id in program_ids_by_channel[channel_id]
        }
        station_count = u32(epg, 0x1C)
        station_table = u32(epg, 0x20)
        actual_keys: list[int] = []
        actual_program_ids: set[int] = set()
        string_count = u32(string, 0x18)
        string_table = u32(string, 0x1C)
        string_positions: set[int] = set()
        for index in range(station_count):
            station = station_table + index * 0x0C
            key, count, refs = u32(epg, station), u32(epg, station + 4), u32(epg, station + 8)
            actual_keys.append(key)
            previous_end = None
            for program_index in range(count):
                ref = refs + program_index * 8
                program_id, detail = u32(epg, ref), u32(epg, ref + 4)
                start, end = u32(epg, detail), u32(epg, detail + 4)
                if end <= start or (previous_end is not None and start < previous_end):
                    raise ValueError(f"area {area_id}: invalid native time window")
                position = u32(epg, detail + 0x14)
                if not 1 <= position <= string_count:
                    raise ValueError(f"area {area_id}: invalid string-table position")
                record = string_table + (position - 1) * 8
                first, second = u32(string, record), u32(string, record + 4)
                if first:
                    read_text(string, first)
                if second:
                    read_text(string, second)
                string_positions.add(position)
                actual_program_ids.add(program_id)
                previous_end = end
        if actual_keys != expected_keys:
            raise ValueError(f"area {area_id}: station keys differ from global header")
        if actual_program_ids != expected_program_ids:
            raise ValueError(f"area {area_id}: program IDs differ from guide")
        if string_count != len(expected_program_ids):
            raise ValueError(f"area {area_id}: string record count differs from programs")
        if string_positions != set(range(1, string_count + 1)):
            raise ValueError(f"area {area_id}: incomplete string-table positions")
        epg_size = epg_path.stat().st_size
        string_size = string_path.stat().st_size
        wc24_download_bytes = literal_lz10_size(epg_size) + literal_lz10_size(string_size)
        vff_payload_bytes = header_size + wc24_download_bytes
        if vff_payload_bytes >= VFF_CAPACITY:
            raise ValueError(
                f"area {area_id}: native payloads exceed the 4 MiB VFF capacity "
                f"before filesystem overhead ({vff_payload_bytes} bytes)"
            )
        total_bytes += epg_size + string_size
        print(
            f"area {area_id}: valid stations={station_count} "
            f"programs={len(actual_program_ids)} raw={epg_size + string_size} "
            f"wc24={wc24_download_bytes} vff_payload={vff_payload_bytes}"
        )
    print(f"valid area payloads={len(guide['areas'])} total_raw_bytes={total_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
