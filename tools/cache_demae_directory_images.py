"""Cache unmodified source JPEGs for the explicit read-only restaurant preview."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.asset_publication import publish_assets


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'imgfp.hotp.jp'
            or parsed.query or parsed.fragment or not parsed.path.startswith('/IMGH/')
            or not parsed.path.lower().endswith('.jpg')):
        raise ValueError('Expected an HTTPS Hot Pepper source JPEG')
    return url


def validate_jpeg(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= 256 * 1024:
        raise ValueError('Source image exceeds preview limit')
    with Image.open(BytesIO(data)) as image:
        if image.format != 'JPEG' or not 0 < image.width <= 1024 or not 0 < image.height <= 1024:
            raise ValueError('Expected a bounded JPEG image')
        dimensions = image.size
        image.verify()
    return dimensions


class ProviderRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def load_images(directory, allowed_ids):
    """Validate immutable files before a local server starts listening."""
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    if (manifest.get('schema_version') != 1 or manifest.get('provider') != 'hotpepper'
            or manifest.get('unmodified_source_images') is not True
            or not isinstance(manifest.get('images'), list) or not 1 <= len(manifest['images']) <= 25):
        raise ValueError('Invalid source-image cache manifest')
    images = {}
    for row in manifest['images']:
        identifier = row['restaurant_id']
        if (not isinstance(identifier, str) or not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier)
                or identifier not in allowed_ids or identifier in images):
            raise ValueError('Image cache identity is outside explicit preview selection')
        filename = identifier.split(':')[1] + '.jpg'
        if row['filename'] != filename:
            raise ValueError('Image filename does not match source identity')
        validate_url(row['source_url'])
        data = (directory / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Image cache fingerprint mismatch')
        if validate_jpeg(data) != (row['width'], row['height']):
            raise ValueError('Image cache dimensions mismatch')
        images[identifier] = data
    return images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output_directory.resolve().is_relative_to(private.resolve()):
        parser.error('Image cache must remain private')
    catalog_bytes = args.catalog.read_bytes()
    catalog = json.loads(catalog_bytes)
    if catalog.get('provider') != 'hotpepper':
        parser.error('Expected a Hot Pepper source catalog')
    rows = {row['id']: row for row in catalog['restaurants']}
    selections = json.loads(args.selection.read_bytes())
    identifiers = list(dict.fromkeys(identifier for group in selections for identifier in group['restaurant_ids']))
    if not 1 <= len(identifiers) <= 25:
        parser.error('Expected a bounded explicit preview selection')
    opener = build_opener(ProviderRedirects())
    assets, records = [], []
    for identifier in identifiers:
        if not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier) or identifier not in rows:
            raise ValueError('Image identity is absent from source catalog')
        url = validate_url(rows[identifier]['logo_url'])
        with opener.open(Request(url, headers={'User-Agent': 'JWC24 directory preview'}), timeout=15) as response:
            data = response.read(256 * 1024 + 1)
        width, height = validate_jpeg(data)
        filename = identifier.split(':')[1] + '.jpg'
        assets.append((args.output_directory / filename, data))
        records.append({'restaurant_id': identifier, 'filename': filename, 'source_url': url,
                        'sha256': hashlib.sha256(data).hexdigest(), 'width': width, 'height': height})
    manifest = {'schema_version': 1, 'provider': 'hotpepper',
                'catalog_sha256': hashlib.sha256(catalog_bytes).hexdigest(),
                'unmodified_source_images': True, 'images': records}
    assets.append((args.output_directory / 'manifest.json', json.dumps(manifest, indent=2).encode()))
    publish_assets(assets, source_check=(args.catalog, catalog_bytes))
    print(f'Cached {len(records)} validated source JPEGs; native image routing remains unverified')


if __name__ == '__main__':
    main()
