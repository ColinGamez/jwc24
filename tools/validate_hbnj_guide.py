from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
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
    days = document.get("days", 1)
    if not isinstance(days, int) or not 1 <= days <= 8:
        fail(f"guide days must be between 1 and 8, got {days!r}")
    try:
        first_broadcast_date = datetime.strptime(document["broadcast_date"], "%Y%m%d")
    except (KeyError, TypeError, ValueError) as error:
        fail(f"invalid broadcast_date: {error}")
    broadcast_dates = {
        (first_broadcast_date + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(days)
    }
    expected_end_date = (first_broadcast_date + timedelta(days=days - 1)).strftime("%Y%m%d")
    if document.get("broadcast_end_date", document["broadcast_date"]) != expected_end_date:
        fail("broadcast_end_date does not match the requested guide window")

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
    dates_by_channel: dict[int, set[str]] = defaultdict(set)
    cross_midnight = 0
    genre_counts: Counter[int] = Counter()
    descriptions = 0
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
        genre_id = program.get("genre_id", 0)
        if not isinstance(genre_id, int) or not 0 <= genre_id <= 12:
            fail(f"program {program['id']} has invalid genre ID {genre_id!r}")
        genre_counts[genre_id] += 1
        description = program.get("description", "")
        if not isinstance(description, str):
            fail(f"program {program['id']} has a non-string description")
        for field_name, value in (("title", program["title"]), ("description", description)):
            supplementary = [character for character in value if ord(character) > 0xFFFF]
            if supplementary:
                codes = ", ".join(f"U+{ord(character):05X}" for character in supplementary[:3])
                fail(
                    f"program {program['id']} {field_name} contains "
                    f"Wii-unsupported supplementary characters: {codes}"
                )
        descriptions += bool(description)
        programs_by_channel[channel_id].append((start, end))
        dates_by_channel[channel_id].add(start.strftime("%Y%m%d"))

    empty_channels = set(channel_ids) - programs_by_channel.keys()
    if empty_channels:
        fail(f"channels without programs: {sorted(empty_channels)[:5]}")
    for channel_id, windows in programs_by_channel.items():
        missing_dates = broadcast_dates - dates_by_channel[channel_id]
        if missing_dates:
            fail(
                f"channel {channel_id} has no program starts on broadcast dates "
                f"{sorted(missing_dates)}"
            )
        if len(windows) > 768:
            fail(f"channel {channel_id} exceeds native 768-program capacity")
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
    if days > 1:
        expected_dates = sorted(broadcast_dates)
        for source in sources:
            if source.get("broadcast_dates") != expected_dates:
                fail(f"source {source.get('area_id')} has an incomplete date window")
            if len(source.get("source_urls", [])) != days:
                fail(f"source {source.get('area_id')} has incomplete source URLs")
            if len(source.get("daily_program_counts", [])) != days:
                fail(f"source {source.get('area_id')} has incomplete daily counts")

    duplicate_names = sum(
        count - 1 for count in Counter(channel["name"] for channel in channels).values()
        if count > 1
    )
    print(
        f"valid: days={days} areas={len(areas)} channels={len(channels)} "
        f"programs={len(programs)} cross_midnight={cross_midnight} "
        f"repeated_names_across_areas={duplicate_names} "
        f"descriptions={descriptions} genres={dict(sorted(genre_counts.items()))}"
    )
    print(f"sha256={hashlib.sha256(raw).hexdigest().upper()} bytes={len(raw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
