"""Original copy/Base64 wrappers; ES returns explicitly synthetic bytes."""
import base64
import json
import os
from pathlib import Path
import unittest

from tests import test_wii_shop_url as native_fixture
from tools.verify_wii_shop_signing import verify_signing_wrapper


class ShopSigningIdentityTests(unittest.TestCase):
    def test_wrong_original_refuses_before_optional_emulation_import(self):
        with self.assertRaisesRegex(ValueError, 'pinned original'):
            verify_signing_wrapper(b'not an original image', b'synthetic',
                                   signature=bytes(60), signer_certificate=bytes(384))


class NativeShopSigningTests(unittest.TestCase):
    def source(self):
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
        except ImportError:
            self.skipTest('Optional native verification dependencies unavailable')
        return native_fixture.NativeShopUrlTests.source(self)

    def test_complete_original_wrappers_preserve_exact_es_bytes_and_encode_real_base64(self):
        source = self.source()
        signature, certificate = bytes(range(60)), bytes(range(256)) + bytes(range(128))
        for message in (b'x', b'<Challenge>a&b</Challenge>', 'synthetic 日本語'.encode(),
                        b'\0binary\xff', b'x' * 1024):
            with self.subTest(size=len(message)):
                result = verify_signing_wrapper(source, message, signature=signature,
                                                signer_certificate=certificate)
                self.assertEqual(result.status, 0)
                self.assertEqual(result.message, message)
                self.assertEqual(result.signature_base64, base64.b64encode(signature))
                self.assertEqual(result.certificate_base64, base64.b64encode(certificate))
                self.assertTrue(result.metadata()['native_base64_executed'])
                self.assertTrue(result.metadata()['object_heap_stack_and_write_bounds_verified'])
                self.assertFalse(result.metadata()['native_copy_string_and_base64_stubbed'])
                self.assertFalse(result.metadata()['es_crypto_and_device_state_executed'])
                self.assertEqual(result.counts['es_calls'], 1)
                self.assertEqual(result.counts['base64_calls'], 2)
                self.assertNotIn('Challenge', repr(result))

    def test_es_failure_keeps_prior_outputs_and_does_not_encode_them_as_success(self):
        source = self.source()
        for status in (-1, -1017, 1):
            with self.subTest(status=status):
                result = verify_signing_wrapper(source, b'synthetic', signature=bytes(60),
                                                signer_certificate=bytes(384), es_status=status)
                self.assertEqual(result.status, status)
                self.assertEqual(result.signature_base64, b'previous-signature')
                self.assertEqual(result.certificate_base64, b'previous-certificate')
                self.assertFalse(result.base64_executed)
                self.assertEqual(result.counts['base64_calls'], 0)

    def test_selected_original_headers_sources_and_retail_call_lengths_match(self):
        from tools.audit_wii_shop_proof_sources import audit
        source_root = Path(os.environ.get('JWC24_SHOP_SOURCE_ROOT',
            'C:/Users/Colin/Desktop/Nintendo/workbench/wii/channel-hunt/packed-resources/shop-build-lead'))
        header_root = Path(os.environ.get('JWC24_SHOP_HEADER_ROOT',
                                        'private/wii_shop/auth-header-evidence-20261027'))
        if not (source_root / 'inventory.json').is_file() or not (header_root / 'iosccert.h').is_file():
            self.skipTest('Selected private original Shop sources/SDK headers unavailable')
        appdata = os.environ.get('APPDATA')
        main = (Path(appdata) / 'Dolphin Emulator/Wii/title/00010002/48414241/content/0000005e.app'
                if appdata else Path('private/wii_shop/main.dol'))
        if not main.is_file():
            self.skipTest('Pinned original Shop executable unavailable')
        result = audit(main, source_root, header_root)
        self.assertEqual(len(result['selected_original_headers']), 4)
        self.assertEqual(len(result['inventory_verified_sources']), 7)
        self.assertEqual(len(result['native_direct_calls_checked']), 4)
        self.assertEqual(result['certificate_layout']['certificate_bytes'], 384)
        self.assertEqual(result['certificate_layout']['raw_signature_bytes'], 60)
        self.assertFalse(result['opaque_header_word_meaning_verified'])
        self.assertFalse(result['headers_compiled_or_original_ios_crypto_executed'])
        self.assertFalse(result['original_archive_sha256_checked'])
        self.assertNotIn(str(source_root), json.dumps(result))
        self.assertNotIn(str(header_root), json.dumps(result))
