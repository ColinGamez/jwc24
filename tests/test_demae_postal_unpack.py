from pathlib import Path
import unittest

from tools.verify_demae_postal_unpack import verify


class NativePostalUnpackTests(unittest.TestCase):
    def check(self, data, expected=b'', **options):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        report = verify(path.read_bytes(), data, expected, **options)
        self.assertTrue(report['cleanup_verified'])
        self.assertTrue(report['allocation_guards_verified'])
        self.assertFalse(report['native_wrapper_mocked'])

    def test_native_unpack_both_formats_with_padding(self):
        from jwc24.forecast import encode_lz10_literal
        from jwc24.lz11 import encode_lz11
        for raw in (b'postal fixture', b'abc'*300):
            for encode in (encode_lz10_literal, encode_lz11):
                data = encode(raw)
                for padding in (0, 15):
                    self.check(data+bytes(padding), raw)

    def test_file_and_allocation_failures(self):
        from jwc24.lz11 import encode_lz11
        raw = b'postal fixture'
        for fault, status in (('open_source', 0x14), ('open_destination', 0x14),
                              ('allocate_input', 0x18), ('allocate_output', 0x18),
                              ('read', 0x15), ('short_read', 0x14), ('write', 0x15),
                              ('close_source', 0x15), ('close_destination', 0x15)):
            with self.subTest(fault=fault):
                self.check(encode_lz11(raw), raw, fault=fault, expected_status=status)

    def test_input_and_declared_output_capacity(self):
        for data, capacity in ((b'', 256), (bytes(7), 256),
                                (b'\x11\x01\0\0'+bytes(12), 8),
                                (b'\x11\0\x01\0'+bytes(4), 32)):
            self.check(data, capacity=capacity, expected_status=0x17)

    def test_decoder_failure_is_propagated_without_output(self):
        for data in (b'\x12\x04\0\0'+bytes(4),
                     b'\x11\x04\0\0\x80\x20\0\0',
                     b'\x10\x03\0\0\0abc'+bytes(33)):
            self.check(data, expected_status=0x1c)

    def test_fingerprint_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'', b'', b'')
