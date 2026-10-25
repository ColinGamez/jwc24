"""Read-only provenance/service-role audit for three owned Japanese channels.

Uses independently extracted private contents, verifies every one against the
source WAD's TMD, and emits metadata only. It never installs titles, reads NAND,
executes Nintendo tools, contacts providers or supplies replacement channel data.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from jwc24.lz11 import decode_lz11


@dataclass(frozen=True)
class ChannelSpec:
    code: str
    filename: str
    extracted: str
    title_id: str
    version: int
    contents: int
    main_sha256: str


CHANNELS = (
    ChannelSpec('HAVJ', 'Today and tomorrow Channel.wad', 'havj-v512', '000100014841564A',
                512, 12, 'fdf597412f5dedf2dd4b9388204ed35a52ad3624282a23c08bb54d29f237f0d2'),
    ChannelSpec('HCFJ', 'Wii Speak channel.wad', 'hcfj-v512', '000100014843464A',
                512, 9, '7da329f17754d3199b6254f26c3e059913671820f9017c2424236430aa64eff3'),
    ChannelSpec('HCDJ', 'digicam print channel.wad', 'hcdj-v1024', '000100014843444A',
                1024, 13, '419c295d0745a5991df5468a4dd1dfc502fdf6c81f47898629f65fbd42e40f7e'),
)
MARKERS = ('NWC24OpenLib', 'NWC24CommitMsg', 'NWC24InitMsgObj', 'NWC24SetMsgAttached',
           'NWC24iDownloadNowEx', 'NWC24iGetSchedulerStat', 'DWC_Init', 'DWC_Login',
           'DWC_Connect', 'NHTTP')


def checked_content(root, row):
    name = row.get('file')
    if not isinstance(name, str) or not re.fullmatch(r'[0-9a-f]{4}-[0-9a-f]{8}\.app', name):
        raise ValueError('Invalid extracted content filename')
    path = (root/name).resolve()
    if not path.is_relative_to(root.resolve()) or not 0 <= path.stat().st_size <= 32*1024*1024:
        raise ValueError('Extracted content outside audit bounds')
    body = path.read_bytes()
    if len(body) != row.get('size') or hashlib.sha256(body).hexdigest() != row.get('sha256'):
        raise ValueError('Extracted content fingerprint differs')
    return body


def application_image(contents):
    """These builds carry LZ11 application code at content index1, not boot index."""
    body = contents.get(1)
    if not isinstance(body, bytes) or len(body) < 4 or body[0] != 0x11:
        raise ValueError('Expected bounded LZ11 application content')
    expected = int.from_bytes(body[1:4], 'little')
    if expected == 0:
        if len(body) < 8:
            raise ValueError('Truncated LZ11 application header')
        expected = int.from_bytes(body[4:8], 'little')
    if not 0 < expected <= 8*1024*1024:
        raise ValueError('Decompressed application exceeds audit bound')
    result = decode_lz11(body)
    if len(result) != expected:
        raise ValueError('Decompressed application size differs')
    return result


def application_consumers(code, application):
    """Check selected static relationships; this does not execute the application."""
    from tools.inspect_demae_references import sections
    layout = sections(application)

    def read(address, size):
        if not 0 < size <= 8192:
            raise ValueError('Native audit slice exceeds bound')
        for _, offset, base, length in layout:
            if base <= address < address+size <= base+length:
                return application[offset+address-base:offset+address-base+size]
        raise ValueError('Native audit read outside mapped sections')

    if code == 'HAVJ':
        table = int.from_bytes(read(0x805556d8, 4), 'big')
        index = int.from_bytes(read(table+0xe0, 2), 'big')
        name_pointer = int.from_bytes(read(table+0xe4, 4), 'big')
        if index != 6 or read(name_pointer, 17) != b'etc/affinity.bin\0':
            raise ValueError('Bundled affinity resource consumer differs')
        return {'scope': 'Static resource-table and selected initializer inspection',
            'initializer': '0x8009b770', 'resource_call': '0x8009b854',
            'resource_consumer': '0x800a7780', 'archive_index': index,
            'bundled_resource': 'etc/affinity.bin', 'local_save_name': 'uranai6.dat',
            'local_save_name_present': b'uranai6.dat\0' in application,
            'hosted_core_payload_contract_recovered': False,
            'local_predictions_or_native_ui_executed': False}
    if code == 'HCFJ':
        uri = b'http://nwcs.wapp.wii.com/hcf/version.enc\0'
        if read(0x803ae36d, len(uri)) != uri:
            raise ValueError('Version descriptor URL differs')
        return {'scope': 'Static version-descriptor and compiled SDK evidence',
            'initializer_slice': ['0x800b9624', '0x800b9718'],
            'version_url_reference': '0x800b965c', 'descriptor_consumer_call': '0x800b9714',
            'descriptor_consumer': '0x800423b4', 'version_host': 'nwcs.wapp.wii.com',
            'version_path': '/hcf/version.enc', 'crypto_resource_selectors_observed': True,
            'crypto_keys_exported': False, 'version_host_is_proven_voice_broker': False,
            'delivery_envelope_or_WFC_service_compatibility_verified': False}
    if code == 'HCDJ':
        return {'scope': 'Static HTTP controller plus separate synthetic native execution',
            'provider_url_controller': '0x80045ed4', 'tls_selector': '0x80046124',
            'formatter': '0x800b3ef4', 'provider_host': 'wch.fdinet.fujifilm.co.jp',
            'operation_path': '/wii_svr/WPOperationServlet',
            'file_operation_path': '/wii_svr/WPFileOperationServlet',
            'print_fulfillment_or_order_contract_verified': False,
            'message_board_delivery_verified': False}
    raise ValueError('Unsupported audited channel')


def audit_package(wad_path, extracted_root, spec):
    from libWiiPy.title.wad import WAD
    from libWiiPy.title.tmd import TMD
    from libWiiPy.title.ticket import Ticket
    from libWiiPy.archive import U8Archive

    wad_path, extracted_root = Path(wad_path), Path(extracted_root)
    if not 0 < wad_path.stat().st_size <= 64*1024*1024:
        raise ValueError('Source WAD exceeds audit bound')
    wad_bytes = wad_path.read_bytes()
    manifest_path = extracted_root/'manifest.json'
    if manifest_path.stat().st_size > 1024*1024:
        raise ValueError('Extracted manifest exceeds audit bound')
    manifest = json.loads(manifest_path.read_bytes())
    source_sha = hashlib.sha256(wad_bytes).hexdigest()
    if manifest.get('source_sha256') != source_sha or manifest.get('source_size') != len(wad_bytes):
        raise ValueError('Source WAD differs from extraction manifest')
    wad = WAD()
    wad.load(wad_bytes)
    tmd_bytes = wad.get_tmd_data()
    tmd, ticket = TMD(), Ticket()
    tmd.load(tmd_bytes)
    ticket.load(wad.get_ticket_data())
    if (ticket.title_id.hex().upper() != spec.title_id or tmd.title_id.upper() != spec.title_id
            or tmd.title_version != spec.version or len(tmd.content_records) != spec.contents
            or manifest.get('title_id') != spec.title_id or manifest.get('title_version') != spec.version):
        raise ValueError('Owned package title/version does not match the selected build')
    rows = manifest.get('contents')
    if not isinstance(rows, list) or len(rows) != spec.contents:
        raise ValueError('Extracted content count differs')
    contents, content_metadata = {}, []
    for record, row in zip(tmd.content_records, rows):
        if (row.get('index') != record.index or row.get('content_id') != f'{record.content_id:08X}'
                or row.get('type') != record.content_type or record.index in contents):
            raise ValueError('Extracted content record differs from source TMD')
        body = checked_content(extracted_root, row)
        expected_sha1 = record.content_hash.decode('ascii')
        if len(body) != record.content_size or hashlib.sha1(body).hexdigest() != expected_sha1:
            raise ValueError('Extracted content does not match source TMD hash/size')
        contents[record.index] = body
        content_metadata.append({'index': record.index, 'content_id': row['content_id'],
            'bytes': len(body), 'sha1_matches_tmd': True, 'sha256': row['sha256']})
    application = application_image(contents)
    if hashlib.sha256(application).hexdigest() != spec.main_sha256:
        raise ValueError('Known application fingerprint differs')
    resources = []
    for index, body in contents.items():
        if body[:4] != b'\x55\xaa\x38\x2d':
            continue
        archive = U8Archive()
        archive.load(body)
        if len(archive.file_name_list) > 10000:
            raise ValueError('Resource archive exceeds audit member bound')
        for name, payload in zip(archive.file_name_list, archive.file_data_list):
            if name == 'affinity.bin' and payload:
                resources.append({'content_index': index, 'member_basename': name,
                    'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
    return {'channel_id': spec.code, 'title_id': spec.title_id, 'title_version': spec.version,
        'required_ios': tmd.ios_version, 'boot_index': tmd.boot_index,
        'source_wad_bytes': len(wad_bytes), 'source_wad_sha256': source_sha,
        'tmd_sha256': hashlib.sha256(tmd_bytes).hexdigest(),
        'ticket_tmd_title_identity_matches': True, 'all_content_sizes_and_sha1_match_tmd': True,
        'nintendo_signature_verified': False, 'verified_contents': content_metadata,
        'application_content_index': 1, 'application_compression': 'Nintendo LZ11',
        'application_bytes': len(application), 'application_sha256': spec.main_sha256,
        'selected_consumer_evidence': application_consumers(spec.code, application),
        'selected_application_marker_counts': {m: application.count(m.encode()) for m in MARKERS},
        'selected_bundled_resources': resources,
        'original_program_or_script_executed': False, 'network_or_device_state_accessed': False,
        'marker_presence_is_not_an_active_service_contract': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wads', type=Path, default=Path('Stock WADs'))
    parser.add_argument('--extracted', type=Path, default=Path('private/channel_coverage_20261026'))
    args = parser.parse_args(argv)
    result = {'schema_version': 1, 'checked_on_jst': '2026-10-26',
        'scope': 'Owned source packages, independently extracted contents and selected application/resource evidence',
        'channels': [audit_package(args.wads/spec.filename, args.extracted/spec.extracted, spec) for spec in CHANNELS],
        'source_wads_changed': False, 'titles_installed_or_launched': False,
        'real_wii_backup_accessed': False, 'device_credentials_accessed': False,
        'print_voice_account_or_delivery_operation_submitted': False}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
