"""Synthetic FD fields and native RAM comparisons; no real startup response."""
from pathlib import Path
import contextlib
import io
import json
import struct
import tempfile
import unittest
from unittest.mock import patch

from jwc24.cmoc import CMOCFormatError, ResponseHeader
from jwc24.cmoc_startup import (
    FIRST_DATA_TAG, decode_first_data_record, encode_first_data_record,
    inspect_first_data_response,
)
from tools.inspect_cmoc_startup import main


def record(*, word_4=0x12345678, byte_8=2, byte_9=3, u16_a=0x4567):
    return encode_first_data_record(word_4=word_4, byte_8=byte_8, byte_9=byte_9,
                                    u16_a=u16_a, evidence_ref='synthetic record fixture, not real service data')


def response(records, *, byte_2=4, byte_3=5):
    return struct.pack('>HBBII20x', FIRST_DATA_TAG, byte_2, byte_3, 0x11223344, 0x55667788) + b''.join(records)


class CMOCStartupTests(unittest.TestCase):
    def test_record_round_trip_preserves_unsigned_fields_without_claiming_semantics(self):
        raw = record(); result = decode_first_data_record(raw)
        self.assertEqual(result.byte_length, 12)
        self.assertEqual((result.word_4, result.byte_8, result.byte_9, result.u16_a),
                         (0x12345678, 2, 3, 0x4567))
        self.assertNotIn(str(0x12345678), repr(result))
        self.assertEqual(result.metadata()['opaque_extension_bytes'], 0)
        for key in ('complete_field_meanings_checked', 'authenticated_or_current_service_data',
                    'native_startup_or_menu_verified'):
            self.assertFalse(result.metadata()[key])

    def test_every_truncated_fixed_record_and_oversized_record_is_rejected(self):
        raw = record()
        for size in range(12):
            with self.subTest(size=size), self.assertRaises(CMOCFormatError):
                decode_first_data_record(raw[:size])
        with self.assertRaises(CMOCFormatError):
            decode_first_data_record(raw + bytes(85))

    def test_wrong_tags_zero_sizes_and_length_mismatch_are_safe_subset_errors(self):
        for tag, size in ((0, 12), (0x5858, 12), (FIRST_DATA_TAG, 0),
                          (FIRST_DATA_TAG, 8), (FIRST_DATA_TAG, 13)):
            raw = bytearray(record()); struct.pack_into('>HH', raw, 0, tag, size)
            with self.subTest(tag=tag, size=size), self.assertRaises(CMOCFormatError):
                decode_first_data_record(bytes(raw))

    def test_unknown_extension_is_retained_without_interpretation(self):
        raw = bytearray(record() + b'private-opaque-extension')
        struct.pack_into('>H', raw, 2, len(raw))
        result = decode_first_data_record(bytes(raw))
        self.assertEqual(result.opaque_extension, b'private-opaque-extension')
        self.assertNotIn('private', repr(result))
        self.assertNotIn('private', repr(result.metadata()))

    def test_encoder_needs_explicit_evidence_and_exact_unsigned_widths(self):
        args = {'word_4': 1, 'byte_8': 2, 'byte_9': 3, 'u16_a': 4,
                'evidence_ref': 'synthetic field evidence'}
        for key, value in (('word_4', -1), ('word_4', 0x100000000),
                           ('byte_8', 256), ('byte_9', True), ('u16_a', 65536),
                           ('evidence_ref', ''), ('evidence_ref', 'private\0marker')):
            with self.subTest(key=key), self.assertRaises(ValueError) as caught:
                encode_first_data_record(**{**args, key: value})
            self.assertNotIn('private', str(caught.exception))
        maximum = decode_first_data_record(record(word_4=0xFFFFFFFF, byte_8=255, byte_9=255, u16_a=65535))
        self.assertEqual(maximum.u16_a, 65535)

    def test_framed_fd_response_correlation_does_not_claim_header_auth_checks(self):
        expected = ResponseHeader(FIRST_DATA_TAG, 0, 0, 0x11223344, 0x55667788)
        result = inspect_first_data_response(response([record()], byte_2=255, byte_3=99), expected_request=expected)
        self.assertTrue(result.request_correlation_checked)
        self.assertFalse(result.metadata()['header_byte_2_and_3_checks_executed'])
        self.assertFalse(result.metadata()['signatures_or_encryption_checked'])
        self.assertFalse(result.metadata()['http_status_or_x_result_checked'])
        self.assertNotIn(str(0x11223344), repr(result.metadata()))
        self.assertFalse(inspect_first_data_response(response([record()])).request_correlation_checked)
        with self.assertRaisesRegex(CMOCFormatError, 'correlation'):
            inspect_first_data_response(response([record()]),
                                         expected_request=ResponseHeader(FIRST_DATA_TAG, 0, 0, 0, 0))

    def test_missing_duplicate_or_unframed_records_are_not_startup_success(self):
        for data in (response([]), response([record(), record()]), response([record()])[:-1]):
            with self.subTest(size=len(data)), self.assertRaises(CMOCFormatError):
                inspect_first_data_response(data)
        other = struct.pack('>HHI', 0x5858, 8, 0)
        result = inspect_first_data_response(response([other, record()]))
        self.assertEqual(result.other_records, 1)
        self.assertEqual(result.metadata()['other_records_not_decoded'], 1)

    def test_cli_reads_bounded_inputs_and_prints_only_scope_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private-selector.bin'
            raw = response([record()]); path.write_bytes(raw)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path)]), 0)
            metadata = json.loads(output.getvalue())
            self.assertEqual(metadata['record_size'], 12)
            self.assertFalse(metadata['native_startup_or_menu_verified'])
            self.assertNotIn('private', output.getvalue())
            self.assertNotIn(str(0x12345678), output.getvalue())
            self.assertEqual(path.read_bytes(), raw)
        stream = io.BytesIO(bytes(1000))
        with patch.object(Path, 'open', return_value=stream), \
             patch.object(stream, 'read', wraps=stream.read) as read, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['synthetic.dat', '--record']), 1)
            read.assert_called_once_with(97)


class CMOCStartupNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependency unavailable')
        path = Path('private/cmoc/v512/0001-0000000c.app')
        if not path.is_file():
            raise unittest.SkipTest('Private original HAPJ v512 executable unavailable')
        cls.source = path.read_bytes()

    def native(self, value):
        from tools.verify_cmoc_startup import verify_first_data_consumer
        return verify_first_data_consumer(self.source, value)

    def test_original_constructor_type_copy_and_state_updates_match_fields(self):
        result = self.native(record())
        self.assertTrue(result['native_constructor_matches_12_byte_encoder'])
        self.assertTrue(result['native_type_predicate_allows_record'])
        self.assertTrue(result['native_fixed_record_copy_and_state_updates_executed'])
        self.assertTrue(result['native_state_fields_match_record'])
        self.assertEqual(result['intercepted_ui_transition_value'], 2)
        self.assertTrue(result['input_and_stack_guards_verified'])
        self.assertFalse(result['http_auth_crypto_or_native_menu_verified'])

    def test_unsigned_extremes_reach_actual_native_state_fields(self):
        for values in ((0, 0, 0), (1, 1, 1), (255, 255, 65535)):
            result = self.native(record(byte_8=values[0], byte_9=values[1], u16_a=values[2]))
            self.assertTrue(result['native_state_fields_match_record'])

    def test_missing_and_wrong_type_records_preserve_state(self):
        raw = bytearray(record()); struct.pack_into('>H', raw, 0, 0x5858)
        for value in (None, bytes(raw)):
            result = self.native(value)
            self.assertFalse(result['native_type_predicate_allows_record'])
            self.assertFalse(result['native_fixed_record_copy_and_state_updates_executed'])
        # Both valid and wrong-type present records request the same local UI
        # transition: that request by itself is not startup/menu acceptance.
        self.assertEqual(self.native(bytes(raw))['intercepted_ui_transition_value'], 2)
        self.assertIsNone(self.native(None)['intercepted_ui_transition_value'])

    def test_generic_tag_zero_native_cast_is_not_the_supported_fd_subset(self):
        raw = bytearray(record()); struct.pack_into('>H', raw, 0, 0)
        result = self.native(bytes(raw))
        self.assertTrue(result['native_type_predicate_allows_record'])
        self.assertTrue(result['native_fixed_record_copy_and_state_updates_executed'])
        self.assertFalse(result['strict_record_subset_accepted'])

    def test_native_short_cast_read_is_trapped_and_oversize_cast_rejects(self):
        raw = bytearray(record()[:8]); struct.pack_into('>H', raw, 2, 8)
        with self.assertRaisesRegex(ValueError, 'read exceeds synthetic record or object bounds'):
            self.native(bytes(raw))
        raw = bytearray(record() + bytes(85)); struct.pack_into('>H', raw, 2, len(raw))
        result = self.native(bytes(raw))
        self.assertFalse(result['native_type_predicate_allows_record'])
        self.assertFalse(result['native_fixed_record_copy_and_state_updates_executed'])


if __name__ == '__main__':
    unittest.main()
