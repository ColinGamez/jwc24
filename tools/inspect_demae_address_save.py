"""Inspect address-save metadata and native trace anchors, never personal fields.

This is not a save decoder, checksum validator or native acceptance test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

SOURCE_SHA = '640982489f7cc7924da52602130dcf3f100054dd8f907a467759356f1659fbfc'
MAX_INSPECTION_BYTES = 1024 * 1024


def inspect_contract(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    if __package__:
        from .inspect_demae_references import sections
    else:
        from inspect_demae_references import sections
    layout = sections(source)
    def instruction(address, expected):
        for _, offset, base, size in layout:
            if base <= address and address+4 <= base+size:
                if struct.unpack_from('>I', source, offset+address-base)[0] != expected:
                    raise ValueError('Address-save native trace anchor mismatch')
                return
        raise ValueError('Address-save anchor outside executable sections')
    instruction(0x800E10A0, 0x38A00020)  # Save caller selects a 32-byte key.
    instruction(0x800E10A4, 0x48000001 | ((0x800879D0-0x800E10A4) & 0x03FFFFFC))
    instruction(0x800E10BC, 0x38C04000)  # Transformation buffer size, r6.
    instruction(0x800E10C0, 0x48000001 | ((0x80087A94-0x800E10C0) & 0x03FFFFFC))
    instruction(0x800E10F0, 0x2C1B0001)  # Helper return must equal one.
    instruction(0x800E10F4, 0x40820038)
    instruction(0x800E110C, 0x3C03AFBC)  # Subtract high half of PDFF.
    instruction(0x800E1110, 0x28004646)  # Compare remaining low half.
    instruction(0x800E1114, 0x40820018)
    return {'title': 'HCCJ', 'title_version': 2,
            'transform_buffer_bytes': 0x4000, 'caller_key_bits': 256,
            'transform_helper': '0x80087a94',
            'post_transform_magic': 'PDFF',
            'helper_success_required': True,
            'static_trace_only': True, 'native_acceptance_verified': False}


def inspect_metadata(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_INSPECTION_BYTES:
        raise ValueError('Expected bounded nonempty address-save bytes')
    return {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'matches_observed_sample_size': len(data) == 0x4000,
            'starts_with_post_transform_magic': data.startswith(b'PDFF'),
            'personal_fields_reported': False, 'save_decoded': False,
            'checksum_verified': False, 'native_acceptance_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('save', type=Path)
    parser.add_argument('--native-dol', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.save.open('rb') as stream:
            data = stream.read(MAX_INSPECTION_BYTES+1)
        result = {'metadata': inspect_metadata(data)}
        if args.native_dol:
            result['native_contract'] = inspect_contract(args.native_dol.read_bytes())
    except (OSError, ValueError):
        print('Address-save inspection failed: unreadable or invalid input', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
