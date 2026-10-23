"""Read-only Shop content audit; never reads tickets or account/save files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from urllib.parse import urlsplit


MARKERS = ('ECommerceInterface', 'ECProgress', 'GetECConfig',
           'CheckDeviceStatus', 'CheckRegistration', 'SyncRegistration')


def shared_names(data):
    if len(data) % 28 or len(data) > 2800000:
        raise ValueError('Invalid shared content map length')
    names = {}
    for offset in range(0, len(data), 28):
        name, digest = data[offset:offset+8], data[offset+8:offset+28]
        if not re.fullmatch(rb'[0-9a-fA-F]{8}', name) or digest in names:
            raise ValueError('Invalid or duplicate shared content map record')
        names[digest] = name.decode('ascii')
    return names


def verify_content(data, size, digest):
    if len(data) != size or hashlib.sha1(data).digest() != digest:
        raise ValueError('Content differs from title metadata')
    return hashlib.sha256(data).hexdigest()


def routes(data):
    found = set()
    for match in re.finditer(rb'https?://[^\x00\s<>"\x27]{1,240}', data):
        try:
            url = urlsplit(match[0].decode('ascii'))
            host = url.hostname
        except (ValueError, UnicodeError):
            continue
        if host and any(host.endswith('.'+domain) or host == domain
                        for domain in ('wii.com', 'nintendo.com', 'nintendo.net')):
            # Query/fragment/userinfo are never emitted, even from a fixture.
            found.add((url.scheme, host, url.path))
    return [{'scheme': scheme, 'host': host, 'path': path} for scheme, host, path in sorted(found)]


def is_dol(data):
    if len(data) < 0x100:
        return False
    offsets = struct.unpack_from('>18I', data)
    addresses = struct.unpack_from('>18I', data, 0x48)
    sizes = struct.unpack_from('>18I', data, 0x90)
    entry = struct.unpack_from('>I', data, 0xe0)[0]
    if entry < 0x1800000:
        entry |= 0x80000000  # Physical MEM1 entry alias used by the installed boot loader.
    executable_entry = False
    for index, (offset, address, size) in enumerate(zip(offsets, addresses, sizes)):
        if not size:
            continue
        if offset < 0x100 or offset+size > len(data) or not 0x80000000 <= address < address+size <= 0x81800000:
            return False
        executable_entry |= index < 7 and address <= entry < address+size
    return executable_entry


def audit(nand_root):
    from libWiiPy.archive import U8Archive
    from libWiiPy.title.tmd import TMD
    root = Path(nand_root).resolve()
    def read(relative, limit):
        path = (root/relative).resolve()
        if not path.is_relative_to(root) or path.stat().st_size > limit:
            raise ValueError('Content path or size outside audit bounds')
        return path.read_bytes()
    content = Path('title/00010002/48414241/content')
    tmd_data = read(content/'title.tmd', 1024*1024)
    tmd = TMD()
    tmd.load(tmd_data)
    if tmd.title_id.upper() != '0001000248414241':
        raise ValueError('Title metadata is not the expected Shop title')
    names = shared_names(read(Path('shared1/content.map'), 2800000))
    rows = []
    for record in tmd.content_records:
        value = record.content_hash
        digest = bytes.fromhex(value.decode('ascii')) if isinstance(value, bytes) and len(value) == 40 else bytes.fromhex(value) if isinstance(value, str) else value
        shared = bool(record.content_type & 0x8000)
        if shared:
            if digest not in names:
                raise ValueError('Shared content missing from content map')
            path = Path('shared1')/(names[digest]+'.app')
        else:
            path = content/f'{record.content_id:08x}.app'
        data = read(path, 64*1024*1024)
        sha256 = verify_content(data, record.content_size, digest)
        executable = is_dol(data)
        row = {'index': record.index, 'content_id': f'{record.content_id:08x}',
               'shared': shared, 'bytes': len(data), 'sha1_matches_tmd': True,
               'sha256': sha256, 'dol_structure': executable,
               'markers': [marker for marker in MARKERS if marker.encode('ascii') in data],
               'static_routes': routes(data) if executable else []}
        if data.startswith(b'\x55\xaa\x38\x2d'):
            archive = U8Archive()
            archive.load(data)
            row['u8_nodes'] = len(archive.file_name_list)
            row['page_config_names'] = [name for name in archive.file_name_list
                                        if re.search(r'\.(html?|js|xml|ini|cfg)$', name, re.I)]
        rows.append(row)
    return {'schema_version': 1, 'title_id': tmd.title_id.upper(),
            'title_version': tmd.title_version, 'required_ios': tmd.ios_version,
            'boot_index': tmd.boot_index, 'tmd_sha256': hashlib.sha256(tmd_data).hexdigest(),
            'contents': rows, 'all_content_hashes_match_tmd': True,
            'tmd_signature_verified': False, 'source_revision_match_verified': False,
            'static_routes_are_candidates': True,
            'static_evidence_only': True, 'startup_request_order_verified': False,
            'runtime_or_nand_modified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('nand_root', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.nand_root), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
