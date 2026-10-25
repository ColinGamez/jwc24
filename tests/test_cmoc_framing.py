"""Independent inspector checks that also run without private channel software."""
import struct
import unittest

from jwc24.cmoc import CMOCFormatError, CMOCUnsupportedFormat, inspect_response


class CMOCFramingTests(unittest.TestCase):
    def test_extended_sizes_preserve_exact_next_record_boundary(self):
        for size in (16, 17, 0x10000):
            with self.subTest(size=size):
                data = (bytes(32) + struct.pack('>HHIII', 0x4142, 0, 0, 0, size)
                        + bytes(size - 16) + struct.pack('>HHI', 0x4344, 8, 0))
                result = inspect_response(data)
                self.assertEqual([(r.offset, r.size, r.extended_size) for r in result.records],
                                 [(32, size, True), (32 + size, 8, False)])

    def test_extended_prefix_cannot_read_beyond_body_or_alias_another_record(self):
        for length in range(8, 16):
            with self.subTest(length=length), self.assertRaises(CMOCUnsupportedFormat):
                inspect_response(bytes(32 + length))
        for size in (0, 1, 8, 15, 17, 0xFFFFFFFF):
            data = bytes(32) + struct.pack('>HHIII', 1, 0, 0, 0, size)
            with self.subTest(size=size), self.assertRaises(CMOCFormatError):
                inspect_response(data)

    def test_header_correlation_is_not_an_authentication_or_status_check(self):
        data = struct.pack('>HBBII', 0x4644, 1, 2, 0x01020304, 0x55667788) + bytes(20)
        result = inspect_response(data)
        changed = bytearray(data)
        changed[2:4] = b'\xFE\xFF'
        self.assertTrue(result.header.matches_request(inspect_response(bytes(changed)).header))
        changed[8] ^= 1
        self.assertFalse(result.header.matches_request(inspect_response(bytes(changed)).header))
        self.assertNotIn('1432778632', repr(result))
        self.assertNotIn('1432778632', str(result.metadata()))
        with self.assertRaises(TypeError):
            result.header.matches_request(data)

    def test_invalid_limit_types_fail_before_parsing(self):
        for kwargs in ({'max_records': True}, {'max_records': 1.5},
                       {'max_bytes': False}, {'max_bytes': 'unbounded'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                inspect_response(bytes(32), **kwargs)
        with self.assertRaises(TypeError):
            inspect_response(bytearray(32))


if __name__ == '__main__':
    unittest.main()
