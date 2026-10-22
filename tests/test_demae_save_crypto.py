from pathlib import Path
import unittest

from tools.verify_demae_save_crypto import verify


class SaveCryptoTests(unittest.TestCase):
    def source(self):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        return path.read_bytes()

    def test_native_cbc_matches_independent_cipher_for_all_key_lengths(self):
        source = self.source()
        for size in (16, 24, 32):
            with self.subTest(key_bytes=size):
                report = verify(source, bytes(range(size)), bytes(range(16)), bytes(range(64)))
                self.assertEqual(report['key_bits'], size*8)
                self.assertEqual(report['blocks_verified'], 4)
                self.assertFalse(report['native_cipher_mocked'])
                self.assertTrue(report['incomplete_block_rejected_without_output_write'])
                self.assertFalse(report['key_derivation_verified'])
                self.assertFalse(report['native_save_acceptance_verified'])

    def test_full_observed_save_buffer(self):
        report = verify(self.source(), bytes(range(32)), bytes(range(16)), bytes(range(256))*64)
        self.assertEqual(report['blocks_verified'], 1024)
        self.assertFalse(report['save_integrity_verified'])

    def test_invalid_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'wrong', bytes(32), bytes(16), bytes(16))
        source = self.source()
        for key, iv, plain in [(bytes(15),bytes(16),bytes(16)),
                               (bytes(32),bytes(15),bytes(16)),
                               (bytes(32),bytes(16),b''),
                               (bytes(32),bytes(16),bytes(17)),
                               (bytes(32),bytes(16),bytes(16400))]:
            with self.subTest(lengths=(len(key),len(iv),len(plain))):
                with self.assertRaises(ValueError):
                    verify(source, key, iv, plain)
