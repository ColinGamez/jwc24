#!/usr/bin/env python3
"""Patch a private Wii no Ma LZ11 executable to a replacement bootstrap root."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from jwc24.lz11 import decode_lz11, encode_lz11


REFERENCE_URLS = (
    b"https://wmp2v3.wapp.wii.com/conf/first.bin",
    b"http://prod.wiilink24.com/conf/first.bin",
    b"http://192.168.2.17///////conf/first.bin",
    b"http://192.168.2.17/////////conf/first.bin",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_app", type=Path)
    parser.add_argument("output_app", type=Path)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    if args.output_app.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_app}")
    suffix = b"/conf/first.bin"
    base = args.base_url.rstrip("/").encode("ascii")
    raw = decode_lz11(args.input_app.read_bytes())
    matches = [url for url in REFERENCE_URLS if raw.count(url) == 1]
    if len(matches) != 1:
        parser.error("expected exactly one known stock or legacy bootstrap URL")
    reference_url = matches[0]
    padding = len(reference_url) - len(base) - len(suffix)
    if padding < 1:
        parser.error("base URL is too long for the fixed bootstrap field")
    replacement = base + b"/" * padding + suffix
    patched = raw.replace(reference_url, replacement)
    compressed = encode_lz11(patched)
    if decode_lz11(compressed) != patched:
        raise ValueError("LZ11 round-trip verification failed")
    args.output_app.parent.mkdir(parents=True, exist_ok=True)
    args.output_app.write_bytes(compressed)
    print(f"source bootstrap: {reference_url.decode('ascii')}")
    print(f"bootstrap: {replacement.decode('ascii')}")
    print(f"wrote {args.output_app} ({len(compressed)} bytes)")
    print(f"SHA-256 {hashlib.sha256(compressed).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
