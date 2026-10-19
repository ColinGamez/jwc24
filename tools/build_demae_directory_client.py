"""Stage an uninstalled directory-list client candidate; not ordering support.

Only removes the shop-list cash-payment eligibility filter. Requires review of
native stopped-row display and navigation before use in the shared profile.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import struct

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwc24.lz11 import decode_lz11, encode_lz11
from tools.asset_publication import publish_assets
from tools.demae_native_hook_support import replace_text_instruction, fill_owned_text_padding, branch_instruction, OWNED_PADDING_START, OWNED_PADDING_END
from tools.inspect_demae_references import sections

SOURCE_SHA = 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830'
FILTER_ADDRESS = 0x80038DB8
ROW_TRANSITION = 0x8003C3BC
JOB_SLOT = 0x8034329C + 0x53B * 4
LOGO_PREFIX_ADDRESS = 0x802D647B
LOGO_HTTPS_ADDRESS = 0x800398E8


def patch_directory_images(source):
    """Pair the stock logo URL data with HTTP at its reviewed list caller."""
    result = replace_text_instruction(source, LOGO_HTTPS_ADDRESS,
                                      expected=bytes.fromhex('38c00001'),
                                      replacement=bytes.fromhex('38c00000'))
    old = b'nwpic.demae-can.com/logoimg2/\0'
    new = b'127.0.0.1:18085/logoimg2/\0'
    for _, offset, base, size in sections(result):
        if base <= LOGO_PREFIX_ADDRESS and LOGO_PREFIX_ADDRESS+len(old) <= base+size:
            position = offset+LOGO_PREFIX_ADDRESS-base
            if result[position:position+len(old)] != old:
                raise ValueError('Logo URL prefix does not match reviewed native data')
            result = result[:position]+new.ljust(len(old), b'\0')+result[position+len(old):]
            return result
    raise ValueError('Logo URL prefix outside native sections')


def patch_directory_filter(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Directory client source fingerprint mismatch')
    result = replace_text_instruction(source, FILTER_ADDRESS,
                                      expected=bytes.fromhex('41820170'),
                                      replacement=bytes.fromhex('60000000'))
    # This does not assert payment support, set its flag, or change status,
    # telephone validation, ordering callbacks, or the home button.
    return result


def patch_directory_modal(source, payload, metadata):
    if metadata['base_address'] != OWNED_PADDING_START:
        raise ValueError('Directory payload link address mismatch')
    for name in ('directory_enter', 'directory_job', 'directory_context', 'directory_cleanup'):
        symbol = metadata['symbols'][name]
        if symbol % 4 or not OWNED_PADDING_START <= symbol < OWNED_PADDING_START+len(payload):
            raise ValueError('Directory symbol outside reviewed payload')
    from tools.verify_demae_directory_modal import verify
    scenarios = verify(payload, metadata)
    result = fill_owned_text_padding(source, payload, expected_sha256=SOURCE_SHA)
    result = replace_text_instruction(result, FILTER_ADDRESS,
                                      expected=bytes.fromhex('41820170'), replacement=bytes.fromhex('60000000'))
    result = replace_text_instruction(result, ROW_TRANSITION, expected=bytes.fromhex('38600104'),
                                      replacement=branch_instruction(ROW_TRANSITION, metadata['symbols']['directory_enter']))
    result = replace_text_instruction(result, 0x800AA2DC, expected=bytes.fromhex('9421ff80'),
                                      replacement=branch_instruction(0x800AA2DC, metadata['symbols']['directory_cleanup']))
    for index, offset, base, size in sections(result):
        if index >= 7 and base <= JOB_SLOT <= base+size-4:
            position = offset+JOB_SLOT-base
            if result[position:position+4] != struct.pack('>I', 0x800B75C4):
                raise ValueError('Directory job slot is not the reviewed unused case')
            result = result[:position]+struct.pack('>I', metadata['symbols']['directory_job'])+result[position+4:]
            break
    else:
        raise ValueError('Directory job slot outside data sections')
    return result, scenarios


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dol', type=Path, required=True)
    parser.add_argument('--output-content', type=Path, required=True)
    parser.add_argument('--modal-payload', type=Path)
    parser.add_argument('--modal-metadata', type=Path)
    parser.add_argument('--local-directory-images', action='store_true')
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    for path in (args.output_dol, args.output_content):
        if not path.resolve().is_relative_to(private.resolve()) or path.exists():
            parser.error('Outputs must be new private files')
    source = args.source.read_bytes()
    if bool(args.modal_payload) != bool(args.modal_metadata):
        parser.error('Modal payload and metadata must be provided together')
    scenarios = 0
    if args.modal_payload:
        result, scenarios = patch_directory_modal(source, args.modal_payload.read_bytes(),
                                                  json.loads(args.modal_metadata.read_bytes()))
    else:
        result = patch_directory_filter(source)
    if args.local_directory_images:
        if not args.modal_payload:
            parser.error('Local directory images require the read-only modal candidate')
        result = patch_directory_images(result)
    content = encode_lz11(result)
    if decode_lz11(content) != result:
        raise ValueError('Directory candidate compression roundtrip failed')
    metadata = {'source_sha256': SOURCE_SHA, 'output_sha256': hashlib.sha256(result).hexdigest(),
                'changed_instructions': [hex(FILTER_ADDRESS)] + ([hex(ROW_TRANSITION), '0x800aa2dc'] if args.modal_payload else []),
                'changed_job_slot': hex(JOB_SLOT) if args.modal_payload else None,
                'cash_payment_flag_modified': False,
                'home_flow_modified': False, 'ordering_callbacks_modified': False,
                'requires_read_only_backend': True,
                'native_render_verified': False, 'installed': False,
                'directory_modal': bool(args.modal_payload), 'compiled_mock_scenarios': scenarios}
    metadata['local_directory_images'] = args.local_directory_images
    if args.local_directory_images:
        metadata['changed_instructions'].append(hex(LOGO_HTTPS_ADDRESS))
        metadata['changed_logo_prefix'] = hex(LOGO_PREFIX_ADDRESS)
    if args.modal_payload:
        metadata['required_resource_group'] = 'JWC24_DIRECTORY'
    publish_assets([(args.output_dol, result), (args.output_content, content),
                    (args.output_dol.with_suffix('.metadata.json'), json.dumps(metadata, indent=2).encode())],
                   source_check=(args.source, source))
    print('Staged uninstalled directory client candidate; no runtime or shared-profile changes')


if __name__ == '__main__':
    main()
