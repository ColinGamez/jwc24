"""Stage a fingerprinted private phone-modal executable; does not install it.

Requires independently reviewed payload metadata and owned-padding review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.lz11 import decode_lz11, encode_lz11
from tools.asset_publication import atomic_write
from tools.demae_native_hook_support import (
    OWNED_PADDING_START, fill_owned_text_padding, branch_instruction, replace_text_instruction,
)

SOURCE_SHA = 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830'
HOOKS = {
    'phone_frame_hook': (0x800DC768, '800400ac'),
    'phone_click_hook': (0x800DC7A8, '2c030000'),
    'phone_draw_hook': (0x800DC8B4, '38600001'),
    'phone_cleanup_hook': (0x800CB774, '80030dd4'),
}


def build(source, payload, metadata):
    if hashlib.sha256(payload).hexdigest() != metadata['payload_sha256']:
        raise ValueError('Reviewed payload fingerprint mismatch')
    if metadata['base_address'] != OWNED_PADDING_START:
        raise ValueError('Payload link address mismatch')
    result = fill_owned_text_padding(source, payload, expected_sha256=SOURCE_SHA)
    for name, (site, original) in HOOKS.items():
        target = metadata['symbols'][name]
        if not OWNED_PADDING_START <= target < OWNED_PADDING_START + len(payload):
            raise ValueError('Hook symbol outside payload')
        result = replace_text_instruction(result, site, expected=bytes.fromhex(original),
                                          replacement=branch_instruction(site, target))
    compressed = encode_lz11(result)
    if decode_lz11(compressed) != result:
        raise ValueError('Executable compression roundtrip failed')
    return result, compressed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'payload', 'metadata', 'output_dol', 'output_content'):
        parser.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    for output in (args.output_dol, args.output_content):
        if not output.resolve().is_relative_to(private.resolve()) or output.exists():
            parser.error('Outputs must be new files inside private/')
    dol, content = build(args.source.read_bytes(), args.payload.read_bytes(),
                         json.loads(args.metadata.read_text(encoding='utf-8')))
    atomic_write(args.output_dol, dol)
    atomic_write(args.output_content, content)
    print('Staged private phone executable; not installed or launched')


if __name__ == '__main__':
    main()
