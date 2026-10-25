"""Synthetic binary/source fixtures for metadata-only commerce auditing."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_wii_shop_commerce_surface as surface
from tools.inspect_demae_references import sections


def binary(words=()):
    data = bytearray(0x220)
    for index, offset, address, size in ((0, 0x100, 0x80001000, 0x20),
                                        (7, 0x120, 0x80320000, 0x100)):
        struct.pack_into('>I', data, 4 * index, offset)
        struct.pack_into('>I', data, 0x48 + 4 * index, address)
        struct.pack_into('>I', data, 0x90 + 4 * index, size)
    for index, word in enumerate(words):
        struct.pack_into('>I', data, 0x100 + 4 * index, word)
    data[0x124:0x129] = b'Name\0'
    return bytes(data)


class CommerceSurfaceTests(unittest.TestCase):
    def test_only_complete_allowlisted_names_are_reported(self):
        data = b'Name\0prefixTitleName\0TitleName\0https://private.invalid/?secret=value\0'
        rows = surface.marker_offsets(data)
        self.assertEqual(rows['Name'], [0])
        self.assertEqual(rows['TitleName'], [21])
        output = json.dumps(rows)
        self.assertNotIn('private.invalid', output)
        self.assertNotIn('secret', output)
        self.assertNotIn('value', output)

    def test_binary_bound_is_enforced(self):
        with patch.object(surface, 'MAX_BYTES', 3), self.assertRaises(ValueError):
            surface.marker_offsets(b'abcd')
        with self.assertRaises(ValueError):
            surface.marker_offsets('Name')

    def test_marker_locations_are_section_mapped(self):
        data = binary()
        self.assertEqual(surface.mapped_markers(data, sections(data))['Name'],
                         [{'file_offset': 0x124, 'address': 0x80320004}])

    def test_relative_loads_check_register_instruction_and_signed_offset(self):
        # addi r4,r31,4; addi r4,r30,4; addi r4,r31,-252
        data = binary((0x389f0004, 0x389e0004, 0x389fff04))
        positive = surface.relative_string_loads(data, sections(data),
                    0x80001000, 0x80001008, 0x80320000)
        self.assertEqual([row['instruction'] for row in positive], ['0x80001000'])
        self.assertEqual(positive[0]['marker'], 'Name')
        negative = surface.relative_string_loads(data, sections(data),
                    0x80001008, 0x8000100c, 0x80320100)
        self.assertEqual(negative[0]['target'], '0x80320004')
        with self.assertRaises(ValueError):
            surface.relative_string_loads(data, sections(data),
                                         0x80001001, 0x80001008, 0x80320000)

    def test_native_pointer_can_reference_compiler_shared_string_suffix(self):
        data = bytearray(binary((0x389f0004,)))
        data[0x123] = ord('X')
        self.assertEqual(surface.marker_offsets(bytes(data))['Name'], [])
        rows = surface.relative_string_loads(bytes(data), sections(data),
                                             0x80001000, 0x80001004, 0x80320000)
        self.assertEqual(rows[0]['marker'], 'Name')

    def test_relative_branch_link_callers_exclude_plain_and_absolute_branches(self):
        data = binary((0x48000011, 0x4800000c, 0x48001013))
        self.assertEqual(surface.direct_callers(data, sections(data), 0x80001010), ['0x80001000'])

    def test_native_slices_reject_unmapped_or_oversized_reads(self):
        data = binary()
        for address, size in ((0, 4), (0x80001000, 8193), (0x8000101c, 8), (0x80001000, 0)):
            with self.subTest(address=address, size=size), self.assertRaises(ValueError):
                surface.read_virtual(data, sections(data), address, size)

    def test_original_fingerprint_is_required_before_any_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.bin'
            path.write_bytes(b'synthetic-private-content')
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                surface.audit(path, path, Path(directory))


if __name__ == '__main__':
    unittest.main()
