"""Create a private HCHJ v512 DOL for loopback-only area fixture experiments.

Does not install/launch a title. Only the known executable fingerprint is accepted.
Other channel endpoints and untraced requests are not made compatible.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.asset_publication import atomic_write

SOURCE_SHA256 = '6b9002431aec265e34ba532aae2707ef74a5b8c491f81be624a54563eabc88c9'


def patch_dol(data, *, include_auth=False, all_api_http=False):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unknown executable fingerprint')
    result = bytearray(data)
    offsets = struct.unpack_from('>18I', data, 0)
    addresses = struct.unpack_from('>18I', data, 0x48)
    sizes = struct.unpack_from('>18I', data, 0x90)
    instruction_addresses = (0x800f90c0, 0x800f91b8)
    if include_auth:
        instruction_addresses += (0x80077c14,)
    for address in instruction_addresses:
        matches = [offset + address - base for offset, base, size in zip(offsets, addresses, sizes)
                   if base <= address and address + 4 <= base + size]
        if len(matches) != 1:
            raise ValueError('Ambiguous instruction location')
        offset = matches[0]
        if data[offset:offset+4] != bytes.fromhex('39000001'):
            raise ValueError('Unexpected scheme instruction')
        result[offset:offset+4] = bytes.fromhex('39000000')
    if all_api_http:
        for address, expected, replacement in (
                (0x8002c298, '7d1c4378', '3b800000'),
                (0x8002c6d4, '7d134378', '3a600000')):
            matches = [offset + address - base for offset, base, size in zip(offsets, addresses, sizes)
                       if base <= address and address + 4 <= base + size]
            if len(matches) != 1 or data[matches[0]:matches[0]+4] != bytes.fromhex(expected):
                raise ValueError('Unexpected common API scheme selector')
            result[matches[0]:matches[0]+4] = bytes.fromhex(replacement)
    for suffix in (b'/nwapi.php?action=', b'/nwapi.php'):
        original = b'nwapi.demae-can.com' + suffix + b'\0'
        replacement = b'127.0.0.1:18085' + suffix + b'\0'
        if data.count(original) != 1 or len(replacement) > len(original):
            raise ValueError('Unexpected endpoint field')
        offset = data.index(original)
        result[offset:offset+len(original)] = replacement.ljust(len(original), b'\0')
    if len(result) != len(data):
        raise ValueError('Executable size changed')
    return bytes(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--include-auth', action='store_true', help='Also redirect the traced auth-key wrapper to HTTP')
    parser.add_argument('--all-api-http', action='store_true', help='Force local API GET/POST builders to HTTP; image hosts unchanged')
    args = parser.parse_args(argv)
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output.resolve().is_relative_to(private.resolve()) or args.output.exists():
        parser.error('Output must be a new file inside private/')
    try:
        patched = patch_dol(args.source.read_bytes(), include_auth=args.include_auth, all_api_http=args.all_api_http)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(args.output, patched)
    except (OSError, ValueError):
        print('Patch rejected; source and installed titles untouched', file=sys.stderr)
        return 1
    print('Prepared private loopback test DOL; not installed or launched')
    print('SHA-256 ' + hashlib.sha256(patched).hexdigest())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
