from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_hbnj_payloads import parse_hdpk, u32


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate all area-specific native HBNJ EPGs.")
    parser.add_argument("guide", type=Path)
    parser.add_argument("area_dir", type=Path)
    args = parser.parse_args()
    guide = json.loads(args.guide.read_text(encoding="utf-8"))
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
        string, string_relocs, _ = parse_hdpk(string_path)
        if len(string) != 0x20 or string_relocs:
            raise ValueError(f"area {area_id}: invalid string payload")

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
                actual_program_ids.add(program_id)
                previous_end = end
        if actual_keys != expected_keys:
            raise ValueError(f"area {area_id}: station keys differ from global header")
        if actual_program_ids != expected_program_ids:
            raise ValueError(f"area {area_id}: program IDs differ from guide")
        total_bytes += epg_path.stat().st_size
        print(
            f"area {area_id}: valid stations={station_count} "
            f"programs={len(actual_program_ids)} bytes={epg_path.stat().st_size}"
        )
    print(f"valid area payloads={len(guide['areas'])} total_epg_bytes={total_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
