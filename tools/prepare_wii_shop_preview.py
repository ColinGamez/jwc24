"""Build a new private Dolphin profile with a loopback-only Shop preview.

Copies the local profile's Config and Wii directories, patches only the copied
Shop executable/resources/metadata, and creates a local development CA. Original
content and personal configuration are not edited. No title is downloaded.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

from tools.verify_wii_shop_url import SOURCE_SHA

BASE_URL = b'https://127.0.0.1:18443'
PRIVATE = Path(__file__).resolve().parents[1]/'private'


def patch_dol(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError('Unknown Shop v21 executable')
    output = bytearray(data)
    count = 0
    pattern = rb'https://(?:oss-auth|ecs|ias|cas|ccs|ucs)\.shop\.wii\.com[^\x00]{0,256}\x00'
    for match in re.finditer(pattern, data):
        original = match[0]
        suffix = original[original.index(b'.shop.wii.com')+len(b'.shop.wii.com'):]
        replacement = BASE_URL+suffix
        if len(replacement) > len(original):
            raise ValueError('Loopback URL exceeds original field')
        output[match.start():match.end()] = replacement.ljust(len(original), b'\0')
        count += 1
    if count < 3 or len(output) != len(data):
        raise ValueError('Shop URL fields differ from expected layout')
    return bytes(output), count


def opera_ca_store(der):
    # Store format documented by OpenShopChannel/WSC-Patcher (MIT).
    # See third_party/wsc-patcher.LICENSE and channels/wii_shop/runtime_preview.md.
    from Crypto.Util.asn1 import DerSequence
    certificate = DerSequence().decode(der)
    body = DerSequence().decode(certificate[0])
    subject = body[5]
    def tag(identifier, payload):
        return bytes([identifier])+struct.pack('>I', len(payload))+payload
    contents = (tag(0x20, struct.pack('>I', 1))+tag(0x21, b'JWC24 Shop Preview CA')
                +tag(0x22, subject)+tag(0x23, der))
    return bytes.fromhex('000010000505002300010004')+tag(2, contents)


def patch_archive(data, root_der):
    from libWiiPy.archive import U8Archive
    archive = U8Archive()
    archive.load(data)
    originals = list(archive.file_data_list)
    replacements = {
        'myfilter.ini': (b'[prefs]\r\nprioritize excludelist=0\r\n\r\n[include]\r\n'
                         b'file:/cnt/*\r\n'+BASE_URL+b'/*\r\nmiip:*\r\n\r\n[exclude]\r\n*\r\n'),
        'opcacrt6.dat': opera_ca_store(root_der),
    }
    for name, replacement in replacements.items():
        if archive.file_name_list.count(name) != 1:
            raise ValueError('Ambiguous Opera resource')
        index = archive.file_name_list.index(name)
        archive.file_data_list[index] = replacement
        archive.u8_node_list[index].size = len(replacement)
    output = archive.dump()
    check = U8Archive()
    check.load(output)
    if check.file_name_list != archive.file_name_list:
        raise ValueError('Resource names changed')
    for name, before, after in zip(check.file_name_list, originals, check.file_data_list):
        if after != replacements.get(name, before):
            raise ValueError('Unrelated resource changed')
    return output


def certificates(directory, openssl):
    directory.mkdir()
    def run(*arguments):
        result = subprocess.run([openssl, *map(str, arguments)], capture_output=True)
        if result.returncode:
            raise RuntimeError('Local certificate generation failed')
    run('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha1', '-days', '3650',
        '-subj', '/CN=JWC24 Shop Preview CA', '-keyout', directory/'root.key', '-out', directory/'root.pem',
        '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    run('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=127.0.0.1',
        '-keyout', directory/'server.key', '-out', directory/'server.csr')
    extension = directory/'server.ext'
    extension.write_text('basicConstraints=critical,CA:FALSE\nsubjectAltName=IP:127.0.0.1\n'
                         'keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    run('x509', '-req', '-sha1', '-days', '3650', '-in', directory/'server.csr',
        '-CA', directory/'root.pem', '-CAkey', directory/'root.key', '-CAcreateserial',
        '-extfile', extension, '-out', directory/'server.pem')
    run('x509', '-in', directory/'root.pem', '-outform', 'DER', '-out', directory/'root.der')
    return (directory/'root.der').read_bytes()


def prepare(source, destination, openssl):
    from tools.audit_wii_shop_client import audit
    from libWiiPy.title.tmd import TMD
    source, destination = source.resolve(), destination.resolve()
    if (not destination.is_relative_to(PRIVATE.resolve()) or destination.exists()
            or destination == PRIVATE.resolve() or source.is_relative_to(destination)):
        raise ValueError('Destination must be a new profile beneath private/')
    source_audit = audit(source/'Wii')
    for tree in (source/'Wii', source/'Config'):
        for root, directories, files in os.walk(tree, followlinks=False):
            for name in directories+files:
                entry = Path(root)/name
                if entry.is_symlink() or getattr(entry.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise ValueError('Source profile contains a reparse point')
    source_hashes = {row['index']: row['sha256'] for row in source_audit['contents']}
    content_rel = Path('Wii/title/00010002/48414241/content')
    if source_hashes[1] != SOURCE_SHA:
        raise ValueError('Installed executable fingerprint differs')
    destination.mkdir(parents=True)
    root_der = certificates(destination/'tls', openssl)
    shutil.copytree(source/'Wii', destination/'Wii')
    shutil.copytree(source/'Config', destination/'Config')
    content = destination/content_rel
    dol_path, arc_path = content/'0000005e.app', content/'0000005f.app'
    if (hashlib.sha256(dol_path.read_bytes()).hexdigest() != source_hashes[1]
            or hashlib.sha256(arc_path.read_bytes()).hexdigest() != source_hashes[2]):
        raise ValueError('Content changed during profile copy')
    patched_dol, url_count = patch_dol(dol_path.read_bytes())
    patched_archive = patch_archive(arc_path.read_bytes(), root_der)
    dol_path.write_bytes(patched_dol)
    arc_path.write_bytes(patched_archive)
    tmd_path = content/'title.tmd'
    tmd = TMD()
    tmd.load(tmd_path.read_bytes())
    for record in tmd.content_records:
        if record.index in (1, 2):
            payload = patched_dol if record.index == 1 else patched_archive
            record.content_size = len(payload)
            record.content_hash = hashlib.sha1(payload).hexdigest()
    tmd_path.write_bytes(tmd.dump())
    config_path = destination/'Config/Dolphin.ini'
    config = configparser.ConfigParser(strict=False, interpolation=None)
    config.optionxform = str
    config.read(config_path, encoding='utf-8')
    for section, key, value in (
        ('General', 'NANDRootPath', str(destination/'Wii')),
        ('Core', 'EnableCustomRTC', 'False'), ('Core', 'EnableCheats', 'False'),
        ('Core', 'WiiSDCard', 'False'),
        ('Core', 'MMU', 'False'), ('General', 'GDBPort', '-1'),
        ('Display', 'RenderToMain', 'True'),
    ):
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, key, value)
    with config_path.open('w', encoding='utf-8') as handle:
        config.write(handle)
    (destination/'Config/Logger.ini').write_text(
        '[Options]\nVerbosity = 3\nWriteToFile = True\nWriteToConsole = False\n'
        '[Logs]\nBOOT = True\nIOS_ES = True\nIOS_NET = True\nIOS_SSL = True\n', encoding='utf-8')
    copied_audit = audit(destination/'Wii')
    if not copied_audit['all_content_hashes_match_tmd']:
        raise ValueError('Patched content audit failed')
    for index, row in enumerate(source_audit['contents']):
        if row['index'] not in (1, 2) and row['sha256'] != copied_audit['contents'][index]['sha256']:
            raise ValueError('Unrelated title content changed')
    if audit(source/'Wii') != source_audit:
        raise ValueError('Source title changed during preparation')
    report = {'schema_version': 1, 'base_url': BASE_URL.decode(), 'title_id': '0001000248414241',
              'source_dol_sha256': SOURCE_SHA, 'patched_dol_sha256': hashlib.sha256(patched_dol).hexdigest(),
              'patched_archive_sha256': hashlib.sha256(patched_archive).hexdigest(),
              'url_fields_replaced': url_count, 'copied_content_hashes_match_tmd': True,
              'modified_content_indices': [1, 2], 'patched_tmd_signature_verified': False,
              'source_title_unchanged': True, 'downloads_supported': False}
    (destination/'preview-profile.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(os.environ['APPDATA'])/'Dolphin Emulator')
    parser.add_argument('--profile', type=Path, default=PRIVATE/'wii_shop/preview-profile')
    parser.add_argument('--openssl', default=shutil.which('openssl'))
    args = parser.parse_args(argv)
    if not args.openssl:
        parser.error('OpenSSL is required for local test certificates')
    print(json.dumps(prepare(args.source, args.profile, args.openssl), indent=2))


if __name__ == '__main__':
    main()
