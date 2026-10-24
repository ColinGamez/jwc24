import os
from pathlib import Path
import unittest

from tools.verify_wii_shop_url import verify


class NativeShopUrlTests(unittest.TestCase):
    def source(self):
        root = os.environ.get('APPDATA')
        path = Path(root)/'Dolphin Emulator/Wii/title/00010002/48414241/content/0000005e.app' if root else Path('private/wii_shop/main.dol')
        if not path.is_file():
            self.skipTest('Private v21 executable unavailable')
        return path.read_bytes()

    def test_mode_selects_original_branch_with_synthetic_bases(self):
        source = self.source()
        for mode in (0, 1, 2, 3, 8, 9, 0xffffffff):
            report = verify(source, mode, b'/test')
            self.assertEqual(report['manual_branch'], mode in (2, 8))
            self.assertFalse(report['native_formatter_mocked'])

    def test_empty_and_truncated_inputs_preserve_guards(self):
        source = self.source()
        for suffix in (b'', b'x'*234, b'x'*235, b'x'*1024):
            report = verify(source, 0, suffix)
            self.assertTrue(report['buffer_guards_verified'])
            self.assertEqual(report['truncated'], len(b'https://shop.example')+len(suffix)>254)
        verify(source, 2, b'', base=b'', manual=b'')

    def test_fingerprint_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'', 0, b'')

    def test_concatenation_does_not_insert_slash_or_reencode_suffix(self):
        source = self.source()
        verify(source, 0, b'relative?test=%E3%81%82')
        with self.assertRaisesRegex(ValueError, 'embedded NUL'):
            verify(source, 0, b'test\0suffix')
