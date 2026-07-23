from __future__ import annotations

import argparse
import json
import struct
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


MOJIBAKE_MARKERS = ("Ã", "Â", "â", "å", "æ", "ç", "ã", "ï", "ð", "�")


def has_mojibake(value: object) -> bool:
    return isinstance(value, str) and any(marker in value for marker in MOJIBAKE_MARKERS)


def root_names(path: Path) -> list[str]:
    raw = path.read_bytes()
    if raw[:8] != b"HDPK001B":
        return ["<not-raw-hdpk>"]
    data_length = struct.unpack_from(">I", raw, 0x0C)[0]
    relocations = struct.unpack_from(">I", raw, 0x10)[0]
    roots = struct.unpack_from(">I", raw, 0x14)[0]
    names_size = struct.unpack_from(">I", raw, 0x18)[0]
    root_base = 0x20 + ((data_length + 3) & ~3) + relocations * 4
    names_base = root_base + roots * 8
    result = []
    for index in range(roots):
        name_offset = struct.unpack_from(">I", raw, root_base + index * 8 + 4)[0]
        start = names_base + name_offset
        end = raw.find(b"\0", start, names_base + names_size)
        result.append(raw[start:end].decode("ascii", errors="replace"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a legacy TV no Tomo guide export.")
    parser.add_argument("guide", type=Path)
    parser.add_argument("--payload-dir", type=Path)
    args = parser.parse_args()

    guide = json.loads(args.guide.read_text(encoding="utf-8"))
    areas = guide.get("areas", [])
    channels = guide.get("channels", [])
    programs = guide.get("programs", [])
    channel_ids = [int(item["id"]) for item in channels]
    program_ids = [int(item["id"]) for item in programs]
    known_channels = set(channel_ids)
    referenced_channels = {int(item["channel_id"]) for item in programs}
    area_channels = [
        int(channel_id)
        for area in areas
        for channel_id in area.get("channel_ids", [])
    ]

    mojibake_areas = [item.get("name") for item in areas if has_mojibake(item.get("name"))]
    mojibake_channels = [item.get("name") for item in channels if has_mojibake(item.get("name"))]
    mojibake_titles = [item.get("title") for item in programs if has_mojibake(item.get("title"))]
    dates = Counter(str(item.get("date", "")) for item in programs)
    invalid_windows = 0
    invalid_examples: list[tuple[object, ...]] = []
    overlaps = 0
    overlap_examples: list[tuple[object, ...]] = []
    by_channel: dict[int, list[tuple[datetime, datetime, dict[str, object]]]] = defaultdict(list)
    for item in programs:
        try:
            start = datetime.fromisoformat(f"{item['date']}T{item['start']}")
            end = datetime.fromisoformat(f"{item['date']}T{item['end']}")
        except (KeyError, TypeError, ValueError):
            invalid_windows += 1
            if len(invalid_examples) < 3:
                invalid_examples.append((item.get("channel_name"), item.get("date"), item.get("start"), item.get("end"), item.get("title")))
            continue
        if end <= start:
            invalid_windows += 1
            if len(invalid_examples) < 3:
                invalid_examples.append((item.get("channel_name"), item.get("date"), item.get("start"), item.get("end"), item.get("title")))
            continue
        by_channel[int(item["channel_id"])].append((start, end, item))
    for channel_id, windows in by_channel.items():
        windows.sort(key=lambda window: (window[0], window[1]))
        for previous, current in zip(windows, windows[1:]):
            if current[0] < previous[1]:
                overlaps += 1
                if len(overlap_examples) < 3:
                    overlap_examples.append(
                        (
                            channel_id,
                            previous[0].isoformat(),
                            previous[1].isoformat(),
                            previous[2].get("title"),
                            current[0].isoformat(),
                            current[1].isoformat(),
                            current[2].get("title"),
                        )
                    )

    print(f"guide={args.guide}")
    print(f"declared_date={guide.get('date')!r} source={guide.get('source')!r}")
    print(f"areas={len(areas)} channels={len(channels)} programs={len(programs)}")
    print(f"program_dates={dict(dates)}")
    print(
        "duplicate_ids: "
        f"channels={len(channel_ids) - len(set(channel_ids))} "
        f"programs={len(program_ids) - len(set(program_ids))}"
    )
    print(
        "references: "
        f"program_missing_channels={len(referenced_channels - known_channels)} "
        f"area_missing_channels={len(set(area_channels) - known_channels)} "
        f"channels_without_programs={len(known_channels - referenced_channels)}"
    )
    print(
        "encoding: "
        f"mojibake_areas={len(mojibake_areas)} "
        f"mojibake_channels={len(mojibake_channels)} "
        f"mojibake_titles={len(mojibake_titles)}"
    )
    print(f"schedule_windows: invalid={invalid_windows} overlaps={overlaps}")
    if invalid_examples:
        print(f"invalid_window_examples={invalid_examples!r}")
    if overlap_examples:
        print(f"overlap_examples={overlap_examples!r}")
    if mojibake_areas:
        print(f"mojibake_area_example={mojibake_areas[0]!r}")
    if mojibake_channels:
        print(f"mojibake_channel_example={mojibake_channels[0]!r}")
    if mojibake_titles:
        print(f"mojibake_title_example={mojibake_titles[0]!r}")

    if args.payload_dir:
        for filename in ("header.bin.payload", "epg.bin.payload", "str.bin.payload"):
            path = args.payload_dir / filename
            print(f"{filename}: size={path.stat().st_size} roots={root_names(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
