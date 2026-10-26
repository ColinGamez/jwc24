"""Synthetic ListData table/record fixtures, never published as a real catalog."""
from pathlib import Path
import contextlib
import io
import json
import struct
import tempfile
import unittest
from unittest.mock import patch

from jwc24.forecast import encode_lz10
from jwc24.lz11 import encode_lz11
from jwc24.nintendo_listdata import (
    DESCRIPTOR_OFFSET, MAX_INPUT_BYTES, MAX_LIST_BYTES, MIN_LIST_BYTES, ListDataFormatError,
    decode_listdata, inspect_listdata,
)
from tools.inspect_nintendo_listdata import main


def synthetic_listdata(*, titles=('Synthetic title \u65e5\u672c\u8a9e \U0001F30F', 'Second synthetic title')):
    raw = bytearray(MIN_LIST_BYTES)
    raw[2] = 6
    software_offset = len(raw)
    raw.extend(bytes(0xEC * len(titles)))
    linked_offset = len(raw)
    raw.extend(bytes(0x116 * len(titles)))
    struct.pack_into('>II', raw, DESCRIPTOR_OFFSET + 3 * 8, len(titles), software_offset)
    struct.pack_into('>II', raw, DESCRIPTOR_OFFSET + 5 * 8, len(titles), linked_offset)
    for index, title in enumerate(titles):
        title_reference = len(raw)
        raw.extend(b'TEST' + title.encode('utf-16-be') + bytes(2))
        software = software_offset + index * 0xEC
        raw[software + 8] = index + 1
        struct.pack_into('>I', raw, software + 0x0C, title_reference)
        row = linked_offset + index * 0x116
        struct.pack_into('>IHI', raw, row,
                         software_offset + (len(titles) - index - 1) * 0xEC, index + 1, 0x12345678 + index)
        raw[row + 0x0A] = 10
        raw[row + 0x0B] = 3
        raw[row + 0x1A] = 2
        raw[row + 0x1B] = index & 1
        raw[row + 0x1C] = 1
    struct.pack_into('>I', raw, 4, len(raw))
    return bytes(raw)


def word(raw, offset, value):
    data = bytearray(raw)
    struct.pack_into('>I', data, offset, value)
    return bytes(data)


