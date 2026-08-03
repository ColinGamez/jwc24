#!/usr/bin/env python3
"""Sign an LZ10-compressed Forecast Channel payload with a private RSA key."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from jwc24.forecast import decode_lz10, sign_compressed_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compressed_payload", type=Path)
    parser.add_argument("private_key", type=Path)
    parser.add_argument("output_payload", type=Path)
    args = parser.parse_args()

    if args.output_payload.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_payload}")
    compressed = args.compressed_payload.read_bytes()
    decode_lz10(compressed)
    signed = sign_compressed_payload(compressed, args.private_key)
    args.output_payload.parent.mkdir(parents=True, exist_ok=True)
    args.output_payload.write_bytes(signed)
    print(f"wrote {args.output_payload} ({len(signed)} bytes)")
    print(f"SHA-256 {hashlib.sha256(signed).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
