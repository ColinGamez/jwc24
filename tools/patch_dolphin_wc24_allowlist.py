from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
from pathlib import Path


# Dolphin 2606 contains the WC24 title allowlist as a contiguous u64 table.
# Replace PAL Region Select in the experimental build; stock Dolphin is kept.
REPLACED_TITLE = 0x0001000848414C50
HBNJ_TITLE = 0x0001000148424E4A


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a separate Dolphin build that allows HBNJ WC24 host patches."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    destination = args.destination.resolve()
    if source == destination:
        raise SystemExit("destination must differ from the stock Dolphin executable")
    data = bytearray(source.read_bytes())
    old = struct.pack("<Q", REPLACED_TITLE)
    new = struct.pack("<Q", HBNJ_TITLE)
    matches: list[int] = []
    cursor = 0
    while (offset := data.find(old, cursor)) >= 0:
        matches.append(offset)
        cursor = offset + len(old)
    if len(matches) != 1:
        raise SystemExit(f"expected one allowlist marker, found {len(matches)}")
    if data.count(new):
        raise SystemExit("source already contains HBNJ; refusing an ambiguous patch")

    offset = matches[0]
    data[offset : offset + 8] = new
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    shutil.copystat(source, destination)

    verify = destination.read_bytes()
    if verify[offset : offset + 8] != new or verify.count(new) != 1:
        raise SystemExit("post-write verification failed")
    print(f"source:      {source}")
    print(f"source hash: {sha256(source)}")
    print(f"patched:     {destination}")
    print(f"patched hash:{sha256(destination)}")
    print(f"offset:      0x{offset:X}")
    print(f"allowlist:   {REPLACED_TITLE:016X} -> {HBNJ_TITLE:016X}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
