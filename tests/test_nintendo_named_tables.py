"""Explicit synthetic inline names/identifiers, never production catalog data."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from jwc24.forecast import encode_lz10
from jwc24.lz11 import encode_lz11
from jwc24.nintendo_listdata import (DESCRIPTOR_OFFSET, ListDataFormatError,
                                     NintendoListInspection, inspect_listdata)
from tests.test_nintendo_listdata import synthetic_listdata


def named_fixture(*, id_name='Second \u65e5\u672c\u8a9e \U0001F30F', code_name='Code \u65e5\u672c\u8a9e', kind=3):
    raw = bytearray(synthetic_listdata())
    table1 = len(raw)
    for identifier, code, name, value in ((7, b'Q01', 'First label', 2),
                                         (4, b'Q02', id_name, kind),
                                         (4, b'Q03', 'Duplicate identifier', 9)):
        row = bytearray(b'\xA5' * 0x6C)
        row[0] = identifier
        row[1:4] = code
        encoded = name.encode('utf-16-be') + bytes(2)
        if len(encoded) > 0x66:
            raise ValueError('Synthetic ID name exceeds its field')
        row[4:4 + len(encoded)] = encoded
        row[0x6A] = value
        row[0x6B] = 0x5A
        raw.extend(row)
    table2 = len(raw)
    for code, name in ((b'ABCD', code_name), (b'WXYZ', 'Other code'), (b'ABCD', 'Duplicate code')):
        row = bytearray(b'\xC7' * 0x80)
        row[:4] = code
        encoded = name.encode('utf-16-be') + bytes(2)
        if len(encoded) > 0x7C:
            raise ValueError('Synthetic code name exceeds its field')
        row[4:4 + len(encoded)] = encoded
        raw.extend(row)
    struct.pack_into('>II', raw, DESCRIPTOR_OFFSET + 8, 3, table1)
    struct.pack_into('>II', raw, DESCRIPTOR_OFFSET + 16, 3, table2)
    software = struct.unpack_from('>II', raw, DESCRIPTOR_OFFSET + 24)[1]
    raw[software + 8] = 4
    raw[software + 0xEC + 8] = 7
    struct.pack_into('>I', raw, 4, len(raw))
    return bytes(raw)


class NintendoNamedTableTests(unittest.TestCase):
    def test_both_name_tables_preserve_order_duplicate_ids_raw_bytes_and_storage(self):
        raw = named_fixture()
        result = inspect_listdata(raw)
        self.assertEqual([row.byte_field_00 for row in result.named_id_rows], [7, 4, 4])
        self.assertEqual([row.code_bytes for row in result.named_code_rows], [b'ABCD', b'WXYZ', b'ABCD'])
        self.assertEqual(result.named_id_rows[1].bytes_field_01, b'Q02')
        self.assertEqual(result.named_id_rows[1].name, 'Second \u65e5\u672c\u8a9e \U0001F30F')
        self.assertEqual(result.named_id_rows[1].opaque_byte_6b, 0x5A)
        for row in result.named_id_rows:
            self.assertEqual(row.name_storage, raw[row.file_offset + 4:row.file_offset + 0x6A])
        for row in result.named_code_rows:
            self.assertEqual(row.name_storage, raw[row.file_offset + 4:row.file_offset + 0x80])
        self.assertEqual(result.tables[2].stride, 0x80)
        self.assertNotIn('Second', repr(result))
        self.assertNotIn('ABCD', repr(result.named_code_rows[0]))
        self.assertNotIn('Second', str(result.metadata()))
        self.assertEqual(result.metadata()['named_id_rows'], 3)
        self.assertEqual(result.metadata()['named_code_rows'], 3)
        self.assertNotIn(2, result.metadata()['undecoded_nonempty_tables'])
        self.assertFalse(result.metadata()['complete_catalog_schema_checked'])
        self.assertFalse(result.metadata()['name_table_semantics_complete'])

    def test_first_matching_name_and_software_relation_keep_missing_relations_distinct(self):
        result = inspect_listdata(named_fixture())
        self.assertEqual(result.find_named_id(4).index, 1)
        self.assertEqual(result.find_named_code(b'ABCD').index, 0)
        self.assertEqual(result.named_id_for_software(0).index, 1)
        self.assertIsNone(result.find_named_id(255))
        self.assertIsNone(result.find_named_code(b'MISS'))
        raw = bytearray(named_fixture())
        raw[result.tables[3].offset + 8] = 255
        result = inspect_listdata(bytes(raw))
        self.assertIsNone(result.named_id_for_software(0))
        self.assertEqual(result.metadata()['software_rows_without_named_id'], 1)
        for value in (True, -1, 256, 'private-marker'):
            with self.assertRaises(ListDataFormatError) as error:
                result.find_named_id(value)
            self.assertNotIn('private-marker', str(error.exception))
        for value in (b'abc', b'abcde', 'private-marker'):
            with self.assertRaises(ListDataFormatError):
                result.find_named_code(value)

    def test_classification_preserves_raw_byte_and_maps_all_unknown_kinds_to_ff(self):
        for value in range(256):
            result = inspect_listdata(named_fixture(kind=value))
            self.assertEqual(result.named_id_rows[1].byte_field_6a, value)
            self.assertEqual(result.named_id_for_software(0).classification_result(),
                             value if 1 <= value <= 10 else 255)

    def test_inline_utf16_has_its_own_bounds_and_cannot_terminate_in_kind_metadata(self):
        self.assertEqual(inspect_listdata(named_fixture(id_name='x' * 50)).named_id_rows[1].name, 'x' * 50)
        self.assertEqual(inspect_listdata(named_fixture(code_name='x' * 61)).named_code_rows[0].name, 'x' * 61)
        good = inspect_listdata(named_fixture())
        for table, length in ((1, 0x66), (2, 0x7C)):
            start = good.tables[table].offset + 4
            raw = bytearray(named_fixture())
            raw[start:start + length] = b'\0x' * (length // 2)
            if table == 1:
                raw[start + length:start + length + 2] = bytes(2)
            with self.assertRaisesRegex(ListDataFormatError, 'termination'):
                inspect_listdata(bytes(raw))
            raw[start:start + 4] = b'\xD8\0\0\0'
            with self.assertRaisesRegex(ListDataFormatError, 'UTF-16'):
                inspect_listdata(bytes(raw))

    def test_new_table_stride_bounds_and_overlap_are_not_inferred_from_the_next_table(self):
        raw = named_fixture()
        result = inspect_listdata(raw)
        for count, offset in ((0xFFFFFFFF, result.tables[2].offset),
                              (3, len(raw) - 0x80), (1, result.tables[1].offset)):
            bad = bytearray(raw)
            struct.pack_into('>II', bad, DESCRIPTOR_OFFSET + 16, count, offset)
            with self.assertRaises(ListDataFormatError):
                inspect_listdata(bytes(bad))

    def test_compression_and_existing_dataclass_constructor_stay_compatible(self):
        raw = named_fixture()
        for wrap in (lambda value: value, encode_lz10, encode_lz11):
            result = inspect_listdata(wrap(raw))
            self.assertEqual(result.find_named_code(b'ABCD').name, 'Code \u65e5\u672c\u8a9e')
        old = inspect_listdata(synthetic_listdata())
        compatible = NintendoListInspection(old.byte_length, old.compression, old.tables,
                                             old.software_rows, old.linked_rows)
        self.assertEqual(compatible.named_id_rows, ())
        self.assertEqual(compatible.named_code_rows, ())

    def test_existing_retained_http_handoff_delivers_the_new_records_without_losing_opaque_fields(self):
        from jwc24.nintendo_http import apply_http_callback, inspect_http_list_download, poll_http_state
        from tests.test_nintendo_http import state, callback, poll
        from tests.test_nintendo_load import csdata, PREFIX
        wire = encode_lz11(named_fixture())
        first = apply_http_callback(state(buffer=b'\xA5' * (len(wire) + 64)),
                                     **callback(chunk=wire[:125]))
        final = apply_http_callback(first.state, **callback(chunk=wire[125:], word_08=0))
        ready = poll_http_state(final.state, **poll())
        result = inspect_http_list_download(csdata([0]), ready, service_prefix=PREFIX, language_code=0)
        self.assertEqual(result.listdata.named_id_for_software(0).bytes_field_01, b'Q02')
        self.assertEqual(result.listdata.find_named_code(b'ABCD').name, 'Code \u65e5\u672c\u8a9e')
        self.assertFalse(result.metadata()['authentication_or_freshness_verified'])
        self.assertFalse(result.listdata.metadata()['name_table_semantics_complete'])

    def test_native_verifier_refuses_unverified_images_before_optional_dependencies(self):
        from tools.verify_nintendo_named_tables import verify_named_tables_native
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_named_tables_native(b'unverified-software', named_fixture())


class NintendoNamedTablesNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/nintendo/v1792/0001-0000003e.app')
        if not path.is_file():
            raise unittest.SkipTest('Private pinned Japanese Nintendo Channel executable unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional Capstone/Unicorn verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_actual_getters_first_matches_inline_unicode_copy_and_all_classification_bytes(self):
        from tools.verify_nintendo_named_tables import verify_named_tables_native
        result = verify_named_tables_native(self.source, named_fixture(), classification_values=tuple(range(256)))
        self.assertEqual(result['native_validator_status'], 0)
        self.assertEqual(result['counts']['classification_bytes_compared'], 256)
        self.assertTrue(result['input_output_object_and_stack_guards_verified'])
        self.assertFalse(result['native_getters_or_copy_helpers_stubbed'])

    def test_unterminated_name_is_local_refusal_not_a_claim_of_native_getter_rejection(self):
        from tools.verify_nintendo_named_tables import verify_named_tables_native
        raw = bytearray(named_fixture())
        table = inspect_listdata(bytes(raw)).tables[1].offset
        raw[table + 4:table + 0x6A] = b'\0x' * 51
        raw[table + 0x6A:table + 0x6C] = bytes(2)
        result = verify_named_tables_native(self.source, bytes(raw))
        self.assertEqual(result['native_validator_status'], 0)
        self.assertFalse(result['independent_inline_name_subset_accepted'])
        self.assertEqual(result['counts']['native_names_copied'], 0)
