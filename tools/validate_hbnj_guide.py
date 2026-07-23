from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a JWC24 HBNJ guide JSON.")
    parser.add_argument("guide", type=Path)
    args = parser.parse_args()

    raw = args.guide.read_bytes()
    document = json.loads(raw.decode("utf-8", errors="strict"))
    if document.get("format") != "jwc24_hbnj_guide_v1":
        fail("unexpected guide format")
    if document.get("status") != "ok":
        fail("guide status is not ok")

    areas = document.get("areas")
    channels = document.get("channels")
    programs = document.get("programs")
    sources = document.get("sources")
    if not all(isinstance(value, list) for value in (areas, channels, programs, sources)):
        fail("areas, channels, programs, and sources must be arrays")
    if len(areas) != 54 or len(sources) != 54:
        fail(f"expected 54 areas and sources, got {len(areas)} and {len(sources)}")

    area_ids = [area["id"] for area in areas]
    channel_ids = [channel["id"] for channel in channels]
    program_ids = [program["id"] for program in programs]
    for label, values in (
        ("area", area_ids),
        ("channel", channel_ids),
        ("program", program_ids),
    ):
        duplicates = [value for value, count in Counter(values).items() if count > 1]
        if duplicates:
            fail(f"duplicate {label} IDs: {duplicates[:5]}")

    channel_by_id = {channel["id"]: channel for channel in channels}
    claimed_channels: list[int] = []
    for area in areas:
        if not area["channel_ids"]:
            fail(f"area {area['id']} has no channels")
        claimed_channels.extend(area["channel_ids"])
        missing = set(area["channel_ids"]) - channel_by_id.keys()
        if missing:
            fail(f"area {area['id']} references missing channels: {sorted(missing)}")
    if Counter(claimed_channels) != Counter(channel_ids):
        fail("area channel lists do not partition the channel table exactly")

    programs_by_channel: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
    cross_midnight = 0
    for program in programs:
        channel_id = program["channel_id"]
        if channel_id not in channel_by_id:
            fail(f"program {program['id']} references missing channel {channel_id}")
        start = datetime.fromisoformat(program["start"])
        end = datetime.fromisoformat(program["end"])
        if end <= start:
            fail(f"program {program['id']} has a non-positive window")
        if end.date() != start.date():
            cross_midnight += 1
        programs_by_channel[channel_id].append((start, end))

    empty_channels = set(channel_ids) - programs_by_channel.keys()
    if empty_channels:
        fail(f"channels without programs: {sorted(empty_channels)[:5]}")
    for channel_id, windows in programs_by_channel.items():
        windows.sort()
        for previous, current in zip(windows, windows[1:]):
            if current[0] < previous[1]:
                fail(
                    f"channel {channel_id} overlaps: "
                    f"{previous[0].isoformat()}..{previous[1].isoformat()} and "
                    f"{current[0].isoformat()}..{current[1].isoformat()}"
                )

    serialized = json.dumps(document, ensure_ascii=False)
    if "\ufffd" in serialized:
        fail("Unicode replacement character found")
    suspicious = {marker: serialized.count(marker) for marker in ("Ã", "â€", "æœ")}
    suspicious = {marker: count for marker, count in suspicious.items() if count}
    if suspicious:
        fail(f"possible mojibake markers found: {suspicious}")

    source_channel_total = sum(source["channels"] for source in sources)
    source_program_total = sum(source["programs"] for source in sources)
    if source_channel_total != len(channels) or source_program_total != len(programs):
        fail("source totals do not match the aggregate tables")

    duplicate_names = sum(
        count - 1 for count in Counter(channel["name"] for channel in channels).values()
        if count > 1
    )
    print(
        f"valid: areas={len(areas)} channels={len(channels)} "
        f"programs={len(programs)} cross_midnight={cross_midnight} "
        f"repeated_names_across_areas={duplicate_names}"
    )
    print(f"sha256={hashlib.sha256(raw).hexdigest().upper()} bytes={len(raw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
