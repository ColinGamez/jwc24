"""Catalog-wide, source-bound JPEG cache; no arbitrary URL proxying."""
import hashlib
import json
from pathlib import Path
import re
import threading
from urllib.request import Request, build_opener

from tools.asset_publication import publish_assets
from tools.cache_demae_directory_images import validate_url, validate_jpeg, ProviderRedirects


def image_index(catalogs):
    result = {}
    prefectures = set()
    for catalog in catalogs:
        prefecture = catalog.get('prefecture_id')
        if (catalog.get('provider') != 'hotpepper' or not isinstance(prefecture, str)
                or not re.fullmatch(r'JP-(0[1-9]|[1-3][0-9]|4[0-7])', prefecture)
                or prefecture in prefectures):
            raise ValueError('Invalid or repeated source prefecture')
        prefectures.add(prefecture)
        rows = catalog.get('restaurants')
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError('Invalid image source catalog')
        for row in rows:
            identifier = row.get('id') if isinstance(row, dict) else None
            if (not isinstance(identifier, str) or not re.fullmatch(r'hotpepper:J[0-9]{9}', identifier)
                    or identifier in result):
                raise ValueError('Invalid or duplicate restaurant image identity')
            url = row.get('logo_url')
            field = 'logo_url'
            if not url or url == 'https://imgfp.hotp.jp/SYS/cmn/images/common/diary/custom/m30_img_noimage.gif':
                url = row.get('photo_url')
                field = 'photo_url'
            # Missing source images stay missing; no substitute restaurant art.
            if url:
                validate_url(url)
            result[identifier] = {'prefecture': prefecture, 'source_url': url or None, 'source_field': field}
    return result


class DirectoryImageStore:
    """Fetch only known source images and persist original bytes on demand.

    One store-level lock bounds provider requests to one at a time. Failed
    downloads do not overwrite a previous cache entry. No user data is sent.
    """
    def __init__(self, catalogs, directory, *, fetch=None):
        self.index = image_index(catalogs)
        self.directory = Path(directory)
        self._lock = threading.Lock()
        self._fetch = fetch or self._download

    @staticmethod
    def _download(url):
        opener = build_opener(ProviderRedirects())
        with opener.open(Request(validate_url(url), headers={'User-Agent': 'JWC24 restaurant image cache'}),
                         timeout=10) as response:
            return response.read(256 * 1024 + 1)

    def get(self, identifier):
        source = self.index.get(identifier)
        if source is None or source['source_url'] is None:
            return None
        filename = identifier.split(':')[1] + '.jpg'
        path = self.directory / filename
        metadata_path = path.with_suffix('.json')
        with self._lock:
            if path.exists() and metadata_path.exists():
                metadata = json.loads(metadata_path.read_bytes())
                data = path.read_bytes()
                if (metadata.get('restaurant_id') != identifier
                        or metadata.get('source_url') != source['source_url']
                        or metadata.get('sha256') != hashlib.sha256(data).hexdigest()):
                    raise ValueError('Restaurant image cache no longer matches its source')
                validate_jpeg(data)
                return data
            data = self._fetch(source['source_url'])
            width, height = validate_jpeg(data)
            metadata = {**source, 'restaurant_id': identifier,
                        'sha256': hashlib.sha256(data).hexdigest(), 'width': width, 'height': height,
                        'unmodified_source_image': True}
            publish_assets([(path, data), (metadata_path, json.dumps(metadata, indent=2).encode())])
            return data
