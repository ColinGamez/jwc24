"""Import explicitly selected Japanese game manuals from the private 2019 capture.

Recovered bodies stay beneath private/. This does not recover the missing Shop
operations guide, execute a script, or enable a Shop route.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_manual import ARCHIVE_SHA256, MAX_BYTES, MAX_FILES, MAX_TITLES, manual_path
from tools.import_wii_shop_frontend_capture import extract_selected, verify_archive
from tools.inspect_wii_shop_frontend_backup import listing_rows, member_path


def select_manual_members(rows, title_ids):
    if (not title_ids or len(title_ids) > MAX_TITLES
            or any(not re.fullmatch(r'00010001[0-9A-F]{6}4A', title) for title in title_ids)):
        raise ValueError('Select one to eight explicit Japanese game title IDs')
    selected, seen, versions, indexes = [], set(), {}, set()
    total = 0
    for row in rows:
        member = member_path(row.get('Path', ''))
        if row.get('Folder') == '+' or row.get('Attributes', '').startswith('D'):
            continue
        parsed = manual_path(member)
        if parsed is None or parsed[0] not in title_ids:
            continue
        title, version, suffix = parsed
        size = int(row['Size'])
        if (member in seen or row.get('Symbolic Link') or row.get('Hard Link')
                or row.get('Encrypted', '-') != '-' or not 0 < size <= 2*1024*1024
                or not re.fullmatch('[0-9A-Fa-f]{8}', row.get('CRC', ''))):
            raise ValueError('Unsafe, duplicate or oversized manual member')
        if title in versions and versions[title] != version:
            raise ValueError('Ambiguous captured manual version')
        versions[title] = version
        if suffix == f'html/{title}/JPN/ja/index.html':
            indexes.add(title)
        seen.add(member)
        selected.append(row)
        total += size
        if len(selected) > MAX_FILES or total > MAX_BYTES:
            raise ValueError('Selected manual pack exceeds bounds')
    if indexes != title_ids:
        raise ValueError('Requested Japanese manual index is absent')
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--listing', required=True, type=Path)
    parser.add_argument('--title-id', action='append', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sevenzip', type=Path, default=Path('C:/Program Files/7-Zip/7z.exe'))
    args = parser.parse_args(argv)
    if args.listing.stat().st_size > 512*1024*1024:
        raise ValueError('Oversized archive listing')
    if len(args.title_id) != len(set(args.title_id)):
        raise ValueError('Duplicate title request')
    titles = set(args.title_id)
    archive_sha256 = verify_archive(args.archive)
    if archive_sha256 != ARCHIVE_SHA256:
        raise ValueError('Unexpected collector archive SHA-256')
    with args.listing.open(encoding='utf-8-sig') as stream:
        selected = select_manual_members(listing_rows(stream), titles)
    files = extract_selected(args.archive.resolve(), selected, args.output, args.sevenzip)
    manifest = {'schema_version': 1, 'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1,
                'archive_sha256': archive_sha256, 'selection': 'japanese-game-manuals',
                'listing_sha256': hashlib.sha256(args.listing.read_bytes()).hexdigest(),
                'title_ids': sorted(titles), 'files': files,
                'scripts_executed': False, 'complete_original_storefront_verified': False}
    (args.output/'manifest.private.json').write_text(json.dumps(manifest, indent=2)+'\n',
                                                   encoding='utf-8', newline='\n')
    print(json.dumps({'captured_files': len(files), 'captured_bytes': sum(r['bytes'] for r in files),
                      'titles': len(titles), 'scripts_executed': False, 'shop_routes_enabled': False}))


if __name__ == '__main__':
    main()
