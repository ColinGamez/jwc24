"""Recover selected 2019 storefront captures into a private, hashed file store.

Reads a checksum-pinned collector backup. Extraction streams through 7-Zip;
captured URL filenames are never used as output paths. No script is executed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zlib

from tools.inspect_wii_shop_frontend_backup import listing_rows, member_path
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE

PRIVATE = Path(__file__).resolve().parents[1]/'private'
ARCHIVE_SIZE = 1668780381


def verify_archive(path):
    if path.stat().st_size != ARCHIVE_SIZE:
        raise ValueError('Unexpected collector archive size')
    sha1, sha256 = hashlib.sha1(), hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):
            sha1.update(chunk)
            sha256.update(chunk)
    if sha1.hexdigest() != ARCHIVE_SHA1:
        raise ValueError('Collector archive fingerprint mismatch')
    return sha256.hexdigest()


def select_members(rows, title_ids):
    selected, navigation, seen = [], Counter(), set()
    for row in rows:
        path = member_path(row['Path'])
        if row.get('Folder') == '+' or row.get('Attributes', '').startswith('D'):
            continue
        size = int(row['Size'])
        if not 0 < size <= 2*1024*1024:
            continue
        take = '/oss/oss/common/' in path or '/oss/oss/ext/attributes/' in path
        if '/oss/serv/' in path:
            name = path.rsplit('/', 1)[-1]
            base = name.split('?', 1)[0]
            if base in ('W_03.jsp', 'B_01.jsp', 'B_27.jsp', 'B_28.jsp', 'B_04.jsp') and navigation[base] < 2:
                navigation[base] += 1
                take = True
            title = re.search(r'(?:\?|&)titleId=([A-Fa-f0-9]{16})(?=&|$)', name)
            japan = re.search(r'(?:\?|&)country=JP(?=&|$)', name)
            if base == 'B_05.jsp' and japan and title and title[1].upper() in title_ids:
                take = True
        if take and not path.lower().endswith('.sh'):
            if (path in seen or row.get('Symbolic Link') or row.get('Hard Link')
                    or row.get('Encrypted', '-') != '-'):
                raise ValueError('Duplicate, linked or encrypted capture member')
            seen.add(path)
            selected.append(row)
    if len(selected) > 4000 or sum(int(r['Size']) for r in selected) > 128*1024*1024:
        raise ValueError('Selected captures exceed review bounds')
    return selected


def extract_selected(archive, rows, output, sevenzip):
    """Require listing-order sizes and CRCs to match the complete output stream."""
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Output must be a new directory beneath private/')
    output.mkdir(parents=True)
    blobs = output/'blobs'
    blobs.mkdir()
    include = output/'members.private.txt'
    include.write_text(''.join(row['Path']+'\n' for row in rows), encoding='utf-8', newline='\n')
    files = []
    with (output/'7z.stderr.private.log').open('wb') as errors:
        process = subprocess.Popen([str(sevenzip), 'x', '-so', '-spd', '-scsUTF-8',
                                    '-bso0', '-bsp0', '-i@'+str(include), str(archive)],
                                   stdout=subprocess.PIPE, stderr=errors)
        try:
            for row in rows:
                size = int(row['Size'])
                data = bytearray()
                while len(data) < size:
                    chunk = process.stdout.read(min(size-len(data), 65536))
                    if not chunk:
                        raise ValueError('Truncated captured member stream')
                    data.extend(chunk)
                if f'{zlib.crc32(data):08X}' != row['CRC'].upper():
                    raise ValueError('Captured member order, size or CRC differs from listing')
                digest = hashlib.sha256(data).hexdigest()
                target = blobs/digest
                if not target.exists():
                    target.write_bytes(data)
                files.append({'member': member_path(row['Path']), 'bytes': size,
                              'crc32': row['CRC'].upper(), 'sha256': digest, 'file': 'blobs/'+digest})
            if process.stdout.read(1) or process.wait(timeout=10) != 0:
                raise ValueError('Unexpected extra capture data or extractor failure')
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--listing', required=True, type=Path)
    parser.add_argument('--catalog', type=Path, default=PRIVATE/'wii_shop/mariocube-catalog-ids.json')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sevenzip', type=Path, default=Path('C:/Program Files/7-Zip/7z.exe'))
    args = parser.parse_args(argv)
    archive_sha256 = verify_archive(args.archive)
    if args.catalog.stat().st_size > 32*1024*1024 or args.listing.stat().st_size > 512*1024*1024:
        raise ValueError('Review input exceeds bounds')
    records = json.loads(args.catalog.read_text(encoding='utf-8'))['records']
    ids = {row['title_id'].upper() for row in records if row.get('title_id')}
    with args.listing.open(encoding='utf-8-sig') as stream:
        selected = select_members(listing_rows(stream), ids)
    if not selected:
        raise ValueError('No captures selected')
    files = extract_selected(args.archive.resolve(), selected, args.output, args.sevenzip)
    manifest = {'schema_version': 1, 'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1,
                'archive_sha256': archive_sha256, 'files': files,
                'complete_original_storefront_verified': False}
    (args.output/'manifest.private.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'captured_files': len(files), 'captured_bytes': sum(f['bytes'] for f in files),
                      'archive_checksum_verified': True, 'scripts_executed': False}))


if __name__ == '__main__':
    main()
