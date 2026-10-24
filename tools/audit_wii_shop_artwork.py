"""Compare the private web artwork pack against TMD-checked installed resources.

Read-only: emits filenames, sizes and hashes, never original bytes or credentials.
A match establishes equality to the installed resource, not a verified Nintendo
signature or provenance for the rest of a third-party web page.
"""
import argparse
import hashlib
import json
from pathlib import Path

from jwc24.wii_shop_artwork import Artwork
from tools.audit_wii_shop_client import audit


def compare_files(web_files, native_files):
    """Compare complete bytes, regardless of filenames, excluding empty entries."""
    by_digest = {}
    for name, data in native_files:
        if data:
            by_digest.setdefault(hashlib.sha256(data).hexdigest(), []).append((name, data))
    rows = []
    for path, data in sorted(web_files.items()):
        digest = hashlib.sha256(data).hexdigest()
        matches = sorted(name for name, candidate in by_digest.get(digest, []) if candidate == data)
        rows.append({'web_path': path, 'bytes': len(data), 'sha256': digest,
                     'installed_byte_matches': matches})
    return rows


def audit_artwork(nand_root, artwork_root):
    from libWiiPy.archive import U8Archive
    installed = audit(nand_root)
    resource = next(row for row in installed['contents'] if row['index'] == 2)
    if resource['shared']:
        raise ValueError('Unexpected shared Shop resource archive')
    root = Path(nand_root).resolve()
    path = (root/'title/00010002/48414241/content'/(resource['content_id']+'.app')).resolve()
    if not path.is_relative_to(root) or path.stat().st_size != resource['bytes']:
        raise ValueError('Resource path or size changed after content audit')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != resource['sha256']:
        raise ValueError('Resource changed after content audit')
    native = U8Archive()
    native.load(data)
    web = Artwork(artwork_root)
    rows = compare_files(web.files, zip(native.file_name_list, native.file_data_list))
    matched = sum(bool(row['installed_byte_matches']) for row in rows)
    return {'schema_version': 1, 'title_id': installed['title_id'],
            'title_version': installed['title_version'],
            'tmd_sha256': installed['tmd_sha256'],
            'resource_sha256': resource['sha256'],
            'installed_content_hashes_match_tmd': True,
            'nintendo_signature_verified': False,
            'web_resources': len(rows), 'installed_byte_matched_resources': matched,
            'unmatched_resources': len(rows)-matched,
            'unmatched_does_not_mean_inauthentic': True,
            'complete_original_storefront_verified': False,
            'files': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('nand_root', type=Path)
    parser.add_argument('artwork_root', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit_artwork(args.nand_root, args.artwork_root), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
