"""Validate historical detail/controller dependencies and write a private index."""
import argparse
import json
from pathlib import Path

from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE, CapturedScripts
from jwc24.wii_shop_captured_titles import CapturedTitlePages, INDEX_REVISION
from jwc24.wii_shop_server import catalog_from_file

PRIVATE = Path(__file__).resolve().parents[1]/'private'


def build(capture_root, support_root, catalog_path, metadata_path, output):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Output must be a new file beneath private/')
    capture = CapturedScripts(capture_root)
    catalog,_ = catalog_from_file(Path(catalog_path),metadata_path,capture.manifest_sha256)
    pages = CapturedTitlePages(capture,catalog.title_metadata,support_root,{row['title_id'] for row in catalog.items})
    document = dict(validation_revision=INDEX_REVISION,source=SOURCE,archive_sha1=ARCHIVE_SHA1,
                    capture_manifest_sha256=capture.manifest_sha256,metadata_sha256=catalog.title_metadata.digest,
                    support_manifest_sha256=pages.support_manifest_sha256,
                    details={key:row['sha256'] for key,row in pages.detail_rows.items()},
                    controllers={key:row['sha256'] for key,row in pages.controller_rows.items()},
                    excluded_details=pages.excluded_details,excluded_controllers=pages.excluded_controllers)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(document,indent=2)+'\n')
    return {'captured_details':len(pages.detail_rows),'captured_controllers':len(pages.controller_rows),
            'excluded_details':len(pages.excluded_details),'excluded_controllers':len(pages.excluded_controllers)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,default=PRIVATE/'wii_shop/frontend-capture-v1')
    parser.add_argument('--support',type=Path,default=PRIVATE/'wii_shop/frontend-title-support-v1')
    parser.add_argument('--catalog',type=Path,default=PRIVATE/'wii_shop/mariocube-catalog-ids.json')
    parser.add_argument('--metadata',type=Path,default=PRIVATE/'wii_shop/title-metadata-v2/metadata.json')
    parser.add_argument('--output',type=Path,default=PRIVATE/'wii_shop/title-pages-v2/index.json')
    args = parser.parse_args(argv)
    print(json.dumps(build(args.capture,args.support,args.catalog,args.metadata,args.output)))


if __name__ == '__main__':
    main()
