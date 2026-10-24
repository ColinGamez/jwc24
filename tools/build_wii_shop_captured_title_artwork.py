"""Build separate private catalog/detail image caches from unchanged captures."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_server import catalog_from_file
from tools.import_wii_shop_title_artwork import image_info

PRIVATE = Path(__file__).resolve().parents[1]/'private'


def build(capture_root, catalog_path, output, requests_path):
    capture_root, output = Path(capture_root).resolve(), Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Output must be a new directory beneath private/')
    path = capture_root/'manifest.private.json'
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('Oversized captured image manifest')
    raw_manifest = path.read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1:
        raise ValueError('Unexpected historical image source')
    catalog, digest = catalog_from_file(Path(catalog_path))
    wanted = {item['title_id'] for item in catalog.items}
    requests_path = Path(requests_path)
    if requests_path.stat().st_size > 2*1024*1024:
        raise ValueError('Oversized image reference file')
    raw_requests = requests_path.read_bytes()
    requests = json.loads(raw_requests)
    if (requests.get('source') != SOURCE or requests.get('archive_sha1') != ARCHIVE_SHA1
            or requests.get('catalog_sha256') != digest
            or any(not set(requests[role]) <= wanted for role in ('images', 'detail_images'))):
        raise ValueError('Image reference source/catalog mismatch')
    captured = {}
    for row in manifest['files']:
        if row['member'] in captured:
            raise ValueError('Duplicate captured image member')
        captured[row['member']] = row
    document = {'source':SOURCE, 'archive_sha1':ARCHIVE_SHA1,
                'capture_manifest_sha256':hashlib.sha256(raw_manifest).hexdigest(),
                'image_requests_sha256':hashlib.sha256(raw_requests).hexdigest(),
                'catalog_sha256':digest}
    payloads, total = {}, 0
    for role, proof, suffix in (('images','reference_catalog_sha256','.img'),
                                ('detail_images','reference_detail_sha256','.detail.img')):
        images = {}
        missing = {identifier:{'status':'no-verified-page-reference'} for identifier in wanted}
        for identifier, reference in requests[role].items():
            match = re.fullmatch(r'oss-auth\.shop\.wii\.com/oss/ccs/([A-Fa-f0-9]{16})/(FFFD[A-Fa-f0-9]{4})', reference['member'])
            if (not match or match[1].upper() != identifier
                    or not re.fullmatch('[0-9a-f]{64}',reference.get(proof) or '')):
                raise ValueError('Image lacks title-bound original page reference')
            row = captured.get(reference['member'])
            if not row:
                missing[identifier] = {'status':'referenced-image-not-captured'}
                continue
            fingerprint = row['sha256']
            if not re.fullmatch('[0-9a-f]{64}', fingerprint) or row['file'] != 'blobs/'+fingerprint:
                raise ValueError('Unexpected captured title image path')
            local = (capture_root/row['file']).resolve()
            if not local.is_relative_to(capture_root) or not 0 < local.stat().st_size <= 512*1024:
                raise ValueError('Captured title image outside bounds')
            data = local.read_bytes()
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != fingerprint:
                raise ValueError('Captured title image fingerprint mismatch')
            try:
                info = image_info(data)
            except (OSError, ValueError):
                missing[identifier] = {'status':'invalid-captured-image'}
                continue
            total += len(data)
            if total > 100*1024*1024:
                raise ValueError('Captured title artwork exceeds bounds')
            filename = identifier+suffix
            images[identifier] = dict(info, file=filename, bytes=len(data), sha256=fingerprint,
                                      member=row['member'], **{proof:reference[proof]})
            payloads[filename] = data
            missing.pop(identifier, None)
        document[role] = images
        document['missing' if role == 'images' else 'missing_detail_images'] = missing
    if not document['images'] or not document['detail_images']:
        raise ValueError('No valid historical images for both roles')
    output.mkdir(parents=True)
    for filename, data in payloads.items():
        (output/filename).write_bytes(data)
    (output/'manifest.json').write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'catalog_titles':len(wanted),'catalog_images':len(document['images']),
            'detail_images':len(document['detail_images']),
            'missing_catalog_images':len(document['missing']),
            'missing_detail_images':len(document['missing_detail_images']),
            'original_image_bytes_preserved':True,'generated_replacement_images':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,default=PRIVATE/'wii_shop/frontend-title-images-v3')
    parser.add_argument('--catalog',type=Path,default=PRIVATE/'wii_shop/mariocube-catalog-ids.json')
    parser.add_argument('--output',type=Path,default=PRIVATE/'wii_shop/title-artwork-v4')
    parser.add_argument('--image-requests',type=Path,default=PRIVATE/'wii_shop/title-image-requests-v3.json')
    args = parser.parse_args(argv)
    print(json.dumps(build(args.capture,args.catalog,args.output,args.image_requests)))


if __name__ == '__main__':
    main()
