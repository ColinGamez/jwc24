"""Actual configured dispatcher using synthetic encrypted compressed bodies."""
import hmac
import importlib.util
from pathlib import Path
import unittest

from tools.verify_cmoc_transform_pipeline import verify_transform_pipeline


def fixture(key_size=16, codec=0x10, arrangement=1):
    from Crypto.Cipher import AES
    from jwc24.forecast import encode_lz10
    from jwc24.lz11 import encode_lz11
    plain = bytes(range(64))
    encoded = (encode_lz10 if codec == 0x10 else encode_lz11)(plain)
    # Explicit synthetic padding fixture; the verifier never generates padding.
    supplied_plaintext = encoded + b'\xA7' * (-len(encoded) % 16)
    key, iv, hash_key = b'K' * key_size, b'I' * 16, b'H' * 20
    cipher = AES.new(key, AES.MODE_CBC, iv).encrypt(supplied_plaintext)
    if arrangement == 1:
        chunks = (cipher,)
    elif arrangement == 2:
        chunks = (cipher[:16], cipher[16:])
    else:
        chunks = (cipher[:16], cipher[16:32], cipher[32:])
    return dict(hash_key=hash_key, cipher_key=key, iv=iv, ciphertext_chunks=chunks,
                receive_sizes=tuple(map(len, chunks)), expected_digest=hmac.digest(hash_key, cipher, 'sha1'),
                expected_wire_prefix=b'CES', wire_prefix=b'CES', cached_prefix=plain[:12],
                decompression_enabled=True)


class PipelineBoundaryTests(unittest.TestCase):
    def test_exact_source_required_without_optional_packages_or_resource_lookup(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_transform_pipeline(b'', hash_key=bytes(20), cipher_key=bytes(16), iv=bytes(16),
                ciphertext_chunks=(bytes(16),), receive_sizes=(16,), expected_digest=bytes(20),
                expected_wire_prefix=b'', wire_prefix=b'', cached_prefix=b'', decompression_enabled=True)


class PipelineNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/cmoc/v512/0001-0000000c.app')
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese CMOC v512 executable unavailable')
        if any(importlib.util.find_spec(name) is None for name in ('unicorn', 'capstone', 'Crypto')):
            raise unittest.SkipTest('Optional crypto/native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_full_callbacks_all_aes_key_sizes_both_codecs_and_multiple_events(self):
        for size in (16, 24, 32):
            for codec in (0x10, 0x11):
                for arrangement in (1, 2, 3):
                    with self.subTest(size=size, codec=codec, arrangement=arrangement):
                        result = verify_transform_pipeline(self.source, **fixture(size, codec, arrangement))
                        self.assertEqual((result['body_size'], result['final_flags']), (64, 0x0E))
                        self.assertTrue(result['native_digest_match'])
                        self.assertTrue(result['full_digest_binary_match'])
                        self.assertFalse(result['transform_or_digest_stubs_used'])
                        self.assertEqual(result['counts']['hash_updates'], arrangement)

    def test_prefix_mismatches_checked_latches_and_forced_short_body_finalization(self):
        from Crypto.Cipher import AES
        base = fixture(arrangement=3)
        for change, flags in ((dict(wire_prefix=b'BAD'), 0x4E),
                               (dict(cached_prefix=b'wrong'), 0x2E),
                               (dict(wire_prefix=b'BAD', initial_flags=0x08), 0x0E),
                               (dict(cached_prefix=b'wrong', initial_flags=0x04), 0x0E),
                               (dict(initial_flags=0x20), 0x2E)):
            with self.subTest(change=change):
                self.assertEqual(verify_transform_pipeline(self.source, **(base | change))['final_flags'], flags)
        cipher = AES.new(base['cipher_key'], AES.MODE_CBC, base['iv']).encrypt(
            b'\x10\x03\0\0\0ABC' + bytes(8))
        short = verify_transform_pipeline(self.source, **(base | dict(
            ciphertext_chunks=(cipher,), receive_sizes=(16,),
            expected_digest=hmac.digest(base['hash_key'], cipher, 'sha1'),
            cached_prefix=b'longer than three')))
        self.assertEqual((short['body_size'], short['final_flags']), (3, 0x2E))

    def test_hash_uses_actual_rounded_ciphertext_backing_before_decryption(self):
        base = fixture(arrangement=3)
        received = tuple(len(c) - 7 for c in base['ciphertext_chunks'])
        result = verify_transform_pipeline(self.source, **(base | dict(receive_sizes=received)))
        self.assertTrue(result['full_digest_binary_match'])
        altered = bytes((base['expected_digest'][0] ^ 1,)) + base['expected_digest'][1:]
        bad = verify_transform_pipeline(self.source, **(base | dict(expected_digest=altered)))
        self.assertFalse(bad['native_digest_match'])
        self.assertFalse(bad['full_digest_binary_match'])
        self.assertEqual(bad['final_flags'], 0x1E)

    def test_actual_native_equal_nul_digest_comparison_is_not_full_binary_authentication(self):
        base = fixture()
        for index in range(4096):
            cipher = index.to_bytes(16, 'big')
            digest = hmac.digest(base['hash_key'], cipher, 'sha1')
            if digest[0] == 0:
                break
        else:
            self.fail('Bounded synthetic equal-NUL fixture unavailable')
        altered = digest[:1] + bytes((digest[1] ^ 1,)) + digest[2:]
        result = verify_transform_pipeline(self.source, **(base | dict(
            ciphertext_chunks=(cipher,), receive_sizes=(16,), expected_digest=altered,
            cached_prefix=b'', decompression_enabled=False)))
        self.assertTrue(result['native_digest_match'])
        self.assertFalse(result['full_digest_binary_match'])
        self.assertEqual(result['native_compared_digest_bytes'], 1)
        self.assertFalse(result['resource_envelope_or_service_authentication_established'])

    def test_disabled_decompression_uses_actual_cipher_bytes_without_interpreting_header(self):
        result = verify_transform_pipeline(self.source, **(fixture(arrangement=2) | dict(
            cached_prefix=b'', decompression_enabled=False)))
        self.assertEqual(result['body_size'], 80)
        self.assertEqual(result['final_flags'], 0x0E)

    def test_rejects_unsupported_geometry_and_negative_or_inconsistent_decoder_counts(self):
        from Crypto.Cipher import AES
        base = fixture()
        for change in (dict(hash_key=bytes(21)), dict(cipher_key=bytes(15)), dict(iv=None),
                       dict(ciphertext_chunks=(bytes(17),)), dict(receive_sizes=(1,)),
                       dict(initial_flags=0x80), dict(initial_flags=True),
                       dict(expected_wire_prefix=bytes(45), wire_prefix=bytes(45)),
                       dict(expected_digest=bytes(21)), dict(cached_prefix=bytes(65))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_transform_pipeline(self.source, **(base | change))
        # Actual standalone behavior writes ABC then returns app0/SDK-3. It is
        # intentionally outside this first composed verifier's success domain.
        bad = b'\x10\x03\0\0\0ABC' + bytes(40)
        cipher = AES.new(base['cipher_key'], AES.MODE_CBC, base['iv']).encrypt(bad)
        with self.assertRaisesRegex(ValueError, 'nonnegative consistent'):
            verify_transform_pipeline(self.source, **(base | dict(ciphertext_chunks=(cipher,),
                receive_sizes=(len(cipher),), expected_digest=hmac.digest(base['hash_key'], cipher, 'sha1'))))


if __name__ == '__main__':
    unittest.main()
