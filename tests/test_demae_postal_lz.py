from pathlib import Path
import unittest

from tools.verify_demae_postal_lz import verify


class NativePostalLzTests(unittest.TestCase):
    def check(self, compressed, expected, **options):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        report = verify(path.read_bytes(), compressed, expected, **options)
        self.assertFalse(report['native_lz_mocked'])
        self.assertTrue(report['output_guards_verified'])

    def test_literal_and_backreference_fixtures(self):
        from jwc24.forecast import encode_lz10_literal
        from jwc24.lz11 import encode_lz11
        for raw in (b'postal fixture', bytes(range(256)), b'abc'*150, b'A'*4096):
            for encode in (encode_lz10_literal, encode_lz11):
                data = encode(raw)
                for padding in (0, 15, 32):
                    with self.subTest(size=len(raw), type=data[0], padding=padding):
                        self.check(data+bytes(padding), raw)

    def test_lz10_and_lz11_overlapping_references(self):
        # Literal A followed by a distance-one copy of three bytes.
        for kind, token in ((0x10, b'\0\0'), (0x11, b'\x20\0')):
            self.check(bytes([kind, 4, 0, 0, 0x40, 65])+token, b'AAAA')

    def test_lz11_long_reference_forms(self):
        for count, token in ((17, b'\0\0\0'), (273, b'\x10\0\0\0')):
            raw = b'A'*(count+1)
            self.check(b'\x11'+len(raw).to_bytes(3, 'little')+b'\x40A'+token, raw)

    def test_extended_size_header(self):
        for kind in (0x10, 0x11):
            self.check(bytes([kind, 0, 0, 0])+b'\x03\0\0\0\0abc', b'abc')

    def test_native_rejection_statuses(self):
        for data, status in ((b'\x12\x04\0\0'+bytes(4), -1),
                             (b'\x10\x04\0\0', -2),
                             (b'\x10\x04\0\0\x80\0\0\0', -4),
                             (b'\x11\x04\0\0\x80\x20\0\0', -4),
                             (b'\x10\x03\0\0\0abc'+bytes(33), -3)):
            with self.subTest(status=status):
                self.check(data, b'', expected_status=status)

    def test_truncated_copy_tokens(self):
        from jwc24.lz11 import decode_lz11
        for count, token in ((3, b'\x20\0'), (17, b'\0\0\0'), (273, b'\x10\0\0\0')):
            data = b'\x11'+(count+1).to_bytes(3, 'little')+b'\x40A'+token
            for size in range(4, len(data)):
                with self.subTest(count=count, size=size):
                    with self.assertRaises(ValueError):
                        decode_lz11(data[:size])

    def test_native_truncated_copy_tokens(self):
        for count, token in ((3, b'\x20\0'), (17, b'\0\0\0'), (273, b'\x10\0\0\0')):
            data = b'\x11'+(count+1).to_bytes(3, 'little')+b'\x40A'+token
            for size in range(4, len(data)):
                with self.subTest(count=count, size=size):
                    self.check(data[:size], b'', expected_status=-2)

    def test_postal_decoder_wraps_truncated_lz11_token(self):
        from Crypto.Cipher import AES
        from jwc24.demae import PostalFormatError, decode_postal_download
        # Offset eight places an incomplete three-byte token at the block end.
        plain = b'zpcd\x08'+bytes(3)+b'\x11\x12\0\0\x40A\0\0'
        key, iv = bytes(32), bytes(16)
        encrypted = AES.new(key, AES.MODE_CBC, iv=iv).encrypt(plain)
        with self.assertRaisesRegex(PostalFormatError, 'truncated LZ11 back-reference'):
            decode_postal_download(encrypted, key, iv)

    def test_fingerprint_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'', bytes(8), b'')
