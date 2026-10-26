from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(WORKSPACE))
from jwc24.hbnj_publication import MAX_FILE_BYTES, publish_hbnj_snapshot

PRIVATE = WORKSPACE / "channels" / "hbnj" / "private"
CURRENT = WORKSPACE / "channels" / "hbnj" / "generated" / "current"
SNAPSHOTS = WORKSPACE / "channels" / "hbnj" / "generated" / "snapshots"
JAPAN_STANDARD_TIME = timezone(timedelta(hours=9), name="JST")


def run(*arguments: str) -> None:
    command = [sys.executable, *arguments]
    environment = os.environ.copy()
    # Windows may otherwise inherit a legacy console code page that cannot
    # print Japanese area names and aborts an otherwise valid collection.
    environment.setdefault("PYTHONUTF8", "1")
    environment['PYTHONPATH'] = str(WORKSPACE)
    result = subprocess.run(
        command,
        cwd=WORKSPACE,
        check=False,
        env=environment,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"HBNJ build stage failed ({result.returncode})")


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build HBNJ guide files; coherent snapshots are opt-in.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--legacy', action='store_true',
                      help='Keep the existing per-file publication experiment (default)')
    mode.add_argument('--coherent', action='store_true',
                      help='Publish one immutable snapshot with explicit source review/age policy')
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
    parser.add_argument("--guide-file", type=Path,
                        help="Build from an explicit normalized local guide; no collection")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--rights-ref",
                        help="Private reference to the source/usage review; not proof of rights")
    parser.add_argument("--max-collection-age-seconds", type=int,
                        help="Explicit local source collection-age policy")
    args = parser.parse_args(argv)
    if args.coherent:
        if args.max_collection_age_seconds is None or not 1 <= args.max_collection_age_seconds <= 7 * 86400:
            parser.error('--coherent requires --max-collection-age-seconds in 1..604800')
        if (args.rights_ref is None or not args.rights_ref.strip() or len(args.rights_ref) > 2048
                or any(ord(char) < 32 or ord(char) == 127 for char in args.rights_ref)):
            parser.error('--coherent requires a bounded nonempty --rights-ref')
    elif any(value is not None for value in (args.rights_ref, args.max_collection_age_seconds, args.output_root)):
        parser.error('Snapshot evidence/options require explicit --coherent mode')
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
        if args.guide_file is None:
            run(
                "tools/collect_hbnj_all.py", "--date", broadcast_date,
                "--out", str(guide), "--delay", str(args.delay),
                "--days", str(args.days), "--retries", str(args.retries),
                "--retry-delay", str(args.retry_delay),
            )
        else:
            if not 0 < args.guide_file.stat().st_size <= MAX_FILE_BYTES:
                raise ValueError('Explicit guide exceeds local byte bounds')
            shutil.copyfile(args.guide_file, guide)
        run("tools/validate_hbnj_guide.py", str(guide))
        run("tools/pack_hbnj_guide.py", str(guide), "--out-dir", str(payloads))
        run(
            "tools/build_hbnj_area_payloads.py",
            str(guide),
            "--out-dir",
            str(payloads / "areas"),
        )
        if args.coherent:
            # The snapshot component validates the exact copied national and
            # regional files before switching its one immutable-generation pointer.
            report = publish_hbnj_snapshot(
                guide, payloads, args.output_root or SNAPSHOTS, rights_ref=args.rights_ref,
                max_collection_age_seconds=args.max_collection_age_seconds,
            )
        else:
            # Preserve the existing experiment and scheduled caller. These are
            # individual file replacements, not an atomic whole-guide switch.
            run('tools/validate_hbnj_payloads.py', str(guide), str(payloads))
            run('tools/validate_hbnj_area_payloads.py', str(guide), str(payloads / 'areas'))
            publish(guide, PRIVATE / f'jwc24-all-{broadcast_date}.json')
            for filename in ('epg.hdpk', 'string.hdpk', 'header.hdpk'):
                publish(payloads / filename, CURRENT / filename)
            for area in sorted((payloads / 'areas').iterdir()):
                for filename in ('epg.hdpk', 'string.hdpk'):
                    publish(area / filename, CURRENT / 'areas' / area.name / filename)
            report = {'mode': 'legacy_per_file_experiment', 'areas': 54,
                      'coherent_generation_published': False,
                      'source_age_policy_checked': False,
                      'source_rights_independently_verified': False,
                      'native_delivery_verified': False}
    import json
    print(json.dumps(report, sort_keys=True))
    if args.coherent:
        print('HBNJ immutable generation prepared; explicit snapshot activation is required.')
    else:
        print('HBNJ legacy files updated individually; whole-guide atomicity is unverified.')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
