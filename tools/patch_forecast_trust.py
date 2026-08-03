#!/usr/bin/env python3
"""Patch a working copy of the Japanese Forecast Channel to trust JWC24.

This intentionally changes only the RSA trust path. It does not alter the
channel's download URLs or disable signature verification.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import subprocess
from pathlib import Path


STOCK_SHA256 = "ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5"
NEW_SECTION_FILE_OFFSET = 0x1D61A0
NEW_SECTION_ADDRESS = 0x80001820
VERIFY_CALL_FILE_OFFSET = 0x112A58
VERIFY_BRANCH = bytes.fromhex("4b ee a3 e8")
URL_HOST_OFFSETS = (0x194EA7, 0x194EDB)
STOCK_HOST = b"weather.wapp.wii.com"

# PowerPC helper which retains RSA verification while supplying a replacement
# 2048-bit modulus. The 256-byte modulus follows this code in the new section.
VERIFY_HELPER = bytes.fromhex(
    "38000100b00300004e800020542b06fe216bfe207c2c0b787c21596e7c0802a6"
    "900c000493ecfffc38a100bc3c608000386319043883fffc380000207c0903a6"
    "806400048404000890650004940500084200fff03881001c3860000038000011"
    "7c0903a690640004946400084200fff8906400043c60800038631a043880003f"
    "5484063e38a0000054a5063e4811117d3c60800038631a043881002038a00002"
    "54a5063e481122757c7f1b782c1f00004082001c38610020388100c038a00100"
    "4811159138610020481124d18141000083eafffc800a00047c0803a67d415378"
    "4e800020"
)
KEY_LABEL = b"wc24pubk.mod\0"


def _public_modulus(public_key: Path) -> bytes:
    result = subprocess.run(
        ["openssl", "rsa", "-pubin", "-in", str(public_key), "-modulus", "-noout"],
        check=True,
        capture_output=True,
        text=True,
    )
    prefix = "Modulus="
    line = result.stdout.strip()
    if not line.startswith(prefix):
        raise ValueError("OpenSSL did not return an RSA modulus")
    modulus = bytes.fromhex(line[len(prefix) :])
    if len(modulus) != 256:
        raise ValueError(f"expected a 2048-bit RSA key, got {len(modulus) * 8} bits")
    return modulus


def patch_trust(stock: bytes, modulus: bytes, host: str | None = None) -> bytes:
    digest = hashlib.sha256(stock).hexdigest()
    if digest != STOCK_SHA256:
        raise ValueError(
            "input is not the supported Japanese Forecast Channel v7 main content "
            f"(SHA-256 {digest})"
        )
    if len(stock) != NEW_SECTION_FILE_OFFSET:
        raise ValueError("unexpected stock DOL length")

    patched = bytearray(stock)
    # DOL data section slot 10: file offset, load address, declared size.
    struct.pack_into(">I", patched, 0x44, NEW_SECTION_FILE_OFFSET)
    struct.pack_into(">I", patched, 0x8C, NEW_SECTION_ADDRESS)
    section = VERIFY_HELPER + modulus + KEY_LABEL
    section += b"\0" * ((4 - len(section) % 4) % 4)
    struct.pack_into(">I", patched, 0xD4, len(section))
    patched[VERIFY_CALL_FILE_OFFSET : VERIFY_CALL_FILE_OFFSET + 4] = VERIFY_BRANCH
    if host:
        encoded_host = host.encode("ascii")
        if len(encoded_host) > len(STOCK_HOST):
            raise ValueError(f"host must be at most {len(STOCK_HOST)} ASCII bytes")
        replacement = encoded_host + b"/" * (len(STOCK_HOST) - len(encoded_host))
        for offset in URL_HOST_OFFSETS:
            if stock[offset : offset + len(STOCK_HOST)] != STOCK_HOST:
                raise ValueError(f"stock URL host is missing at 0x{offset:x}")
            patched[offset : offset + len(STOCK_HOST)] = replacement
    patched.extend(section)
    return bytes(patched)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_app", type=Path)
    parser.add_argument("public_key", type=Path)
    parser.add_argument("output_app", type=Path)
    parser.add_argument(
        "--host",
        help="embed an HTTP host (short values are slash-padded inside the URL)",
    )
    args = parser.parse_args()

    if args.output_app.exists():
        parser.error(f"refusing to overwrite existing output: {args.output_app}")
    output = patch_trust(
        args.stock_app.read_bytes(), _public_modulus(args.public_key), args.host
    )
    args.output_app.parent.mkdir(parents=True, exist_ok=True)
    args.output_app.write_bytes(output)
    print(f"wrote {args.output_app} ({len(output)} bytes)")
    print(f"SHA-256 {hashlib.sha256(output).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
