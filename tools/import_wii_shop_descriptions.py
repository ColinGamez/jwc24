"""Recover title-bound original B06 pages and only their referenced screenshots.

Two bounded 7-Zip streams preserve original bytes under private/. This never
extracts title binaries, manual packs or unreferenced CCS files, executes scripts,
changes Shop routes, or contacts an external service.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_descriptions import (
    ARCHIVE_SHA256, HOST, MAX_BYTES, MAX_FILES, MAX_TITLES, VALIDATION_REVISION,
    b05_description_link, image_info, page_identity, parse_description, read_blob,
)
from tools.import_wii_shop_frontend_capture import extract_selected, verify_archive
from tools.inspect_wii_shop_frontend_backup import listing_rows, member_path

PRIVATE = Path(__file__).resolve().parents[1] / 'private'
STAGE_BOUND = 128 * 1024 * 1024


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_row(row, bound):
    size = int(row['Size'])
    if (row.get('Symbolic Link') or row.get('Hard Link') or row.get('Encrypted', '-') != '-'
            or not 0 < size <= bound or not re.fullmatch('[0-9A-Fa-f]{8}', row.get('CRC', ''))):
        raise ValueError('Unsafe, linked, encrypted or oversized description member')
    return size


def select_source_pages(rows, title_ids):
    if (not title_ids or len(title_ids) > MAX_TITLES
            or any(not isinstance(i, str) or not re.fullmatch('[0-9A-F]{16}', i) for i in title_ids)):
        raise ValueError('Expected bounded catalog title IDs')
    selected, seen, identities, total = [], set(), set(), 0
    for row in rows:
        member = member_path(row.get('Path', ''))
        if row.get('Folder') == '+' or row.get('Attributes', '').startswith('D'):
            continue
        identity = page_identity(member)
        if not identity or identity[1] not in title_ids:
            continue
        size = _safe_row(row, 2 * 1024 * 1024)
        if member in seen or identity in identities:
            raise ValueError('Duplicate or ambiguous description source-page identity')
        selected.append(row)
        seen.add(member)
        identities.add(identity)
        total += size
        if len(selected) > MAX_TITLES * 2 or total > STAGE_BOUND:
            raise ValueError('Description source selection exceeds bounds')
    return selected


def select_screenshots(rows, requested):
    if (len(requested) > MAX_TITLES * 2 or any(not re.fullmatch(
            re.escape(HOST) + r'/oss/ccs/[A-Fa-f0-9]{16}/FFFD[0-9A-F]{4}', member)
            for member in requested)):
        raise ValueError('Expected only exact source-referenced screenshot members')
    selected, seen, total = [], set(), 0
    for row in rows:
        member = member_path(row.get('Path', ''))
        if member not in requested or row.get('Folder') == '+' or row.get('Attributes', '').startswith('D'):
            continue
        size = _safe_row(row, 512 * 1024)
        if member in seen:
            raise ValueError('Duplicate screenshot member')
        seen.add(member)
        selected.append(row)
        total += size
        if len(selected) > MAX_TITLES * 2 or total > STAGE_BOUND:
            raise ValueError('Description screenshot selection exceeds bounds')
    return selected


def _reuse_sources(source_pack, selected, output, catalog_digest, listing_digest):
    source_pack = Path(source_pack).resolve()
    manifest_path = source_pack / 'manifest.private.json'
    if not source_pack.is_relative_to(PRIVATE.resolve()) or manifest_path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Source reuse requires a bounded existing private description pack')
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if (manifest.get('schema_version') != 1 or manifest.get('source') != SOURCE
            or manifest.get('archive_sha1') != ARCHIVE_SHA1
            or manifest.get('archive_sha256') != ARCHIVE_SHA256
            or manifest.get('catalog_sha256') != catalog_digest
            or manifest.get('listing_sha256') != listing_digest
            or manifest.get('selection') != 'japan-b06-descriptions'
            or not isinstance(manifest.get('files'), list) or len(manifest['files']) > MAX_FILES):
        raise ValueError('Reusable source pack archive/catalog/listing binding differs')
    files = [row for row in manifest['files'] if page_identity(row.get('member', ''))]
    by_member = {row['member']: row for row in files}
    if len(by_member) != len(files) or set(by_member) != {member_path(row['Path']) for row in selected}:
        raise ValueError('Reusable source selection differs from pinned archive listing')
    blobs = output / 'source-pages' / 'blobs'
    blobs.mkdir(parents=True)
    for expected in selected:
        row = by_member[member_path(expected['Path'])]
        if row['bytes'] != int(expected['Size']) or row.get('crc32') != expected['CRC'].upper():
            raise ValueError('Reusable source size/CRC differs from archive listing')
        data = read_blob(source_pack, row, 'source-pages')
        (blobs / row['sha256']).write_bytes(data)
    return files, hashlib.sha256(raw).hexdigest()


def import_descriptions(archive, listing, catalog_path, output, sevenzip, *, source_pack=None):
    archive, listing, catalog_path = map(Path, (archive, listing, catalog_path))
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Output must be a new directory beneath private/')
    if listing.stat().st_size > 512 * 1024 * 1024 or catalog_path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Description input exceeds bounds')
    archive_sha256 = verify_archive(archive)
    if archive_sha256 != ARCHIVE_SHA256:
        raise ValueError('Unexpected collector archive SHA-256')
    catalog_bytes = catalog_path.read_bytes()
    catalog_digest = hashlib.sha256(catalog_bytes).hexdigest()
    listing_digest = file_sha256(listing)
    catalog = Catalog(json.loads(catalog_bytes)['records'])
    titles = {row['title_id'] for row in catalog.items}
    with listing.open(encoding='utf-8-sig') as stream:
        source_rows = select_source_pages(listing_rows(stream), titles)
    if not source_rows:
        raise ValueError('No matching Japanese description source pages')
    output.mkdir(parents=True)
    reused_manifest = None
    if source_pack is None:
        source_files = extract_selected(archive.resolve(), source_rows, output / 'source-pages', sevenzip)
        source_files = [dict(row, file='source-pages/' + row['file']) for row in source_files]
    else:
        source_files, reused_manifest = _reuse_sources(source_pack, source_rows, output, catalog_digest, listing_digest)
    by_identity = {page_identity(row['member']): row for row in source_files}
    accepted, excluded, requested = {}, {}, set()
    for identifier in sorted(titles):
        detail = by_identity.get(('B_05.jsp', identifier))
        description = by_identity.get(('B_06.jsp', identifier))
        if detail is None or description is None:
            excluded[identifier] = {'reason': 'missing-b05-or-b06-source-page'}
            continue
        try:
            proof = b05_description_link(read_blob(output, detail, 'source-pages'), identifier)
            parsed = parse_description(read_blob(output, description, 'source-pages'), identifier)
        except (ValueError, UnicodeError) as error:
            excluded[identifier] = {'reason': str(error)}
            continue
        accepted[identifier] = {'detail_member': detail['member'], 'detail_proof': proof,
                                'description_member': description['member'],
                                'description_sha256': description['sha256'],
                                'display_title_differs': parsed['title'] != proof['title'],
                                'screenshots': parsed['screenshots'],
                                'shared_paths': parsed['shared_paths'],
                                'content_activities': parsed['content_activities'],
                                'back_button': parsed['back_button']}
        requested.update(HOST + path for path in parsed['screenshots'])
    if not accepted:
        raise ValueError('No source-bound B06 description pages passed validation')
    with listing.open(encoding='utf-8-sig') as stream:
        image_rows = select_screenshots(listing_rows(stream), requested)
    image_files = extract_selected(archive.resolve(), image_rows, output / 'screenshots', sevenzip) if image_rows else []
    valid_images, invalid_images = {}, set()
    for row in image_files:
        row = dict(row, file='screenshots/' + row['file'])
        data = read_blob(output, row, 'screenshots')
        try:
            info = image_info(data)
        except (OSError, ValueError):
            invalid_images.add(row['member'])
            continue
        valid_images[row['member']] = dict(row, image_info=info)
    for identifier, row in list(accepted.items()):
        missing = sorted(path for path in row['screenshots'] if HOST + path not in valid_images)
        if missing:
            excluded[identifier] = {'reason': 'missing-or-invalid-original-screenshot', 'paths': missing}
            del accepted[identifier]
    # Keep validated image records only when at least one eligible original page references them.
    retained = {HOST + path for row in accepted.values() for path in row['screenshots']}
    files = source_files + [row for member, row in valid_images.items() if member in retained]
    total = sum(row['bytes'] for row in files)
    if len(files) > MAX_FILES or total > MAX_BYTES:
        raise ValueError('Description pack exceeds final bounds')
    manifest = {'schema_version': 1, 'validation_revision': VALIDATION_REVISION,
                'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1,
                'archive_sha256': archive_sha256, 'selection': 'japan-b06-descriptions',
                'catalog_sha256': catalog_digest, 'listing_sha256': listing_digest,
                'files': files, 'titles': accepted, 'excluded': excluded,
                'requested_screenshot_count': len(requested),
                'absent_screenshot_count': len(requested - set(valid_images) - invalid_images),
                'invalid_screenshot_count': len(invalid_images),
                'scripts_executed': False, 'complete_original_storefront_verified': False}
    if reused_manifest is not None:
        manifest['source_stage_reused_from_manifest_sha256'] = reused_manifest
    (output / 'manifest.private.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                                encoding='utf-8', newline='\n')
    return {'catalog_titles': len(titles), 'source_pages': len(source_files),
            'eligible_descriptions': len(accepted), 'excluded_descriptions': len(excluded),
            'screenshot_images': len(retained), 'captured_bytes': total,
            'absent_screenshots': manifest['absent_screenshot_count'],
            'invalid_screenshots': len(invalid_images),
            'b05_b06_display_title_differences': sum(r['display_title_differs'] for r in accepted.values()),
            'scripts_executed': False, 'routes_enabled': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--listing', required=True, type=Path)
    parser.add_argument('--catalog', type=Path, default=PRIVATE / 'wii_shop/mariocube-catalog-ids.json')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-pack', type=Path, help='Reuse and reverify only source pages from a completed private pack')
    parser.add_argument('--sevenzip', type=Path, default=Path('C:/Program Files/7-Zip/7z.exe'))
    args = parser.parse_args(argv)
    print(json.dumps(import_descriptions(args.archive, args.listing, args.catalog, args.output,
                                        args.sevenzip, source_pack=args.source_pack)))


if __name__ == '__main__':
    main()
