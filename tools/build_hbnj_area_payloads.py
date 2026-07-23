from __future__ import annotations

import argparse
import json
from pathlib import Path

from pack_hbnj_guide import make_epg, make_string, station_maps


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one native EPG per HBNJ broadcast area.")
    parser.add_argument("guide", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.guide.read_text(encoding="utf-8"))
    channel_by_id, global_keys = station_maps(document["channels"])
    programs_by_channel: dict[int, list[dict]] = {}
    for program in document["programs"]:
        programs_by_channel.setdefault(int(program["channel_id"]), []).append(program)

    for area in document["areas"]:
        channel_ids = [int(value) for value in area["channel_ids"]]
        area_channels = {channel_id: channel_by_id[channel_id] for channel_id in channel_ids}
        area_programs = [
            program
            for channel_id in channel_ids
            for program in programs_by_channel.get(channel_id, [])
        ]
        area_document = {
            **document,
            "areas": [area],
            "channels": list(area_channels.values()),
            "programs": area_programs,
        }
        output = args.out_dir / str(area["id"])
        output.mkdir(parents=True, exist_ok=True)
        (output / "epg.hdpk").write_bytes(
            make_epg(area_document, area_channels, global_keys)
        )
        (output / "string.hdpk").write_bytes(make_string(area_document, area_channels))
        print(
            f"area {area['id']}: stations={len(area_channels)} "
            f"programs={len(area_programs)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
