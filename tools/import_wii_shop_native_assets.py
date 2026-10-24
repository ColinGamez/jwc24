"""Cache three unchanged installed Shop scripts privately; no code is executed."""
import argparse
import hashlib
import json
from pathlib import Path

from jwc24.wii_shop_native_assets import RESOURCE_SHA256, SCRIPTS
from tools.audit_wii_shop_client import audit

PRIVATE = Path(__file__).resolve().parents[1]/'private'


def import_scripts(nand_root, output):
    from libWiiPy.archive import U8Archive
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Output must be a new directory beneath private/')
    report = audit(nand_root)
    row = next(r for r in report['contents'] if r['index'] == 2)
    if row['shared'] or row['sha256'] != RESOURCE_SHA256:
        raise ValueError('Expected original Shop v21 resource archive')
    root = Path(nand_root).resolve()
    path = (root/'title/00010002/48414241/content'/(row['content_id']+'.app')).resolve()
    if not path.is_relative_to(root) or path.stat().st_size != row['bytes']:
        raise ValueError('Installed resource path or size changed')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != RESOURCE_SHA256:
        raise ValueError('Installed resource changed after audit')
    archive = U8Archive()
    archive.load(data)
    selected = {}
    for name, digest in SCRIPTS.items():
        if archive.file_name_list.count(name) != 1:
            raise ValueError('Missing or ambiguous native script')
        script = archive.file_data_list[archive.file_name_list.index(name)]
        if hashlib.sha256(script).hexdigest() != digest:
            raise ValueError('Unexpected native script bytes')
        selected[name] = script
    metadata = {'schema_version': 1, 'title_id': report['title_id'],
                'title_version': report['title_version'], 'tmd_sha256': report['tmd_sha256'],
                'resource_sha256': RESOURCE_SHA256, 'nintendo_signature_verified': False,
                'files': {name: {'bytes': len(data), 'sha256': SCRIPTS[name]} for name, data in selected.items()}}
    output.mkdir(parents=True)
    for name, script in selected.items():
        (output/name).write_bytes(script)
    (output/'manifest.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8', newline='\n')
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('nand_root', type=Path)
    parser.add_argument('--output', type=Path, default=PRIVATE/'wii_shop/native-assets-v1')
    args = parser.parse_args(argv)
    report = import_scripts(args.nand_root, args.output)
    print(json.dumps({'unchanged_scripts_cached': len(report['files']), 'original_resources_private': True}))


if __name__ == '__main__':
    main()
