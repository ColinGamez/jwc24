from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Correct the HBNJ native preflight status word.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--raw-destination",
        type=Path,
        help="also write the corrected raw HDPK payload without its four-byte WC24 length prefix",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    destination = args.destination.resolve()
    if source == destination:
        raise SystemExit("destination must differ so the original fixture remains preserved")
    data = bytearray(source.read_bytes())
    if len(data) < 0x28 or data[4:12] != b"HDPK001B":
        raise SystemExit("source is not a length-prefixed HDPK001B object")
    declared = int.from_bytes(data[0:4], "big")
    if declared != len(data) - 4:
        raise SystemExit(f"invalid length prefix: {declared} != {len(data) - 4}")
    reserved_before = int.from_bytes(data[0x20:0x24], "big")
    status_before = int.from_bytes(data[0x24:0x28], "big")
    if reserved_before not in {0, 1} or status_before not in {0, 1}:
        raise SystemExit(
            f"unexpected reserved/status words: reserved={reserved_before}, status={status_before}"
        )
    # The native response is the raw HDPK (the wrapper is only retained as a
    # source fixture). Its preflight word is raw byte 0x20, or wrapped byte
    # 0x24. Raw byte 0x1c remains the outer HDPK reserved word.
    data[0x20:0x24] = (0).to_bytes(4, "big")
    data[0x24:0x28] = (1).to_bytes(4, "big")
    old_root_name = b"icitSingleton.h\0"
    if not data.endswith(old_root_name):
        raise SystemExit("unexpected HDPK root name")
    data[-len(old_root_name) :] = b"main\0".ljust(len(old_root_name), b"\0")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    verify = destination.read_bytes()
    if (
        int.from_bytes(verify[0x20:0x24], "big") != 0
        or int.from_bytes(verify[0x24:0x28], "big") != 1
    ):
        raise SystemExit("post-write verification failed")
    print(f"source:       {source}")
    print(f"source hash:  {digest(source.read_bytes())}")
    print(f"corrected:    {destination}")
    print(f"corrected hash:{digest(verify)}")
    print(f"reserved word:{reserved_before} -> 0")
    print(f"status word:  {status_before} -> 1")
    print("root name:    icitSingleton.h -> main")
    if args.raw_destination:
        raw_destination = args.raw_destination.resolve()
        if raw_destination in {source, destination}:
            raise SystemExit("raw destination must differ from the source and corrected wrapped fixture")
        raw_destination.parent.mkdir(parents=True, exist_ok=True)
        raw_destination.write_bytes(verify[4:])
        raw_verify = raw_destination.read_bytes()
        if raw_verify[:8] != b"HDPK001B" or len(raw_verify) != declared:
            raise SystemExit("raw payload post-write verification failed")
        print(f"raw payload:  {raw_destination}")
        print(f"raw hash:     {digest(raw_verify)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
