from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from collect_hbnj_region import atomic_json, fetch, parse_region
from jwc24.hbnj_regions import PREFECTURES, broadcast_area_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect all 54 HBNJ broadcast areas strictly.")
    parser.add_argument("--date", required=True, help="Broadcast date in YYYYMMDD form")
    parser.add_argument("--out", type=Path, required=True)
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
    if args.retries < 1:
        raise SystemExit("--retries must be at least 1")
    if args.retry_delay < 0:
        raise SystemExit("--retry-delay cannot be negative")

    areas: list[dict[str, object]] = []
    channels: list[dict[str, object]] = []
    programs: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    area_id = 1001
    for prefecture_raw, prefecture_name, regions in PREFECTURES:
        for group_id, region_name in regions:
            area_name = region_name if len(regions) > 1 else prefecture_name
            print(
                f"[{area_id - 1000:02d}/{broadcast_area_count()}] "
                f"group={group_id} area={area_name}",
                flush=True,
            )
            for attempt in range(1, args.retries + 1):
                try:
                    source_url, source = fetch(group_id, args.date)
                    region = parse_region(
                        source,
                        group_id=group_id,
                        area_id=area_id,
                        area_name=area_name,
                        prefecture_raw=prefecture_raw,
                        source_url=source_url,
                    )
                    break
                except Exception as error:
                    if attempt == args.retries:
                        raise
                    wait = args.retry_delay * (2 ** (attempt - 1))
                    print(
                        f"  attempt {attempt}/{args.retries} failed: "
                        f"{type(error).__name__}: {error}; retrying in {wait:g}s",
                        file=sys.stderr,
                        flush=True,
                    )
                    if wait:
                        time.sleep(wait)
            area = dict(region["area"])
            areas.append(area)
            channels.extend(region["channels"])
            programs.extend(region["programs"])
            sources.append(
                {
                    "area_id": area_id,
                    "group_id": group_id,
                    "source_url": source_url,
                    "channels": len(region["channels"]),
                    "programs": len(region["programs"]),
                }
            )
            area_id += 1
            if args.delay:
                time.sleep(args.delay)

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
