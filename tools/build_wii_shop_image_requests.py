"""Resolve separate title icons/Photos from captured page references, without JS."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs

from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_server import catalog_from_file
from jwc24.wii_shop_title_metadata import DetailFields, parse_detail

PRIVATE = Path(__file__).resolve().parents[1]/'private'


def resolve_photo(data, identifier, metadata):
    if parse_detail(data, identifier) != metadata:
        raise ValueError('Historical metadata differs from captured source fields')
    parser = DetailFields()
    parser.feed(data.decode('utf-8-sig'))
    if len(parser.photo_sources) != 1:
        raise ValueError('Missing or ambiguous original Photo element')
    match = re.fullmatch(r'/oss/ccs/([A-Fa-f0-9]{16})/(FFFD[A-Fa-f0-9]{4})', parser.photo_sources[0])
    if not match or match[1].upper() != identifier:
        raise ValueError('Captured Photo is not bound to its title')
    return {'member':'oss-auth.shop.wii.com'+parser.photo_sources[0],
            'reference_detail_sha256':metadata['capture_sha256']}


def resolve_catalog(data, wanted):
    from jwc24.wii_shop_artwork import Tree
    source = data.decode('utf-8-sig')
    source = re.sub(r'<script\b[^>]*>.*?</script\s*>', '', source, flags=re.I|re.S)
    source = re.sub(r'<!--.*?-->', '', source, flags=re.S)
    body = source[source.lower().index('<body'):source.lower().rfind('</body>')]
    references = {}
    for node in Tree(body).root.walk():
        if not re.fullmatch(r'panel\d+', node.attrs.get('id','')):
            continue
        targets, images = set(), set()
        for child in node.walk():
            if child.tag == 'a':
                match = re.search(r'B_05\.jsp\?[^\x27\x22]*?titleId=([A-Fa-f0-9]{16})(?=&|[\x27\x22)]|$)', child.attrs.get('href',''))
                if match: targets.add(match[1].upper())
            if child.tag == 'img':
                match = re.fullmatch(r'/oss/ccs/([A-Fa-f0-9]{16})/(FFFD[A-Fa-f0-9]{4})',child.attrs.get('src',''))
                if match: images.add((match[1].upper(), child.attrs['src']))
        if len(targets) != 1 or len(images) != 1:
            continue
        identifier = next(iter(targets))
        image_id, image_url = next(iter(images))
        if identifier != image_id or identifier not in wanted:
            continue
        value = {'member':'oss-auth.shop.wii.com'+image_url,
                 'reference_catalog_sha256':hashlib.sha256(data).hexdigest()}
        if identifier in references and references[identifier]['member'] != value['member']:
            raise ValueError('Conflicting catalog image references in one page')
        references[identifier] = value
    return references


def build(capture_root, catalog_path, metadata_path, output, catalog_capture):
    capture_root, output = Path(capture_root).resolve(), Path(output).resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Output must be a new file beneath private/')
    manifest_path = capture_root/'manifest.private.json'
    if manifest_path.stat().st_size > 2*1024*1024:
        raise ValueError('Oversized captured page manifest')
    raw_manifest = manifest_path.read_bytes()
    manifest_digest = hashlib.sha256(raw_manifest).hexdigest()
    manifest = json.loads(raw_manifest)
    if manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1:
        raise ValueError('Unexpected image-reference source')
    catalog, digest = catalog_from_file(Path(catalog_path), metadata_path, manifest_digest)
    wanted = {item['title_id'] for item in catalog.items}
    requests, details = {}, {}
    references = alternate = 0
    for item in catalog.items:
        identifier = item['title_id']
        source = item.get('historical_metadata')
        if source:
            local = (capture_root/'blobs'/source['capture_sha256']).resolve()
            if not local.is_relative_to(capture_root) or local.stat().st_size > 2*1024*1024:
                raise ValueError('Captured image-reference page outside bounds')
            data = local.read_bytes()
            reference = resolve_photo(data, identifier, source)
            references += 1
            alternate += not reference['member'].endswith('/FFFD0001')
            details[identifier] = reference
    catalog_capture = Path(catalog_capture).resolve()
    catalog_manifest = catalog_capture/'manifest.private.json'
    if catalog_manifest.stat().st_size > 2*1024*1024:
        raise ValueError('Oversized catalog capture manifest')
    raw_catalog_manifest = catalog_manifest.read_bytes()
    captured_pages = json.loads(raw_catalog_manifest)
    if captured_pages.get('source') != SOURCE or captured_pages.get('archive_sha1') != ARCHIVE_SHA1:
        raise ValueError('Unexpected catalog image-reference source')
    conflicts = set()
    for row in captured_pages['files']:
        base, _, query = row['member'].rsplit('/',1)[-1].partition('?')
        if base != 'B_04.jsp' or parse_qs(query).get('country') != ['JP']:
            raise ValueError('Expected Japan-region catalog captures')
        fingerprint = row['sha256']
        if not re.fullmatch('[0-9a-f]{64}', fingerprint) or row['file'] != 'blobs/'+fingerprint:
            raise ValueError('Unexpected catalog reference file')
        local = (catalog_capture/row['file']).resolve()
        if not local.is_relative_to(catalog_capture) or local.stat().st_size > 8*1024*1024:
            raise ValueError('Catalog reference page outside bounds')
        data = local.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != fingerprint:
            raise ValueError('Catalog reference fingerprint mismatch')
        for identifier, reference in resolve_catalog(data, wanted).items():
            if identifier in requests and requests[identifier]['member'] != reference['member']:
                conflicts.add(identifier)
            requests[identifier] = reference
    for identifier in conflicts:
        requests.pop(identifier,None)
    if not requests:
        raise ValueError('No ID-paired catalog image references')
    document = {'schema_version':1,'source':SOURCE,'archive_sha1':ARCHIVE_SHA1,
                'catalog_sha256':digest,'metadata_sha256':catalog.title_metadata.digest,
                'capture_manifest_sha256':manifest_digest,
                'catalog_capture_manifest_sha256':hashlib.sha256(raw_catalog_manifest).hexdigest(),
                'images':requests,'detail_images':details}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(document,indent=2)+'\n')
    return {'catalog_image_references':len(requests),'captured_photo_references':references,
            'alternate_detail_image_file_ids':alternate,'conflicting_catalog_references_excluded':len(conflicts),
            'titles_without_catalog_reference':len(wanted-set(requests))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,default=PRIVATE/'wii_shop/frontend-capture-v1')
    parser.add_argument('--catalog',type=Path,default=PRIVATE/'wii_shop/mariocube-catalog-ids.json')
    parser.add_argument('--title-metadata',type=Path,default=PRIVATE/'wii_shop/title-metadata-v2/metadata.json')
    parser.add_argument('--catalog-capture',type=Path,default=PRIVATE/'wii_shop/frontend-japan-catalog-v2')
    parser.add_argument('--output',type=Path,default=PRIVATE/'wii_shop/title-image-requests-v3.json')
    args=parser.parse_args(argv)
    print(json.dumps(build(args.capture,args.catalog,args.title_metadata,args.output,args.catalog_capture)))


if __name__ == '__main__':
    main()
