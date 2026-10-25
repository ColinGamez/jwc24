import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from jwc24 import wii_shop_localization as localization
from jwc24.wii_shop_captured_scripts import CapturedScripts


class SharedFixture:
    """Synthetic GIF headers only; no original proprietary pixels are copied."""
    def __init__(self):
        self.shared = {}

    def resource_url(self, path):
        if path not in self.shared:
            raise ValueError('Missing fixture resource')
        return '/assets/captured'+path


class ShopLocalizationTests(unittest.TestCase):
    def fixture(self, *, width=77, height=65, magic=b'GIF89a'):
        shared = SharedFixture()
        rows = []
        for index in range(2):
            path = '/oss/oss/common/images/banner/synthetic'+str(index)+'.gif'
            data = magic+struct.pack('<HH', width, height)+b'synthetic fixture '+bytes([index])
            rows.append((path, len(data), hashlib.sha256(data).hexdigest()))
            shared.shared[path] = ('image/gif', data)
        return shared, tuple(rows)

    def test_normal_and_hover_order_and_source_bytes_are_preserved(self):
        shared, rows = self.fixture()
        original = shared.shared.copy()
        with patch.object(localization, 'CONTROLLER_IMAGES', rows):
            result = localization.controller_images(shared)
        self.assertEqual(result, tuple('/assets/captured'+row[0] for row in rows))
        self.assertEqual(shared.shared, original)

    def test_missing_member_never_falls_back_to_an_english_or_generated_image(self):
        shared, rows = self.fixture()
        del shared.shared[rows[1][0]]
        with patch.object(localization, 'CONTROLLER_IMAGES', rows), self.assertRaisesRegex(ValueError, 'Missing'):
            localization.controller_images(shared)

    def test_tampering_wrong_size_or_wrong_mime_is_rejected(self):
        for case in ('tamper', 'size', 'mime'):
            shared, rows = self.fixture()
            path = rows[0][0]
            mime, data = shared.shared[path]
            if case == 'tamper':
                data = data[:-1]+b'x'
            elif case == 'size':
                data += b'x'
            else:
                mime = 'image/png'
            shared.shared[path] = (mime, data)
            with self.subTest(case=case), patch.object(localization, 'CONTROLLER_IMAGES', rows):
                with self.assertRaisesRegex(ValueError, 'fingerprint or size'):
                    localization.controller_images(shared)

    def test_matching_fingerprint_does_not_skip_gif_dimension_checks(self):
        for changes in ({'width': 76}, {'height': 64}, {'magic': b'NOTGIF'}):
            shared, rows = self.fixture(**changes)
            with self.subTest(changes=changes), patch.object(localization, 'CONTROLLER_IMAGES', rows):
                with self.assertRaisesRegex(ValueError, 'GIF dimensions'):
                    localization.controller_images(shared)

    @unittest.skipUnless(Path('private/wii_shop/frontend-capture-v1/manifest.private.json').is_file(),
                         'Private collector shared assets are optional')
    def test_private_reviewed_pair_remains_byte_identical_and_77_by_65(self):
        shared = CapturedScripts('private/wii_shop/frontend-capture-v1')
        urls = localization.controller_images(shared)
        for url, (path, size, digest) in zip(urls, localization.CONTROLLER_IMAGES):
            status, mime, data = shared.asset(url)
            self.assertEqual((status, mime, len(data)), (200, 'image/gif', size))
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            self.assertEqual(struct.unpack('<HH', data[6:10]), (77, 65))
            self.assertEqual(url, shared.resource_url(path))


if __name__ == '__main__':
    unittest.main()
