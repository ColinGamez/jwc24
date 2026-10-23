from pathlib import Path
import unittest

from tools.verify_demae_postal_callback import verify


class PostalCallbackTests(unittest.TestCase):
    def source(self):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        return path.read_bytes()

    def encrypt(self, plain):
        from Crypto.Cipher import AES
        return AES.new(bytes(range(32)), AES.MODE_CBC, iv=bytes(range(16))).encrypt(plain)

    def run_callback(self, data, **options):
        return verify(self.source(), bytes(range(32)), bytes(range(16)), data, **options)

    def test_native_decrypt_and_strip_for_both_compression_types(self):
        from jwc24.forecast import encode_lz10_literal
        from jwc24.lz11 import encode_lz11
        for encode in (encode_lz10_literal, encode_lz11):
            plain = b'zpcd\x10'+bytes(11)+encode(b'synthetic postal record data')
            plain += bytes((-len(plain)) % 16)
            report = self.run_callback(self.encrypt(plain))
            self.assertEqual(report['native_status'], 0)
            self.assertEqual(report['stripped_bytes'], len(plain)-16)
            self.assertTrue(report['cleanup_verified'])

    def test_native_size_rejection_and_cleanup(self):
        for data, capacity in ((b'', 256), (bytes(15), 256), (bytes(17), 256), (bytes(32), 16)):
            self.assertEqual(self.run_callback(data, capacity=capacity)['native_status'], 0x17)

    def test_native_header_rejection_and_cleanup(self):
        self.assertEqual(self.run_callback(self.encrypt(bytes(32)))['native_status'], 0x1b)

    def test_native_allocation_failures_release_partial_allocation(self):
        for number in (1, 2):
            report = self.run_callback(self.encrypt(b'zpcd\x10'+bytes(27)), fail_allocation=number)
            self.assertEqual(report['native_status'], 0x18)
            self.assertTrue(report['cleanup_verified'])

    def test_fingerprint_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'', bytes(32), bytes(16), bytes(16))

    def test_unsafe_offsets_excluded_before_emulation(self):
        for offset in (0, 4, 33, 255):
            data = self.encrypt(b'zpcd'+bytes([offset])+bytes(27))
            with self.assertRaisesRegex(ValueError, 'Unsafe synthetic offset'):
                self.run_callback(data)


if __name__ == '__main__':
    unittest.main()
