"""Load a bounded private cache of archived, title-ID-addressed Shop images."""
import hashlib
import json
from pathlib import Path
import re


class TitleArtwork:
    def __init__(self, root, catalog_digest=None):
        self.images = {}
        root = Path(root).resolve()
        path = root/'manifest.json'
        if not path.is_file():
            return
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized title artwork manifest')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if (manifest.get('source') != 'https://wiishopchannel.net'
                or len(manifest['images']) > 20000
                or (catalog_digest is not None and manifest.get('catalog_sha256') != catalog_digest)):
            raise ValueError('Title artwork source/catalog differs')
        total = 0
        for identifier, row in manifest['images'].items():
            if (not re.fullmatch('[0-9A-F]{16}', identifier) or row['file'] != identifier+'.img'
                    or row['format'] not in ('GIF', 'PNG', 'JPEG')
                    or row['url'] != 'https://wiishopchannel.net/oss/ccs/'+identifier+'/FFFD0001'):
                raise ValueError('Unexpected title artwork mapping')
            local = (root/row['file']).resolve()
            if not local.is_relative_to(root) or not 0 < local.stat().st_size <= 512*1024:
                raise ValueError('Title artwork outside cache bounds')
            data = local.read_bytes()
            total += len(data)
            if total > 100*1024*1024:
                raise ValueError('Title artwork cache exceeds memory bound')
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Title artwork fingerprint mismatch')
            self.images[identifier] = ({'GIF': 'image/gif', 'PNG': 'image/png', 'JPEG': 'image/jpeg'}[row['format']], data)

    def url(self, identifier):
        return '/title-artwork/'+identifier if identifier in self.images else '/oss/oss/common/images/spacer.gif'

    def asset(self, path):
        match = re.fullmatch('/title-artwork/([0-9A-F]{16})', path)
        if not match or match[1] not in self.images:
            return 404, 'text/plain', b'Title artwork not found'
        mime, data = self.images[match[1]]
        return 200, mime, data
