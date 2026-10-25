"""Synthetic framing interop with a private, fingerprinted Japanese retail DOL."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from jwc24.cmoc import CMOCFormatError, CMOCUnsupportedFormat, inspect_response
from tools.verify_cmoc_framing import NativeFramingBoundsError, verify_framing


def header():
    return struct.pack('>HBBII', 0x4644, 1, 2, 0x12345678, 9) + bytes(20)


def ordinary(size, tag=0x4142):
    return struct.pack('>HHI', tag, size, 0) + bytes(max(0, size - 8))


def extended(size):
    return struct.pack('>HHIII', 0x4344, 0, 0, 0, size) + bytes(max(0, size - 16))


class CMOCNativeFramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'private/cmoc/v512/0001-0000000c.app'
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese CMOC v512 executable unavailable')
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependency unavailable')
        cls.source = path.read_bytes()

    def native(self, data, **kwargs):
        return verify_framing(self.source, data, **kwargs)

    def test_native_header_threshold_every_short_length(self):
        for length in range(33):
            with self.subTest(length=length):
                result = self.native(bytes(length))
                self.assertEqual(result['header_present'], length >= 32)
                self.assertFalse(result['native_routines_stubbed'])
                self.assertTrue(result['input_object_and_stack_guards_verified'])

    def test_ordinary_and_extended_records_match_independent_inspector(self):
        for sizes in ((8,), (9, 13, 128), (0xFFFF,)):
            data = header() + b''.join(ordinary(size) for size in sizes)
            inspection = inspect_response(data)
            self.assertEqual(self.native(data)['records'],
                             [{'offset': item.offset, 'size': item.size} for item in inspection.records])
        for size in (16, 17, 100, 0x10000):
            with self.subTest(extended_size=size):
                data = header() + ordinary(9) + extended(size) + ordinary(8)
                inspection = inspect_response(data)
                self.assertTrue(inspection.records[1].extended_size)
                result = self.native(data)
                self.assertEqual(result['records'],
                                 [{'offset': item.offset, 'size': item.size} for item in inspection.records])
                self.assertEqual(result['unconsumed_bytes'], 0)

    def test_incomplete_extended_accessor_is_trapped_before_read(self):
        for size in range(8, 16):
            with self.subTest(size=size):
                data = header() + bytes(size)
                with self.assertRaises(NativeFramingBoundsError):
                    self.native(data)
                with self.assertRaises(CMOCUnsupportedFormat):
                    inspect_response(data)

    def test_local_extended_minimum_is_stricter_than_native_framing(self):
        # The malformed extended prefix aliases another ordinary prefix.
        data = header() + struct.pack('>HHIII', 0x4344, 0, 0, 0x41420008, 8)
        result = self.native(data)
        self.assertEqual(result['records'], [{'offset': 32, 'size': 8},
                                             {'offset': 40, 'size': 8}])
        self.assertEqual(result['unconsumed_bytes'], 0)
        with self.assertRaises(CMOCFormatError):
            inspect_response(data)

    def test_malformed_size_stops_native_and_strict_inspector_rejects(self):
        for tail in (b'x', bytes(7), ordinary(8)[:7], ordinary(9)[:8],
                     struct.pack('>HHI', 1, 7, 0), extended(17)[:16]):
            with self.subTest(tail_size=len(tail)):
                data = header() + tail
                result = self.native(data)
                self.assertEqual(result['records'], [])
                self.assertEqual(result['cursor'], 32)
                with self.assertRaises(CMOCFormatError):
                    inspect_response(data)

    def test_native_correlation_fields_and_independent_header_matcher(self):
        base = header()
        parsed = inspect_response(base).header
        for offset in range(32):
            changed = bytearray(base)
            changed[offset] ^= 1
            changed = bytes(changed)
            expected = offset not in (0, 1, 4, 5, 6, 7, 8, 9, 10, 11)
            with self.subTest(offset=offset):
                self.assertEqual(self.native(changed, expected_header=base)['header_matches'], expected)
                self.assertEqual(inspect_response(changed).header.matches_request(parsed), expected)
        self.assertNotIn('305419896', repr(parsed))
        self.assertFalse(replace(parsed, word_8=10).matches_request(parsed))

    def test_harness_rejects_wrong_source_and_invalid_inputs_without_echo(self):
        for source, data, expected in ((b'wrong', b'', None), (self.source, bytearray(), None),
                                       (self.source, b'', b'private-identity')):
            with self.subTest(expected_length=len(expected or b'')), self.assertRaises(ValueError) as caught:
                verify_framing(source, data, expected_header=expected)
            self.assertNotIn('private-identity', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
