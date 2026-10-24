"""Load a bounded private cache of archived, title-ID-addressed Shop images."""
import hashlib
import json
from pathlib import Path
import re
from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE


class TitleArtwork:
    def __init__(self, root, catalog_digest=None):
        self.images = {}
        self.detail_images = {}
        self.source, self.digest = None, None
        root = Path(root).resolve()
        path = root/'manifest.json'
        if not path.is_file():
            return
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized title artwork manifest')
        manifest_data = path.read_bytes()
        manifest = json.loads(manifest_data)
        historical = manifest.get('source') == SOURCE
        if (manifest.get('source') not in ('https://wiishopchannel.net', SOURCE)
                or len(manifest['images']) > 20000
                or historical and (manifest.get('archive_sha1') != ARCHIVE_SHA1
                                   or not re.fullmatch('[0-9a-f]{64}',manifest.get('capture_manifest_sha256','')))
                or (catalog_digest is not None and manifest.get('catalog_sha256') != catalog_digest)):
            raise ValueError('Title artwork source/catalog differs')
        if historical and ('detail_images' not in manifest or len(manifest['detail_images']) > 20000):
            raise ValueError('Historical artwork requires separate catalog and detail roles')
        total = 0
        for role, rows in (('catalog', manifest['images']), ('detail', manifest.get('detail_images', {}))):
            target = self.images if role == 'catalog' else self.detail_images
            for identifier, row in rows.items():
                suffix = '.img' if role == 'catalog' else '.detail.img'
                if (not re.fullmatch('[0-9A-F]{16}', identifier) or row['file'] != identifier+suffix
                        or row['format'] not in ('GIF', 'PNG', 'JPEG', 'BMP')
                        or (not historical and row['url'] != 'https://wiishopchannel.net/oss/ccs/'+identifier+'/FFFD0001')):
                    raise ValueError('Unexpected title artwork mapping')
                if historical:
                    match = re.fullmatch(r'oss-auth\.shop\.wii\.com/oss/ccs/([A-Fa-f0-9]{16})/(FFFD[A-Fa-f0-9]{4})', row.get('member',''))
                    if not match or match[1].upper() != identifier:
                        raise ValueError('Unexpected historical title artwork mapping')
                    proof = 'reference_catalog_sha256' if role == 'catalog' else 'reference_detail_sha256'
                    if not re.fullmatch('[0-9a-f]{64}', row.get(proof) or ''):
                        raise ValueError('Artwork lacks captured '+role+' provenance')
                local = (root/row['file']).resolve()
                if not local.is_relative_to(root) or not 0 < local.stat().st_size <= 512*1024:
                    raise ValueError('Title artwork outside cache bounds')
                data = local.read_bytes()
                total += len(data)
                if total > 100*1024*1024:
                    raise ValueError('Title artwork cache exceeds memory bound')
                if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                    raise ValueError('Title artwork fingerprint mismatch')
                target[identifier] = ({'GIF': 'image/gif', 'PNG': 'image/png', 'JPEG': 'image/jpeg', 'BMP':'image/bmp'}[row['format']], data)
        if not historical:
            self.detail_images = self.images
        self.source, self.digest = manifest['source'], hashlib.sha256(manifest_data).hexdigest()

    def url(self, identifier, role='catalog'):
        if role not in ('catalog', 'detail'):
            raise ValueError('Unknown title artwork role')
        images = self.images if role == 'catalog' else self.detail_images
        return '/title-artwork/'+identifier+('/detail' if role == 'detail' else '') if identifier in images else '/oss/oss/common/images/spacer.gif'

    def asset(self, path):
        match = re.fullmatch('/title-artwork/([0-9A-F]{16})(/detail)?', path)
        images = self.detail_images if match and match[2] else self.images
        if not match or match[1] not in images:
            return 404, 'text/plain', b'Title artwork not found'
        mime, data = images[match[1]]
        return 200, mime, data
