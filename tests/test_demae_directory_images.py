from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from tools.cache_demae_directory_images import load_images, validate_url, validate_jpeg


class DirectoryImageTests(unittest.TestCase):
    def test_provider_urls_reject_other_hosts_and_ambiguous_authorities(self):
        good = 'https://imgfp.hotp.jp/IMGH/00/01/P000000001/P000000001_69.jpg'
        self.assertEqual(validate_url(good), good)
        for bad in (good.replace('https:', 'http:'), good.replace('imgfp.hotp.jp', 'example.com'),
                    good.replace('imgfp.hotp.jp', 'imgfp.hotp.jp@evil.example'), good+'?redirect=x'):
            with self.assertRaises(ValueError):
                validate_url(bad)

    def test_cache_preserves_bytes_and_rejects_tampering_and_path_changes(self):
        buffer = BytesIO()
        Image.new('RGB', (8, 8)).save(buffer, format='JPEG')
        data = buffer.getvalue()
        self.assertEqual(validate_jpeg(data), (8, 8))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identifier = 'hotpepper:J000000001'
            row = dict(restaurant_id=identifier, filename='J000000001.jpg',
                       source_url='https://imgfp.hotp.jp/IMGH/00/01/P000000001/P000000001_69.jpg',
                       sha256=hashlib.sha256(data).hexdigest(), width=8, height=8)
            manifest = dict(schema_version=1, provider='hotpepper', unmodified_source_images=True, images=[row])
            (root / row['filename']).write_bytes(data)
            (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(load_images(root, {identifier}), {identifier: data})
            with self.assertRaises(ValueError):
                load_images(root, set())
            (root / row['filename']).write_bytes(data+b'tampered')
            with self.assertRaises(ValueError):
                load_images(root, {identifier})
            row['filename'] = '../outside.jpg'
            (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_images(root, {identifier})
