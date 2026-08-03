#!/usr/bin/env python3
"""Build the encrypted Wii no Ma v1025 first.bin bootstrap response."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def config_xml(base_url: str, updated: str) -> bytes:
    base = base_url.rstrip("/")
    root = ET.Element("Config")
    values = (
        # This JWC24 WAD retains the stock v1025 client's version checks. The
        # 9998 value used by separately version-patched clients triggers the
        # stock channel's Wii Shop update screen (354607).
        ("ver", "399"),
        ("maint", "0"),
        ("url1", f"{base}/url1/"),
        ("url2", f"{base}/url2/"),
        ("url3", f"{base}/url3/"),
        ("eulaver", "3"),
        ("shopurl", f"{base}/shop/index.esf"),
        ("shopkey", "7fce738e542f0a60fe5d8d8e1e8781af"),
        ("shopvalid", "1"),
        ("akahost", "5"),
        ("akaca", "1"),
        ("smpkey", "5ab362aa57dbb1dc16849e3e2d1cf2ff"),
        ("fmax", "30"),
        ("bmax", "10"),
        ("upddt", updated),
    )
    for name, value in values:
        ET.SubElement(root, name).text = value
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8") + b"\n"


def encrypt_cbc(payload: bytes, key: bytes, iv: bytes) -> bytes:
    padding = 16 - len(payload) % 16
    padded = payload + bytes((padding,)) * padding
    try:
        from Crypto.Cipher import AES
    except ModuleNotFoundError:
        openssl = shutil.which("openssl")
        if not openssl:
            raise RuntimeError("AES-CBC requires pycryptodome or OpenSSL")
        result = subprocess.run(
            [openssl, "enc", "-aes-128-cbc", "-K", key.hex(), "-iv", iv.hex(), "-nopad"],
            input=padded,
            capture_output=True,
            check=True,
        )
        return result.stdout
    return AES.new(key, AES.MODE_CBC, iv=iv).encrypt(padded)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", type=Path)
    parser.add_argument("iv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--updated")
    args = parser.parse_args()
    key, iv = args.key.read_bytes(), args.iv.read_bytes()
    if len(key) != 16 or len(iv) != 16:
        parser.error("key and IV must each contain exactly 16 bytes")
    updated = args.updated or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    xml = config_xml(args.base_url, updated)
    encrypted = encrypt_cbc(xml, key, iv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encrypted)
    print(f"wrote {args.output} ({len(encrypted)} bytes; {len(xml)} XML bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
