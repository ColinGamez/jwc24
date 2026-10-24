"""Cache original Shop title images by source-reported Japan catalog IDs.

Fetches only the archive's FFFD0001 image route, never title binaries. Missing
or invalid images stay absent; originals are cached privately with provenance.
"""
import argparse
import concurrent.futures
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jwc24.wii_shop_server import catalog_from_file

ORIGIN = 'https://wiishopchannel.net'
PRIVATE = Path(__file__).resolve().parents[1]/'private'


def image_info(data):
    from PIL import Image
    if not data or len(data) > 512*1024:
        raise ValueError('Title image exceeds byte bounds')
    with Image.open(BytesIO(data)) as image:
        if image.format not in ('GIF', 'PNG', 'JPEG', 'BMP') or not (0 < image.width <= 1024 and 0 < image.height <= 1024):
            raise ValueError('Unexpected title image format/dimensions')
        result = {'format': image.format, 'width': image.width, 'height': image.height}
        image.verify()
    return result


def fetch(identifier):
    if not isinstance(identifier, str) or not re.fullmatch('[0-9A-F]{16}', identifier):
        raise ValueError('Expected validated catalog title ID')
    url = ORIGIN+'/oss/ccs/'+identifier+'/FFFD0001'
    time.sleep(0.08)
    try:
        with urlopen(Request(url, headers={'User-Agent': 'JWC24-artwork-research/1'}), timeout=15) as response:
            if response.url != url:
                raise ValueError('Title image redirect changed source')
            data = response.read(512*1024+1)
        info = image_info(data)
        return identifier, data, dict(info, url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    except HTTPError as error:
        return identifier, None, {'status': 'http-'+str(error.code)}
    except (OSError, URLError, ValueError):
        return identifier, None, {'status': 'unavailable-or-invalid-image'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=PRIVATE/'wii_shop/mariocube-catalog-ids.json')
    parser.add_argument('--output', type=Path, default=PRIVATE/'wii_shop/title-artwork-v1')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(PRIVATE.resolve()):
        parser.error('Output must be a new directory under private/')
    catalog, digest = catalog_from_file(args.catalog)
    output.mkdir(parents=True)
    images, missing = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for identifier, data, row in pool.map(fetch, [item['title_id'] for item in catalog.items]):
            if data is None:
                missing[identifier] = row
            else:
                filename = identifier+'.img'
                (output/filename).write_bytes(data)
                images[identifier] = dict(row, file=filename)
    report = {'source': ORIGIN, 'catalog_sha256': digest, 'images': images, 'missing': missing}
    (output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'catalog_titles': len(catalog.items), 'title_images': len(images),
                      'missing_or_invalid': len(missing), 'title_binaries_downloaded': False}))


if __name__ == '__main__':
    main()
