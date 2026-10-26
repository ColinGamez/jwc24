"""Metadata-only private source/header and retail signer-boundary audit."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re

from tools.audit_wii_shop_commerce_surface import read_virtual
from tools.audit_wii_shop_sources import audit as audit_sources
from tools.inspect_demae_references import sections
from tools.verify_wii_shop_url import SOURCE_SHA


HEADERS = {
    'rvl/iosc.h': (3807, 'a9623c698d782cb1873963a4196702619f93aa469f626dd3bc9e7f19e0150b59'),
    'es.h': (9398, 'e6112488a385d03ee81fcfb3d66e9e2a661ab5dc4e9b16d8422669df1ebc1b2a'),
    'iosccert.h': (3722, '93b4894dd409e9dbdbe691466748ae5c50e019a6fb8f2d23192f2b2437a6de7b'),
    'iosctypes.h': (4388, '5037622270b2a8331a83693b2c299c2d7d6a91f525a1c5ed62dfad655907c9a9'),
}
SOURCES = tuple('common/lib/ec/' + name for name in (
    'ec_misc.cpp', 'ec_asyncOp.cpp', 'ec_asyncOp.h', 'ec_base64.cpp',
    'ec_base64.h', 'ec_common.h', 'ec_esEsp.h'))
CALLS = (
    ('sign_to_sign_data', 0x800785AC, 0x80078430),
    ('sign_data_to_ES_Sign', 0x800784D8, 0x8025AA90),
    ('sign_signature_to_base64', 0x800785D8, 0x800830E0),
    ('sign_certificate_to_base64', 0x800785E8, 0x800830E0),
)


def _read(root, relative, maximum=1024 * 1024):
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Private proof audit input escaped its explicit root')
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Private proof audit input exceeded its byte bound')
    return data


def certificate_layout():
    """Compute the selected SDK layout using retail-confirmed 60-byte aliases.

    The recovered IOSC header aliases CSL ECC types; their 60-byte concrete
    size is independently corroborated by the original retail copy/encode calls.
    This is a layout calculation, not a compilation/execution of recovered code.
    """
    class Signature(ctypes.BigEndianStructure):
        _pack_ = 4
        _fields_ = [('type', ctypes.c_uint32), ('signature', ctypes.c_ubyte * 60),
                    ('ecc_pad', ctypes.c_ubyte * 4), ('dummy', ctypes.c_ubyte * 60),
                    ('issuer', ctypes.c_ubyte * 64)]
    class Header(ctypes.BigEndianStructure):
        _pack_ = 4
        _fields_ = [('type', ctypes.c_uint32), ('name', ctypes.c_ubyte * 64),
                    ('opaque_word', ctypes.c_uint32)]
    class Certificate(ctypes.BigEndianStructure):
        _pack_ = 4
        _fields_ = [('signature', Signature), ('header', Header),
                    ('public_key', ctypes.c_ubyte * 60), ('ecc_pad', ctypes.c_ubyte * 4),
                    ('pad', ctypes.c_ubyte * 52), ('pad2', ctypes.c_ubyte * 4)]
    return {'certificate_bytes': ctypes.sizeof(Certificate), 'raw_signature_bytes': 60,
            'signature_type_offset': 0, 'raw_signature_offset': 4,
            'issuer_offset': Signature.issuer.offset,
            'public_key_type_offset': Certificate.header.offset,
            'name_offset': Certificate.header.offset + Header.name.offset,
            'opaque_word_offset': Certificate.header.offset + Header.opaque_word.offset,
            'public_key_offset': Certificate.public_key.offset,
            'raw_public_key_bytes': 60}


def audit(main, source_root, header_root):
    source_root, header_root = Path(source_root).resolve(), Path(header_root).resolve()
    sources = audit_sources(source_root, selected=SOURCES)
    if sources['inventory_sha256'] != 'ea7edbe9e4e03f96f24cb3b2ccf45241bbac678be6351877719cab89e453c352':
        raise ValueError('Private Shop source inventory differs from the reviewed extraction')
    rows, texts = [], {}
    for name, (size, digest) in HEADERS.items():
        data = _read(header_root, name)
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Private SDK header differs from the selected archive member')
        texts[name] = data.decode('latin-1')
        rows.append({'member': 'ios_releases/ios_30.4.0/RVL_128/usr/include/' + name,
                     'bytes': size, 'sha256': digest})
    if (re.search(r'IOSCEccSignedCert\s*\[384\]', texts['iosctypes.h']) is None
            or 'IOSC_SIG_RSA4096 = 0x00010000' not in texts['iosctypes.h']
            or re.search(r'IOSCName\s*\[64\]', texts['iosccert.h']) is None
            or re.search(r'IOSCSigDummy\s*\[60\]', texts['iosccert.h']) is None
            or re.search(r'IOSCCertPad\s*\[52\]', texts['iosccert.h']) is None
            or 'IOSCEccEccCert* signerKeyCert' not in texts['es.h']):
        raise ValueError('Selected SDK structure evidence differs')
    try:
        with Path(main).open('rb') as stream:
            data = stream.read(4 * 1024 * 1024 + 1)
    except OSError:
        raise ValueError('Original Shop executable could not be read') from None
    if len(data) > 4 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError('Original Shop executable identity differs')
    layout = sections(data)
    calls = []
    for role, site, target in CALLS:
        word = int.from_bytes(read_virtual(data, layout, site, 4), 'big')
        offset = word & 0x3FFFFFC
        offset -= 0x4000000 if offset & 0x2000000 else 0
        if word >> 26 != 18 or word & 3 != 1 or (site + offset) & 0xFFFFFFFF != target:
            raise ValueError('Original Shop signing call target differs')
        calls.append({'role': role, 'site': f'0x{site:08x}', 'target': f'0x{target:08x}'})
    # Explicit native Base64 input lengths, not inferred from typedef spelling.
    if (read_virtual(data, layout, 0x800785D4, 4) != bytes.fromhex('3880003c')
            or read_virtual(data, layout, 0x800785E4, 4) != bytes.fromhex('38800180')):
        raise ValueError('Original Shop signing output lengths differ')
    return {'schema_version': 1, 'checked_on_jst': '2026-10-27',
            'source_inventory_sha256': sources['inventory_sha256'],
            'inventory_verified_sources': sources['verified_files'],
            'selected_original_headers': rows, 'original_archive_sha256_checked': False,
            'archive_nintendo_provenance_independently_verified': False,
            'certificate_layout': certificate_layout(), 'native_direct_calls_checked': calls,
            'native_slices': [{'start': f'0x{start:08x}', 'end': f'0x{end:08x}',
                              'sha256': hashlib.sha256(read_virtual(data, layout, start, end - start)).hexdigest()}
                             for start, end in ((0x80078430, 0x80078570), (0x80078570, 0x80078610))],
            'headers_compiled_or_original_ios_crypto_executed': False,
            'opaque_header_word_meaning_verified': False,
            'device_or_profile_accessed': False, 'metadata_only': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--header-root', type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.main, args.source_root, args.header_root), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
