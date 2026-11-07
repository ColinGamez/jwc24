"""Public synthetic AES-CBC vectors and optional original CMOC execution."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch

from jwc24.cmoc_cipher import decrypt_aes_cbc, inspect_application_cipher

CRYPTO = importlib.util.find_spec('Crypto') is not None


def vectors():
    # Public interoperability vectors: NIST SP 800-38A, F.2.2/F.2.4/F.2.6.
    plain = bytes.fromhex(
        '6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130'
        'c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710')
    entries = (
        ('2b7e151628aed2a6abf7158809cf4f3c',
         '7649abac8119b246cee98e9b12e9197d5086cb9b507219ee95db113a917678b273'
         'bed6b8e3c1743b7116e69e222295163ff1caa1681fac09120eca307586e1a7'),
        ('8e73b0f7da0e6452c810f32b809079e562f8ead2522c6b7b',
         '4f021db243bc633d7178183a9fa071e8b4d9ada9ad7dedf4e5e738763f69145a'
         '571b242012fb7ae07fa9baac3df102e008b0e27988598881d920a9e64f5615cd'),
        ('603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4',
         'f58c4c04d6e5f1ba779eabfb5f7bfbd69cfc4e967edb808d679f777bc6702c7d'
         '39f23369a9d9bacfa530e26304231461b2eb05e2c39be9fcda6c19078c6a9d1b'))
    return tuple((bytes.fromhex(key), bytes(range(16)), bytes.fromhex(cipher), plain)
                 for key, cipher in entries)


def split(cipher, sizes):
    offset, chunks = 0, []
    for size in sizes:
        chunks.append(cipher[offset:offset + size])
        offset += size
    assert offset == len(cipher)
    return tuple(chunks)


class CipherBoundaryTests(unittest.TestCase):
    def test_missing_crypto_dependency_reports_actionable_error(self):
        import builtins
        original_import = builtins.__import__

        def without_crypto(name, *args, **kwargs):
            if name == 'Crypto.Cipher':
                raise ImportError('Synthetic missing optional dependency')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', without_crypto), self.assertRaisesRegex(RuntimeError, 'optional crypto extra'):
            decrypt_aes_cbc(key=b'K' * 16, iv=bytes(16), chunks=(bytes(16),))

    def test_direct_algorithm_rejects_missing_iv_nonblocks_and_ambiguous_types(self):
        good = dict(key=b'K' * 16, iv=b'I' * 16, chunks=(bytes(16),))
        for change in (dict(key=None), dict(key=b'K' * 15), dict(iv=None),
                       dict(iv=bytes(15)), dict(chunks=(bytes(17),)),
                       dict(chunks=[bytes(16)]), dict(chunks=(bytearray(16),)),
                       dict(chunks=(b'',) * 65), dict(chunks=(bytes(1024 * 1024 + 1),))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                decrypt_aes_cbc(**(good | change))

    def test_disabled_cipher_copies_and_does_not_claim_sdk_or_acquisition(self):
        result = inspect_application_cipher(key=None, key_size=0, iv=None,
                                            chunks=(b'private-marker', b''),
                                            setup_acquired=None, chunk_acquired=(None, None))
        self.assertFalse(result.enabled)
        self.assertEqual(result.chunks[0].written, b'private-marker')
        self.assertIsNone(result.chunks[0].sdk_accepted)
        self.assertIsNone(result.final_chain)
        self.assertNotIn('private-marker', repr(result))
        self.assertNotIn('private-marker', str(result.metadata()))
        self.assertFalse(result.metadata()['source_authentication_established'])

    def test_setup_failure_and_invalid_key_disable_without_invented_decryption(self):
        for key, size, acquired in ((b'K' * 16, 16, False), (b'K' * 15, 15, True),
                                    (b'\0', 0, True), (b'K' * 33, 33, True)):
            result = inspect_application_cipher(key=key, key_size=size, iv=None,
                                                chunks=(b'not-block-aligned',),
                                                setup_acquired=acquired, chunk_acquired=(None,))
            self.assertFalse(result.setup_enabled)
            self.assertEqual(result.resolved_key_size, 0)
            self.assertEqual(result.chunks[0].written, b'not-block-aligned')

    def test_enabled_acquisition_failure_and_nonblock_return_are_not_writes(self):
        result = inspect_application_cipher(key=b'K' * 16, key_size=16, iv=None,
                                            chunks=(bytes(16), bytes(17)),
                                            setup_acquired=True, chunk_acquired=(False, True))
        self.assertTrue(result.enabled)
        self.assertEqual(tuple(c.return_size for c in result.chunks), (0, 17))
        self.assertEqual(tuple(c.sdk_accepted for c in result.chunks), (None, False))
        self.assertTrue(all(c.written is None for c in result.chunks))
        self.assertEqual(result.final_chain, bytes(16))

    def test_release_failure_preserves_enabled_context_success_clears_flag_only(self):
        values = dict(key=b'K' * 16, key_size=16, iv=b'I' * 16, chunks=(),
                      setup_acquired=True, chunk_acquired=(), release=True)
        failed = inspect_application_cipher(**values, release_acquired=False)
        released = inspect_application_cipher(**values, release_acquired=True)
        self.assertTrue(failed.enabled)
        self.assertEqual(failed.resolved_key_size, 16)
        self.assertFalse(released.enabled)
        self.assertEqual(released.resolved_key_size, 0)
        self.assertEqual(released.final_chain, b'I' * 16)  # No key/chain erasure claim.

    def test_strict_explicit_acquisition_and_key_span_validation(self):
        good = dict(key=b'K' * 16, key_size=16, iv=None, chunks=(),
                    setup_acquired=True, chunk_acquired=())
        for change in (dict(key_size=True), dict(key_size=17), dict(key=b'K', key_size=0),
                       dict(key=bytearray(16)), dict(iv=b'I'), dict(setup_acquired=1),
                       dict(chunk_acquired=[]), dict(chunk_acquired=(True,)),
                       dict(release=1), dict(release_acquired=True),
                       dict(release=True), dict(release=True, release_acquired=1)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                inspect_application_cipher(**(good | change))
        for change in (dict(setup_acquired=True), dict(key_size=1)):
            with self.assertRaises(ValueError):
                inspect_application_cipher(**(good | dict(key=None, key_size=0, setup_acquired=None) | change))
        for changes in (dict(chunk_acquired=(None,)), dict(chunk_acquired=(1,))):
            with self.assertRaises(ValueError):
                inspect_application_cipher(**(good | dict(chunks=(bytes(16),)) | changes))

    def test_native_source_and_ios_boundary_input_guards_before_optional_execution(self):
        from tools.verify_cmoc_cipher import _execute
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            _execute(b'', key=b'K' * 16, key_size=16, iv=bytes(16),
                     chunks=(), application=True)


@unittest.skipUnless(CRYPTO, 'Optional crypto extra unavailable')
class CipherAlgorithmTests(unittest.TestCase):
    def test_nist_three_key_sizes_and_chunk_arrangements(self):
        for key, iv, cipher, plain in vectors():
            for sizes in ((64,), (16, 16, 16, 16), (0, 16, 0, 48, 0)):
                chunks = split(cipher, sizes)
                self.assertEqual(b''.join(decrypt_aes_cbc(key=key, iv=iv, chunks=chunks)), plain)
                result = inspect_application_cipher(key=key, key_size=len(key), iv=iv,
                                                    chunks=chunks, setup_acquired=True,
                                                    chunk_acquired=(True,) * len(chunks))
                self.assertEqual(b''.join(c.written for c in result.chunks), plain)
                self.assertEqual(result.final_chain, cipher[-16:])

    def test_original_null_iv_and_strlen_mode_remain_explicit(self):
        from Crypto.Cipher import AES
        for size in (16, 24, 32):
            key, plain = b'K' * size, bytes(range(32))
            cipher = AES.new(key, AES.MODE_CBC, bytes(16)).encrypt(plain)
            result = inspect_application_cipher(key=key + b'\0unused', key_size=0,
                                                iv=None, chunks=(cipher,),
                                                setup_acquired=True, chunk_acquired=(True,))
            self.assertEqual(result.chunks[0].written, plain)
            self.assertEqual(result.setup_key_size, size)

    def test_failed_chunk_does_not_advance_chain_and_later_chunk_can_recover(self):
        from Crypto.Cipher import AES
        key, iv, cipher = b'K' * 16, b'I' * 16, bytes(range(32))
        result = inspect_application_cipher(key=key, key_size=16, iv=iv,
                                            chunks=(cipher[:16], cipher[16:]),
                                            setup_acquired=True, chunk_acquired=(False, True))
        self.assertIsNone(result.chunks[0].written)
        self.assertEqual(result.chunks[1].written, AES.new(key, AES.MODE_CBC, iv).decrypt(cipher[16:]))
        self.assertEqual(result.final_chain, cipher[-16:])


@unittest.skipUnless(CRYPTO, 'Optional crypto extra unavailable')
class CipherNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/cmoc/v512/0001-0000000c.app')
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese CMOC v512 executable unavailable')
        if any(importlib.util.find_spec(name) is None for name in ('unicorn', 'capstone')):
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_original_standard_vectors_full_core_separate_and_inplace(self):
        from tools.verify_cmoc_cipher import verify_sdk_cipher, verify_application_cipher
        for key, iv, cipher, _ in vectors():
            for sizes in ((64,), (16, 16, 16, 16), (0, 16, 0, 48, 0)):
                for inplace in (False, True):
                    chunks = split(cipher, sizes)
                    sdk = verify_sdk_cipher(self.source, key=key, iv=iv, chunks=chunks, inplace=inplace)
                    self.assertTrue(sdk['plaintext_and_final_chain_match'])
                    app = verify_application_cipher(self.source, key=key, key_size=len(key),
                                                     iv=iv, chunks=chunks, inplace=inplace)
                    self.assertTrue(app['original_cipher_and_wrappers_executed'])

    def test_original_null_iv_strlen_and_zero_chunks(self):
        from Crypto.Cipher import AES
        from tools.verify_cmoc_cipher import verify_application_cipher
        for key, iv, _, plain in vectors():
            for initial in (iv, None):
                cipher = AES.new(key, AES.MODE_CBC, iv if initial is not None else bytes(16)).encrypt(plain)
                for string_mode in (False, True):
                    result = verify_application_cipher(
                        self.source, key=key + b'\0unused' if string_mode else key,
                        key_size=0 if string_mode else len(key), iv=initial,
                        chunks=(cipher[:16], cipher[16:]))
                    self.assertEqual(result['setup_key_size'], len(key))
        self.assertEqual(verify_application_cipher(self.source, key=b'K' * 16,
                                                  key_size=16, iv=None, chunks=(b'',))['counts']['native_blocks'], 0)

    def test_original_disabled_invalid_and_nonblock_paths(self):
        from tools.verify_cmoc_cipher import verify_application_cipher
        for size in (0, 1, 15, 17, 23, 25, 31, 33):
            result = verify_application_cipher(self.source, key=b'\0' if size == 0 else b'K' * size,
                                                key_size=size, iv=None, chunks=(bytes(32),))
            self.assertFalse(result['enabled'])
            self.assertEqual(result['counts']['native_blocks'], 0)
        self.assertFalse(verify_application_cipher(self.source, key=None, key_size=0, iv=None,
                                                   chunks=(bytes(32),))['enabled'])
        for size in (1, 15, 17, 31):
            result = verify_application_cipher(self.source, key=b'K' * 16, key_size=16,
                                                iv=None, chunks=(bytes(size),))
            self.assertEqual(result['chunks'][0]['return_size'], size)
            self.assertIsNone(result['chunks'][0]['written_size'])
            self.assertFalse(result['chunks'][0]['sdk_accepted'])

    def test_original_acquire_recovery_close_and_release_failures(self):
        from tools.verify_cmoc_cipher import verify_application_cipher
        base = dict(key=b'K' * 16, key_size=16, iv=b'I' * 16, chunks=(bytes(32),))
        cases = (dict(open_results=(-1,)), dict(open_results=(7, -1)),
                 dict(chunks=(bytes(16), bytes(16)), open_results=(7, -1, 7)),
                 dict(close_results=(-1, 0)), dict(release=True),
                 dict(release=True, close_results=(-1, 0, 0)),
                 dict(release=True, open_results=(7, 7, -1)))
        for change in cases:
            with self.subTest(change=change):
                result = verify_application_cipher(self.source, **(base | change))
                self.assertTrue(result['acquisition_results_observed_from_original_helper'])
                self.assertTrue(result['input_and_stack_guards_verified'])

    def test_actual_guards_reject_missing_strlen_backing_and_unused_boundary_results(self):
        from tools.verify_cmoc_cipher import _execute
        base = dict(key=b'K' * 16, key_size=16, iv=bytes(16), chunks=(), application=True)
        for changes in (dict(open_results=(7, 7)), dict(close_results=(0, 0)),
                        dict(key=b'K' * 16, key_size=0), dict(open_results=(True,)),
                        dict(key_size=True), dict(chunks=(bytes(4097),)), dict(inplace=1)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                _execute(self.source, **(base | changes))


if __name__ == '__main__':
    unittest.main()
