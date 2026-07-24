from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collect_hbnj_region import atomic_json, fetch, parse_region
from jwc24.hbnj_regions import PREFECTURES, broadcast_area_count


def merge_duplicate_program(
    previous: dict[str, object],
    current: dict[str, object],
) -> dict[str, object]:
    comparable_previous = {
        key: value for key, value in previous.items() if key != "source_program_id"
    }
    comparable_current = {
        key: value for key, value in current.items() if key != "source_program_id"
    }
    if comparable_previous != comparable_current:
        raise ValueError(f"program {current['id']} changed across broadcast pages")
    # Bangumi sometimes exposes the real program ID on one side of the 05:00
    # broadcast-day boundary and the placeholder -1 on the other.
    if previous.get("source_program_id") == "-1" and current.get("source_program_id") != "-1":
        return current
    return previous


def collect_with_retry(
    *,
    group_id: int,
    broadcast_date: str,
    area_id: int,
    area_name: str,
    prefecture_raw: int,
    retries: int,
    retry_delay: float,
) -> tuple[str, dict[str, object]]:
    for attempt in range(1, retries + 1):
        try:
            source_url, source = fetch(group_id, broadcast_date)
            return source_url, parse_region(
                source,
                group_id=group_id,
                area_id=area_id,
                area_name=area_name,
                prefecture_raw=prefecture_raw,
                source_url=source_url,
            )
        except Exception as error:
            if attempt == retries:
                raise
            wait = retry_delay * (2 ** (attempt - 1))
            print(
                f"  attempt {attempt}/{retries} failed: "
                f"{type(error).__name__}: {error}; retrying in {wait:g}s",
                file=sys.stderr,
                flush=True,
            )
            if wait:
                time.sleep(wait)
    raise AssertionError("retry loop ended without a result")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect all 54 HBNJ broadcast areas strictly.")
    parser.add_argument("--date", required=True, help="Broadcast date in YYYYMMDD form")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--days",
        type=int,
        default=8,
        help="Consecutive broadcast days to collect (TV no Tomo displays eight)",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between region requests")
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Attempts per region before failing the complete build",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.0,
        help="Initial retry delay in seconds (doubles after each failure)",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"\d{8}", args.date):
        raise SystemExit("--date must use YYYYMMDD")
    if args.delay < 0:
        raise SystemExit("--delay cannot be negative")
    if not 1 <= args.days <= 8:
        raise SystemExit("--days must be between 1 and 8")
    if args.retries < 1:
        raise SystemExit("--retries must be at least 1")
    if args.retry_delay < 0:
        raise SystemExit("--retry-delay cannot be negative")

    areas: list[dict[str, object]] = []
    channels: list[dict[str, object]] = []
    programs: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    first_date = datetime.strptime(args.date, "%Y%m%d")
    broadcast_dates = [
        (first_date + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(args.days)
    ]
    area_id = 1001
    for prefecture_raw, prefecture_name, regions in PREFECTURES:
        for group_id, region_name in regions:
            area_name = region_name if len(regions) > 1 else prefecture_name
            area: dict[str, object] | None = None
            canonical_channels: list[dict[str, object]] | None = None
            canonical_id_by_service: dict[str, int] = {}
            area_programs: dict[int, dict[str, object]] = {}
            source_urls: list[str] = []
            daily_program_counts: list[int] = []
            for day_number, broadcast_date in enumerate(broadcast_dates, start=1):
                print(
                    f"[{area_id - 1000:02d}/{broadcast_area_count()} "
                    f"day {day_number}/{args.days}] group={group_id} "
                    f"date={broadcast_date} area={area_name}",
                    flush=True,
                )
                source_url, region = collect_with_retry(
                    group_id=group_id,
                    broadcast_date=broadcast_date,
                    area_id=area_id,
                    area_name=area_name,
                    prefecture_raw=prefecture_raw,
                    retries=args.retries,
                    retry_delay=args.retry_delay,
                )
                region_channels = list(region["channels"])
                service_by_region_channel = {
                    int(channel["id"]): str(channel["service_id"])
                    for channel in region_channels
                }
                if canonical_channels is None:
                    area = dict(region["area"])
                    canonical_channels = region_channels
                    canonical_id_by_service = {
                        str(channel["service_id"]): int(channel["id"])
                        for channel in canonical_channels
                    }
                elif set(service_by_region_channel.values()) != set(canonical_id_by_service):
                    raise ValueError(
                        f"area {area_id} service lineup changed on {broadcast_date}"
                    )

                for program in region["programs"]:
                    normalized = dict(program)
                    service_id = service_by_region_channel[int(program["channel_id"])]
                    normalized["channel_id"] = canonical_id_by_service[service_id]
                    program_id = int(normalized["id"])
                    previous = area_programs.get(program_id)
                    area_programs[program_id] = (
                        normalized
                        if previous is None
                        else merge_duplicate_program(previous, normalized)
                    )
                source_urls.append(source_url)
                daily_program_counts.append(len(region["programs"]))
                if args.delay and not (
                    area_id == 1000 + broadcast_area_count()
                    and day_number == args.days
                ):
                    time.sleep(args.delay)

            assert area is not None and canonical_channels is not None
            merged_programs = sorted(
                area_programs.values(),
                key=lambda program: (
                    int(program["channel_id"]),
                    str(program["start"]),
                    int(program["id"]),
                ),
            )
            areas.append(area)
            channels.extend(canonical_channels)
            programs.extend(merged_programs)
            sources.append(
                {
                    "area_id": area_id,
                    "group_id": group_id,
                    "source_urls": source_urls,
                    "broadcast_dates": broadcast_dates,
                    "daily_program_counts": daily_program_counts,
                    "channels": len(canonical_channels),
                    "programs": len(merged_programs),
                }
            )
            area_id += 1

    channel_ids = [int(channel["id"]) for channel in channels]
    program_ids = [int(program["id"]) for program in programs]
    if len(set(channel_ids)) != len(channel_ids):
        raise ValueError("duplicate national channel IDs")
    if len(set(program_ids)) != len(program_ids):
        raise ValueError("duplicate national program IDs")
    if len(areas) != broadcast_area_count():
        raise ValueError("national area count changed unexpectedly")

    payload = {
        "status": "ok",
        "format": "jwc24_hbnj_guide_v1",
        "source": "bangumi.org",
        "broadcast_date": args.date,
        "broadcast_end_date": broadcast_dates[-1],
        "days": args.days,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "areas": areas,
        "channels": channels,
        "programs": programs,
        "sources": sources,
    }
    atomic_json(args.out, payload)
    print(
        f"wrote {args.out}: areas={len(areas)} channels={len(channels)} "
        f"programs={len(programs)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