class NintendoListDataTests(unittest.TestCase):
    def test_software_titles_and_cross_row_links_decode_in_native_order(self):
        result = inspect_listdata(synthetic_listdata())
        self.assertEqual(len(result.software_rows), 2)
        self.assertEqual(result.software_rows[0].title, 'Synthetic title \u65e5\u672c\u8a9e \U0001F30F')
        self.assertEqual(result.software_rows[0].title_prefix, b'TEST')
        self.assertEqual([row.software_index for row in result.linked_rows], [1, 0])
        self.assertEqual(result.linked_rows[0].u32_field_06, 0x12345678)
        self.assertEqual(result.linked_rows[0].byte_field_0a, 10)
        self.assertFalse(result.linked_rows[0].flag_field_1b)
        self.assertNotIn('Synthetic', repr(result))
        self.assertNotIn('Synthetic', repr(result.metadata()))
        for key in ('crc_or_signature_checked', 'freshness_checked',
                    'complete_catalog_schema_checked', 'media_playability_checked',
                    'native_download_or_ui_verified'):
            self.assertFalse(result.metadata()[key])

    def test_missing_title_and_software_link_remain_missing(self):
        raw = synthetic_listdata()
        result = inspect_listdata(raw)
        raw = word(raw, result.tables[3].offset + 0x0C, 0)
        raw = word(raw, result.tables[5].offset, 0)
        result = inspect_listdata(raw)
        self.assertIsNone(result.software_rows[0].title)
        self.assertIsNone(result.linked_rows[0].software_index)
        self.assertEqual(result.metadata()['linked_rows_without_software'], 1)

    def test_unknown_header_word_is_not_mislabeled_crc_integrity(self):
        raw = word(synthetic_listdata(), 8, 0xDEADBEEF)
        self.assertEqual(len(inspect_listdata(raw).software_rows), 2)
        self.assertFalse(inspect_listdata(raw).metadata()['crc_or_signature_checked'])

    def test_prefix_declared_length_and_table_byte_ranges_are_bounded(self):
        raw = synthetic_listdata()
        for bad in (raw[:MIN_LIST_BYTES - 1], word(raw, 4, len(raw) + 1),
                    word(raw, DESCRIPTOR_OFFSET + 3 * 8, 0xFFFFFFFF),
                    word(raw, DESCRIPTOR_OFFSET + 3 * 8 + 4, MIN_LIST_BYTES - 1),
                    word(raw, DESCRIPTOR_OFFSET + 3 * 8 + 4, len(raw)),
                    word(raw, DESCRIPTOR_OFFSET + 5 * 8 + 4, MIN_LIST_BYTES)):
            with self.subTest(size=len(bad)), self.assertRaises(ListDataFormatError):
                inspect_listdata(bad)
        bad = bytearray(raw); bad[2] = 7
        with self.assertRaises(ListDataFormatError):
            inspect_listdata(bytes(bad))

    def test_exact_record_links_cannot_point_into_middle_or_missing_rows(self):
        raw = synthetic_listdata(); result = inspect_listdata(raw)
        for reference in (1, result.tables[3].offset + 1,
                          result.tables[3].offset + 2 * 0xEC):
            with self.subTest(reference=reference), self.assertRaisesRegex(ListDataFormatError, 'exact software record'):
                inspect_listdata(word(raw, result.tables[5].offset, reference))

    def test_utf16_titles_and_terminators_are_independently_bounded(self):
        raw = synthetic_listdata(); result = inspect_listdata(raw)
        pointer_field = result.tables[3].offset + 0x0C
        for reference in (4, len(raw), result.software_rows[0].title_reference + 1,
                          result.tables[3].offset):
            with self.subTest(reference=reference), self.assertRaises(ListDataFormatError):
                inspect_listdata(word(raw, pointer_field, reference))
        bad = bytearray(raw); start = result.software_rows[0].title_reference + 4
        bad[start:start + 2] = b'\xD8\x00'
        with self.assertRaisesRegex(ListDataFormatError, 'UTF-16'):
            inspect_listdata(bytes(bad))
        self.assertEqual(len(inspect_listdata(synthetic_listdata(titles=('x' * 499,))).software_rows[0].title), 499)
        with self.assertRaisesRegex(ListDataFormatError, 'termination'):
            inspect_listdata(synthetic_listdata(titles=('x' * 500,)))

    def test_native_linked_enum_and_boolean_limits(self):
        raw = synthetic_listdata(); offset = inspect_listdata(raw).tables[5].offset
        for relative, value in ((0x0A, 11), (0x1B, 2), (0x1C, 2)):
            bad = bytearray(raw); bad[offset + relative] = value
            with self.subTest(relative=relative), self.assertRaisesRegex(ListDataFormatError, 'native bounds'):
                inspect_listdata(bytes(bad))

    def test_undecoded_nonempty_table_remains_explicitly_unresolved(self):
        raw = bytearray(synthetic_listdata()); offset = len(raw); raw.extend(b'opaque-table')
        struct.pack_into('>II', raw, DESCRIPTOR_OFFSET + 14 * 8, 1, offset)
        struct.pack_into('>I', raw, 4, len(raw))
        result = inspect_listdata(bytes(raw))
        self.assertEqual(result.metadata()['undecoded_nonempty_tables'], [14])
        self.assertFalse(result.metadata()['complete_catalog_schema_checked'])

    def test_compression_is_bounded_before_decoding_and_preserves_record_titles(self):
        raw = synthetic_listdata()
        for encoder in (encode_lz10, encode_lz11):
            encoded = encoder(raw)
            extended = encoded[:1] + bytes(3) + len(raw).to_bytes(4, 'little') + encoded[4:]
            for payload in (encoded, extended):
                self.assertEqual(inspect_listdata(payload).software_rows, inspect_listdata(raw).software_rows)
        with patch('jwc24.nintendo_listdata.decode_lz10', side_effect=AssertionError('unbounded decode')):
            with self.assertRaises(ListDataFormatError):
                decode_listdata(b'\x10' + (MAX_LIST_BYTES + 1).to_bytes(3, 'little'))

    def test_cli_keeps_title_data_private_and_reads_a_bounded_amount(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private-title-marker.bin'
            raw = synthetic_listdata(); path.write_bytes(raw)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())['software_titles_present'], 2)
            self.assertNotIn('Synthetic', output.getvalue())
            self.assertNotIn('private-title-marker', output.getvalue())
            self.assertEqual(path.read_bytes(), raw)
        stream = io.BytesIO(bytes(MAX_INPUT_BYTES + 2))
        with patch.object(Path, 'open', return_value=stream), \
             patch.object(stream, 'read', wraps=stream.read) as read, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['synthetic.dat']), 1)
            read.assert_called_once_with(MAX_INPUT_BYTES + 1)


class NintendoListDataNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification package unavailable')
        path = Path('private/nintendo/v1792/0001-0000003e.app')
        if not path.is_file():
            raise unittest.SkipTest('Private original HATJ executable unavailable')
        cls.source = path.read_bytes()

    def native(self, payload=None):
        from tools.verify_nintendo_listdata import verify_listdata_native
        return verify_listdata_native(self.source, payload if payload is not None else synthetic_listdata())

    def test_original_constructor_validator_record_accessors_and_unicode_copy_match(self):
        result = self.native()
        self.assertEqual(result['native_validator_status'], 0)
        self.assertTrue(result['independent_subset_accepted'])
        self.assertEqual(result['counts']['software_records_compared'], 2)
        self.assertEqual(result['counts']['native_titles_copied'], 2)
        self.assertEqual(result['counts']['linked_records_compared'], 2)
        self.assertFalse(result['sdk_helpers_stubbed'])
        self.assertTrue(result['input_and_stack_guards_verified'])

    def test_original_validator_rejects_linked_row_enum_and_boolean_failures(self):
        raw = synthetic_listdata(); offset = inspect_listdata(raw).tables[5].offset
        for relative in (0x0A, 0x1B, 0x1C):
            bad = bytearray(raw); bad[offset + relative] = 11
            with self.subTest(relative=relative):
                result = self.native(bytes(bad))
                self.assertEqual(result['native_validator_status'], 1)
                self.assertFalse(result['independent_subset_accepted'])

    def test_unknown_header_word_has_no_crc_check_in_selected_native_consumer(self):
        result = self.native(word(synthetic_listdata(), 8, 0xDEADBEEF))
        self.assertEqual(result['native_validator_status'], 0)
        self.assertEqual(result['counts']['native_titles_copied'], 2)
        self.assertFalse(result['crc_or_signature_checked'])

    def test_strict_local_title_and_size_policies_are_separate_from_native_gate(self):
        raw = synthetic_listdata()
        for bad in (word(raw, 4, len(raw) + 1),
                    synthetic_listdata(titles=('x' * 500,))):
            with self.subTest(size=len(bad)):
                result = self.native(bad)
                self.assertEqual(result['native_validator_status'], 0)
                self.assertFalse(result['independent_subset_accepted'])
                self.assertEqual(result['counts']['native_titles_copied'], 0)

    def test_malformed_native_count_is_trapped_by_read_guard_not_called_valid(self):
        raw = synthetic_listdata()
        raw = word(raw, DESCRIPTOR_OFFSET + 5 * 8 + 4, len(raw) - 1)
        with self.assertRaisesRegex(ValueError, 'read exceeds synthetic bounds'):
            self.native(raw)


if __name__ == '__main__':
    unittest.main()
