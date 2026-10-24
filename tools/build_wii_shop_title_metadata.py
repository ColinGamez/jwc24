"""Build private historical display metadata from checksum-checked captures."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs

from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_title_metadata import parse_detail

PRIVATE = Path(__file__).resolve().parents[1]/'private'


def build(capture_root, catalog_path, output):
    capture_root, output = Path(capture_root).resolve(), Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Output must be a new directory beneath private/')
    manifest_path = capture_root/'manifest.private.json'
    catalog_path = Path(catalog_path)
    if manifest_path.stat().st_size > 2*1024*1024 or catalog_path.stat().st_size > 32*1024*1024:
        raise ValueError('Oversized title metadata input')
    raw_manifest, raw_catalog = manifest_path.read_bytes(), catalog_path.read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1:
        raise ValueError('Unexpected captured detail source')
    catalog = Catalog(json.loads(raw_catalog)['records'])
    wanted = {row['title_id'] for row in catalog.items}
    records, rejected, conflicting = {}, Counter(), set()
    for row in manifest['files']:
        name = row['member'].rsplit('/', 1)[-1]
        base, _, query = name.partition('?')
        if base != 'B_05.jsp':
            continue
        fields = parse_qs(query, max_num_fields=20)
        ids = fields.get('titleId', [])
        if fields.get('country') != ['JP'] or len(ids) != 1 or ids[0].upper() not in wanted:
            continue
        identifier = ids[0].upper()
        digest = row['sha256']
        if not re.fullmatch('[0-9a-f]{64}', digest) or row['file'] != 'blobs/'+digest:
            raise ValueError('Unexpected captured detail path')
        local = (capture_root/row['file']).resolve()
        if not local.is_relative_to(capture_root) or local.stat().st_size > 2*1024*1024:
            raise ValueError('Captured detail outside pack bounds')
        data = local.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Captured detail fingerprint mismatch')
        try:
            value = parse_detail(data, identifier)
        except (ValueError, UnicodeError) as error:
            rejected['undecodable_utf8' if isinstance(error, UnicodeError) else str(error)] += 1
            continue
        if identifier in records and records[identifier] != value:
            conflicting.add(identifier)
        records[identifier] = value
    for identifier in conflicting:
        records.pop(identifier, None)
    document = {'schema_version': 1, 'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1,
                'capture_manifest_sha256': hashlib.sha256(raw_manifest).hexdigest(),
                'catalog_sha256': hashlib.sha256(raw_catalog).hexdigest(), 'records': records}
    output.mkdir(parents=True)
    (output/'metadata.json').write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    return {'catalog_titles': len(wanted), 'verified_historical_titles': len(records),
            'verified_historical_points': sum(row['points'] is not None for row in records.values()),
            'conflicting_titles_excluded': len(conflicting), 'rejected_captures': dict(rejected),
            'catalog_titles_without_verified_capture': len(wanted-set(records)),
            'current_prices_or_ownership_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=PRIVATE/'wii_shop/frontend-capture-v1')
    parser.add_argument('--catalog', type=Path, default=PRIVATE/'wii_shop/mariocube-catalog-ids.json')
    parser.add_argument('--output', type=Path, default=PRIVATE/'wii_shop/title-metadata-v2')
    args = parser.parse_args(argv)
    print(json.dumps(build(args.capture, args.catalog, args.output)))


if __name__ == '__main__':
    main()
