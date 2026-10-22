from pathlib import Path
import struct
import unittest

from jwc24.demae_save_sections import inspect_sections
from tools.verify_demae_save_sections import verify


def fixture(rows):
    data = bytearray(0x4000)
    data[:5] = b'PDFF\x02'
    offset = 0x80
    for tag, length, stop in rows:
        struct.pack_into('>4sIB3x', data, offset, tag, length, stop)
        offset += length
    return bytes(data)


class SaveSectionTests(unittest.TestCase):
    def test_offsets_lengths_and_opaque_payload(self):
        data = bytearray(fixture([(b'INFO', 32, 0), (b'KANA', 20, 1)]))
        data[0x8C:0x98] = b'PRIVATE NAME'
        version, rows = inspect_sections(bytes(data))
        self.assertEqual(version, 2)
        self.assertEqual([(r.tag, r.offset, r.payload_length) for r in rows],
                         [(b'INFO', 128, 20), (b'KANA', 160, 8)])
        self.assertNotIn('PRIVATE NAME', repr(rows))

    def test_nonzero_stop_prevents_trailing_record_interpretation(self):
        _, rows = inspect_sections(fixture([(b'INFO', 32, 7), (b'KANA', 20, 1)]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].stop_byte, 7)

    def test_zero_short_oversized_and_truncated_sections_rejected(self):
        for length in (0, 1, 11, 0xFFFFFFFF, 0x4000):
            data = bytearray(0x4000)
            data[:4] = b'PDFF'
            struct.pack_into('>4sIB', data, 0x80, b'INFO', length, 0)
            with self.subTest(length=length), self.assertRaises(ValueError):
                inspect_sections(bytes(data))
        data = fixture([(b'INFO', 0x4000-0x80-4, 0)])
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            inspect_sections(data)

    def test_header_and_input_bounds_rejected(self):
        for data in (b'', bytes(0x4000), bytes(0x4001), bytearray(0x4000)):
            with self.subTest(kind=type(data).__name__), self.assertRaises(ValueError):
                inspect_sections(data)

    def test_buffer_boundary_can_end_a_nonterminal_section(self):
        _, rows = inspect_sections(fixture([(b'INFO', 0x4000-0x80, 0)]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].offset+rows[0].byte_length, 0x4000)

    def test_native_lookup_matches_bounded_inspection(self):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        for rows in [[(b'INFO', 32, 0), (b'TEST', 16, 0), (b'KANA', 20, 1)],
                     [(b'INFO', 32, 7), (b'KANA', 20, 1)],
                     [(b'INFO', 32, 0), (b'INFO', 16, 1)],
                     [(b'INFO', 0x4000-0x80, 0)]]:
            with self.subTest(rows=rows):
                report = verify(path.read_bytes(), fixture(rows), probe_tags=(b'KANA', b'NOPE'))
                self.assertTrue(report['missing_tag_verified'])
                self.assertFalse(report['native_lookup_mocked'])
                self.assertFalse(report['integrity_verified'])

    def test_wrong_executable_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'wrong', fixture([(b'INFO', 32, 1)]))
