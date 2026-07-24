from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
PRIVATE = WORKSPACE / "channels" / "hbnj" / "private"
CURRENT = WORKSPACE / "channels" / "hbnj" / "generated" / "current"
JAPAN_STANDARD_TIME = timezone(timedelta(hours=9), name="JST")


def run(*arguments: str) -> None:
    command = [sys.executable, *arguments]
    environment = os.environ.copy()
    # Windows may otherwise inherit a legacy console code page that cannot
    # print Japanese area names and aborts an otherwise valid collection.
    environment.setdefault("PYTHONUTF8", "1")
    result = subprocess.run(
        command,
        cwd=WORKSPACE,
        check=False,
        env=environment,
    )
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}")


def publish(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=destination.name + ".",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        shutil.copyfile(source, temporary_path)
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and atomically publish today's HBNJ guide.")
    parser.add_argument(
        "--date",
        help="Broadcast date in YYYYMMDD form (default: current date in Japan)",
    )
    # Eight days across 54 areas is 432 requests. A short courtesy delay keeps
    # the scheduled build comfortably inside its 20-minute execution window.
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--days", type=int, default=8)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=1.0)
    args = parser.parse_args()
    # Japan has observed UTC+09:00 year-round since 1951, so this avoids an
    # unnecessary dependency on the optional Windows IANA/tzdata package.
    broadcast_date = args.date or datetime.now(JAPAN_STANDARD_TIME).strftime("%Y%m%d")
    if len(broadcast_date) != 8 or not broadcast_date.isdigit():
        raise SystemExit("--date must use YYYYMMDD")

    PRIVATE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hbnj-update-", dir=PRIVATE) as temporary:
        staging = Path(temporary)
        guide = staging / f"jwc24-all-{broadcast_date}.json"
        payloads = staging / "payloads"
        run(
            "tools/collect_hbnj_all.py",
            "--date",
            broadcast_date,
            "--out",
            str(guide),
            "--delay",
            str(args.delay),
            "--days",
            str(args.days),
            "--retries",
            str(args.retries),
            "--retry-delay",
            str(args.retry_delay),
        )
        run("tools/validate_hbnj_guide.py", str(guide))
        run("tools/pack_hbnj_guide.py", str(guide), "--out-dir", str(payloads))
        run("tools/validate_hbnj_payloads.py", str(guide), str(payloads))
        run(
            "tools/build_hbnj_area_payloads.py",
            str(guide),
            "--out-dir",
            str(payloads / "areas"),
        )
        run(
            "tools/validate_hbnj_area_payloads.py",
            str(guide),
            str(payloads / "areas"),
        )

        archive = PRIVATE / f"jwc24-all-{broadcast_date}.json"
        publish(guide, archive)
        for filename in ("epg.hdpk", "string.hdpk"):
            publish(payloads / filename, CURRENT / filename)
        # Header data changes only when station/area metadata changes, but
        # publishing it alongside a fully validated guide keeps rebuilds reproducible.
        publish(payloads / "header.hdpk", CURRENT / "header.hdpk")
        for area in sorted((payloads / "areas").iterdir()):
            for filename in ("epg.hdpk", "string.hdpk"):
                publish(area / filename, CURRENT / "areas" / area.name / filename)

    for path in (CURRENT / "header.hdpk", CURRENT / "epg.hdpk", CURRENT / "string.hdpk"):
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        print(f"published {path.relative_to(WORKSPACE)} sha256={digest}")
    print(f"HBNJ daily update complete for {broadcast_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
