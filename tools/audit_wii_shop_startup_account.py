"""Verify bounded original startup/account call boundaries; emit metadata only.

No source bodies, original bytes, disassembly, encryption parameters, identities
or endpoint values are exported. Static call evidence is not a complete runtime
startup/authorization trace.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from tools.audit_wii_shop_sources import audit as audit_sources
from tools.audit_wii_shop_commerce_surface import read_virtual
from tools.inspect_demae_references import sections
from tools.verify_wii_shop_url import SOURCE_SHA


SOURCES = tuple('common/lib/ec/'+name for name in (
    'ec_api.cpp', 'ec_wshop.cpp', 'ec_js.cpp', 'ec_connect.cpp', 'ec_register.cpp',
    'ec_asyncOp.cpp', 'ec_asyncOp.h', 'ec_soap.cpp', 'ec_soap.h'))
CALLS = (
    ('application_to_EC_Init', 0x8002735c, 0x80088fd0),
    ('EC_Init_to_platform_init', 0x80089024, 0x8008a3c0),
    ('EC_Init_to_environment_init', 0x8008903c, 0x80074010),
    ('platform_init_to_plugin_registration', 0x8008a700, 0x80099f60),
    ('connection_worker_to_GetChallenge', 0x80088e48, 0x80087a50),
    ('connection_worker_to_registration_sync', 0x80088e6c, 0x80088620),
    ('GetChallenge_constructor', 0x80087a80, 0x80087b40),
    ('GetChallenge_start', 0x80087a88, 0x8007c950),
    ('GetChallenge_end', 0x80087a90, 0x8007d600),
    ('GetChallenge_response_wrapper', 0x80087aa0, 0x8007dab0),
    ('response_wrapper_transport', 0x8007db50, 0x800a74a0),
    ('response_wrapper_common_parser', 0x8007dbfc, 0x8007dd20),
    ('GetChallenge_field_reader', 0x80087ad4, 0x8007e470),
)
ARGUMENT_NAMES = ('alloc', 'free', 'EC_LOG_LEVEL', 'EC_BLUETOOTH_MAC_ADDR',
    'EC_DEVICE_CODE', 'EC_ADD_JS_PLUGIN_CALLBACK', 'EC_GET_CURRENT_URL_CALLBACK',
    'EC_CC_ENCRYPT_MODULUS', 'EC_CC_ENCRYPT_MODULUS_SIZE',
    'EC_CC_ENCRYPT_EXPONENT', 'EC_CC_ENCRYPT_EXPONENT_SIZE')
SLICES = ((0x800272e8, 0x800273a0), (0x80088fd0, 0x800890b8),
          (0x80099f60, 0x8009a0a4), (0x80087a50, 0x80087b34))


def audit(main, source_root):
    main = Path(main)
    if not 0 < main.stat().st_size <= 4*1024*1024:
        raise ValueError('Shop executable outside audit byte bound')
    data = main.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError('Original Shop executable fingerprint differs')
    layout = sections(data)
    sources = audit_sources(source_root, selected=SOURCES)
    calls = []
    for role, address, expected in CALLS:
        word = int.from_bytes(read_virtual(data, layout, address, 4), 'big')
        if word >> 26 != 18 or not word & 1 or word & 2:
            raise ValueError('Expected native relative branch-link instruction')
        offset = word & 0x3fffffc
        offset -= 0x4000000 if offset & 0x2000000 else 0
        if (address+offset) & 0xffffffff != expected:
            raise ValueError('Native startup/account call target differs')
        calls.append({'role': role, 'call': f'0x{address:08x}', 'target': f'0x{expected:08x}'})
    table = read_virtual(data, layout, 0x802cea60, 88)
    for index, expected in enumerate(ARGUMENT_NAMES):
        name = struct.unpack_from('>I', table, index*8)[0]
        value = read_virtual(data, layout, name, 96).split(b'\0', 1)[0]
        if value != expected.encode('ascii'):
            raise ValueError('Retail startup argument-name table differs')
    worker = struct.unpack('>6I', read_virtual(data, layout, 0x80322188, 24))
    if worker != (0x803221c0, 0, 0x80076c80, 0x80088f60, 0x80088920, 0x80088f70):
        raise ValueError('Connection worker virtual table differs')
    return {'schema_version': 1, 'checked_on_jst': '2026-10-26',
        'original_main_sha256': SOURCE_SHA,
        'source_inventory_sha256': sources['inventory_sha256'],
        'inventory_verified_sources': sources['verified_files'],
        'native_direct_calls_checked': calls,
        'retail_startup_argument_table': '0x802cea60',
        'retail_startup_argument_count': len(ARGUMENT_NAMES),
        'retail_startup_argument_names': list(ARGUMENT_NAMES),
        'argument_values_or_encryption_parameters_exported': False,
        'connection_worker_virtual_table': '0x80322188',
        'connection_worker_run_entry': '0x80088920',
        'plugin_registration_entry': '0x80099f60',
        'plugin_global_getter': '0x80091300',
        'plugin_origin_callback': '0x80091150',
        'native_slices': [{'start': f'0x{start:08x}', 'end': f'0x{end:08x}',
            'sha256': hashlib.sha256(read_virtual(data, layout, start, end-start)).hexdigest()}
            for start, end in SLICES],
        'original_code_executed_by_audit': False, 'network_or_device_state_accessed': False,
        'complete_runtime_startup_trace': False,
        'public_EC_Connect_or_worker_scheduling_caller_verified': False,
        'account_signing_registration_or_connection_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.main, args.source_root), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
