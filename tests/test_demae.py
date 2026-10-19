import contextlib
import io
import struct
import tempfile
from pathlib import Path
import unittest

from jwc24.demae import PostalFormatError, inspect_postal_records, decode_postal_download
from tools.inspect_demae_postal import main


def record(code, strings):
    return struct.pack('>I', code) + b''.join(s.encode('utf-16-be') + b'\0\0' for s in strings)


class DemaePostalTests(unittest.TestCase):
    def test_application_download_pipeline_for_both_compression_types(self):
        from Crypto.Cipher import AES
        from jwc24.forecast import encode_lz10_literal
        from jwc24.lz11 import encode_lz11
        key, iv = bytes(range(32)), bytes(range(16))
        raw = record(3700000, ('群馬県', '高崎市', '合成テスト'))
        for encode in (encode_lz10_literal, encode_lz11):
            plain = b'zpcd\x10' + bytes(11) + encode(raw)
            plain += bytes((-len(plain)) % 16)
            encrypted = AES.new(key, AES.MODE_CBC, iv=iv).encrypt(plain)
            self.assertEqual(decode_postal_download(encrypted, key, iv), raw)

    def test_download_rejects_bad_headers_and_declared_allocation_before_decode(self):
        from Crypto.Cipher import AES
        key, iv = bytes(32), bytes(16)
        for plain in (bytes(32), b'zpcd\xff' + bytes(27),
                      b'zpcd\x10' + bytes(11) + b'\x10\x01\x00\x04' + bytes(12),
                      b'zpcd\x10' + bytes(11) + b'\x11\0\0\0\xff\xff\xff\x7f' + bytes(8)):
            encrypted = AES.new(key, AES.MODE_CBC, iv=iv).encrypt(plain)
            with self.assertRaises(PostalFormatError):
                decode_postal_download(encrypted, key, iv)
        for data in (b'', bytes(15), bytes(17)):
            with self.assertRaises(PostalFormatError):
                decode_postal_download(data, key, iv)

    def test_big_endian_records_and_utf16_code_units(self):
        data = record(3700000, ('群馬県', '高崎市', '住所例😀')) + record(123, ('', '', ''))
        result = inspect_postal_records(data)
        self.assertEqual([r.postal_code for r in result], [3700000, 123])
        self.assertEqual(result[0].strings, ('群馬県', '高崎市', '住所例😀'))
        self.assertEqual(result[1].strings, ('', '', ''))

    def test_every_nonempty_truncated_record_is_rejected(self):
        data = record(1, ('甲', '乙', '丙'))
        for length in range(1, len(data)):
            with self.subTest(length=length), self.assertRaises(PostalFormatError):
                inspect_postal_records(data[:length])

    def test_limits_and_unpaired_surrogate(self):
        data = record(1, ('', '', ''))
        for options in ({'max_bytes': len(data)-1}, {'max_records': 0}):
            with self.assertRaises(PostalFormatError):
                inspect_postal_records(data, **options)
        with self.assertRaises(PostalFormatError):
            inspect_postal_records(struct.pack('>I', 1) + b'\xd8\x00\0\0\0\0\0\0')

    def test_cli_does_not_print_addresses_or_postal_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'processed.dat'
            p.write_bytes(record(7654321, ('private', 'address', 'text')))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(p)]), 0)
            for value in ('7654321', 'private', 'address'):
                self.assertNotIn(value, output.getvalue())
