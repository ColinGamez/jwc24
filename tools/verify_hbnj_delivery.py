from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

from jwc24.server import _aes_ofb


def decode_lz10(payload: bytes) -> bytes:
    if len(payload) < 4 or payload[0] != 0x10:
        raise ValueError("response is not Nintendo LZ10")
    expected = int.from_bytes(payload[1:4], "little")
    source = 4
    output = bytearray()
    while len(output) < expected:
        flags = payload[source]
        source += 1
        for bit in range(7, -1, -1):
            if len(output) >= expected:
                break
            if flags & (1 << bit):
                pair = int.from_bytes(payload[source:source + 2], "big")
                source += 2
                length = (pair >> 12) + 3
                distance = (pair & 0xFFF) + 1
                for _ in range(length):
                    output.append(output[-distance])
            else:
                output.append(payload[source])
                source += 1
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a live HBNJ WC24 delivery end to end.")
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("pairs", nargs="+", help="route=expected-payload")
    args = parser.parse_args()
    key_blob = args.key_file.read_bytes()
    if len(key_blob) != 544:
        raise ValueError("unexpected wc24pubk.mod size")
    key = key_blob[512:528]
    for pair in args.pairs:
        route, expected_path = pair.split("=", 1)
        with urlopen(args.base_url.rstrip("/") + route, timeout=30) as response:
            envelope = response.read()
        if len(envelope) < 320 or envelope[:4] != b"Wc24":
            raise ValueError(f"{route}: missing WC24 envelope")
        iv = envelope[48:64]
        compressed = _aes_ofb(envelope[320:], key, iv, decrypt=True)
        actual = decode_lz10(compressed)
        expected = Path(expected_path).read_bytes()
        if actual != expected:
            raise ValueError(f"{route}: delivered payload differs from {expected_path}")
        print(
            f"{route}: ok envelope={len(envelope)} lz10={len(compressed)} "
            f"hdpk={len(actual)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
