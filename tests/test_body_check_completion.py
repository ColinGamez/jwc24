"""Synthetic HFNJ completion buffers only; no saves, measurements or service IO."""
import contextlib
import io
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import zlib

from jwc24.body_check import BodyCheckFormatError, MAX_DATASET_BYTES
from jwc24.body_check_completion import (
    BodyCheckCompletionError, evaluate_dataset_read_completion,
    evaluate_header_pair_gate, inspect_dataset_header_gate,
)
from tools.verify_body_check_completion import (
    main, synthetic_header_pairs, synthetic_read_cases,
    verify_header_pair_gate, verify_read_completion,
)


def buffer(*, good_crc=True, first=1, second=0):
    value = bytearray(MAX_DATASET_BYTES)
    value[4:12] = b'opaque!!'
    struct.pack_into('>HH', value, 12, first, second)
    struct.pack_into('>I', value, 0, zlib.crc32(value[4:16]) ^ int(not good_crc))
    value[16:30] = b'private-marker'
    return bytes(value)


def inputs(**changes):
    values = dict(read_result=0, latched_flag=False, diagnostic_code=987654321,
                  converted_reader_diagnostic=None)
    values.update(changes)
    return values


class BodyCheckCompletionTests(unittest.TestCase):
    def test_return_one_without_header_check_is_distinct_from_crc_matching_read(self):
        unverified = evaluate_dataset_read_completion(buffer(good_crc=False), **inputs(read_result=2))
        self.assertEqual(unverified.native_return, 1)
        self.assertTrue(unverified.read_invoked)
        self.assertFalse(unverified.header_crc_checked)
        self.assertIsNone(unverified.header_crc_matches)
        self.assertFalse(unverified.buffer_cleared)
        self.assertEqual(unverified.diagnostic_code, 987654321)
        self.assertEqual(unverified.buffer, buffer(good_crc=False))
        checked = evaluate_dataset_read_completion(buffer(), **inputs())
        self.assertEqual(checked.native_return, 1)
        self.assertTrue(checked.header_crc_checked)
        self.assertTrue(checked.header_crc_matches)
        # A matching new header does not clear the native diagnostic word.
        self.assertEqual(checked.diagnostic_code, 987654321)
        for result in (unverified, checked):
            self.assertNotIn('private-marker', repr(result))
            self.assertNotIn('987654321', repr(result))
            self.assertNotIn('private-marker', json.dumps(result.metadata()))
            self.assertFalse(result.metadata()['freshness_or_authentication_verified'])

    def test_prior_latched_flag_skips_read_and_preserves_every_explicit_state_value(self):
        for status in (0, 2, 5, 0xB006, 0xFFFFFFFF):
            result = evaluate_dataset_read_completion(buffer(), **inputs(read_result=status, latched_flag=True))
            self.assertEqual(result.native_return, 0)
            self.assertFalse(result.read_invoked)
            self.assertFalse(result.header_crc_checked)
            self.assertFalse(result.diagnostic_conversion_requested)
            self.assertTrue(result.latched_flag)
            self.assertEqual(result.buffer, buffer())
            self.assertEqual(result.diagnostic_code, 987654321)

    def test_bad_crc_and_explicit_read_errors_clear_only_the_native_buffer(self):
        bad = evaluate_dataset_read_completion(buffer(good_crc=False), **inputs())
        self.assertEqual((bad.native_return, bad.latched_flag, bad.diagnostic_code), (0, True, -999))
        self.assertTrue(bad.header_crc_checked)
        self.assertFalse(bad.header_crc_matches)
        self.assertEqual(bad.buffer, bytes(MAX_DATASET_BYTES))
        for status in (1, 3, 4, 0xB006, 0xFFFFFFFF, 0x80000000):
            result = evaluate_dataset_read_completion(buffer(), **inputs(read_result=status))
            self.assertEqual((result.native_return, result.latched_flag, result.diagnostic_code), (0, True, -5))
            self.assertFalse(result.header_crc_checked)
            self.assertEqual(result.buffer, bytes(MAX_DATASET_BYTES))
        converted = evaluate_dataset_read_completion(
            buffer(), **inputs(read_result=5, converted_reader_diagnostic=-77))
        self.assertTrue(converted.diagnostic_conversion_requested)
        self.assertEqual(converted.diagnostic_code, -77)
        self.assertEqual(converted.buffer, bytes(MAX_DATASET_BYTES))
        with self.assertRaisesRegex(BodyCheckCompletionError, 'explicit converted'):
            evaluate_dataset_read_completion(buffer(), **inputs(read_result=5))

    def test_only_header_bytes_affect_crc_and_opaque_pair_gate(self):
        for first, second in synthetic_header_pairs():
            data = buffer(first=first, second=second)
            inspection = inspect_dataset_header_gate(data)
            self.assertEqual(inspection.gate_result, first > 1 or first == 1 and second != 0)
            self.assertTrue(inspection.metadata()['opaque_header_pair_gate_checked'])
            self.assertFalse(inspection.metadata()['record_semantics_checked'])
            changed = bytearray(data)
            changed[16] ^= 1
            changed[-1] ^= 1
            self.assertEqual(inspect_dataset_header_gate(bytes(changed)), inspection)
        with self.assertRaises(BodyCheckFormatError):
            inspect_dataset_header_gate(buffer(good_crc=False))
        self.assertEqual(inspect_dataset_header_gate(buffer()[:16]).inspection.byte_length, 16)

    def test_state_bounds_and_wrong_original_refuse_without_echoing_inputs(self):
        for value in (bytes(15), bytes(MAX_DATASET_BYTES - 1), bytes(MAX_DATASET_BYTES + 1), bytearray(buffer())):
            with self.assertRaises(BodyCheckCompletionError):
                evaluate_dataset_read_completion(value, **inputs())
        for field, value in (('read_result', -1), ('read_result', 1 << 32),
                             ('read_result', True), ('latched_flag', 1),
                             ('diagnostic_code', 1 << 31),
                             ('converted_reader_diagnostic', 'private-marker')):
            with self.subTest(field=field), self.assertRaises(BodyCheckCompletionError) as caught:
                evaluate_dataset_read_completion(buffer(), **inputs(**{field: value}))
            self.assertNotIn('private-marker', str(caught.exception))
        for pair in ((-1, 0), (65536, 0), (0, True), (0, 'private-marker')):
            with self.assertRaises(BodyCheckCompletionError):
                evaluate_header_pair_gate(*pair)
        for verifier, cases in ((verify_read_completion, synthetic_read_cases()),
                                (verify_header_pair_gate, synthetic_header_pairs())):
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                verifier(b'private-marker', cases)

    def test_cli_filesystem_failure_never_echoes_private_path(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-marker')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(main(['private-marker']), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('private-marker', errors.getvalue())


class BodyCheckCompletionNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/body_check/v256/0001-0000000e.dol')
        if not path.is_file():
            raise unittest.SkipTest('Pinned private original HFNJ v256 application unavailable')
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_complete_original_read_consumer_states_and_returned_length_independence(self):
        report = verify_read_completion(self.source, synthetic_read_cases())
        self.assertEqual(report['read_consumer_cases'], 25)
        self.assertTrue(report['complete_original_read_consumer_executed'])
        self.assertTrue(report['dataset_reads_bounded_to_header'])
        self.assertTrue(report['reported_length_not_used_by_selected_consumer'])
        self.assertTrue(report['state_input_and_stack_guards_verified'])
        self.assertFalse(report['original_copy_clear_and_crc_stubbed'])
        self.assertFalse(report['opaque_payload_semantics_or_authentication_verified'])
        self.assertFalse(report['native_ui_verified'])

    def test_complete_original_header_pair_predicate_and_copy(self):
        report = verify_header_pair_gate(self.source, synthetic_header_pairs())
        self.assertEqual(report['opaque_header_pair_cases'], 15)
        self.assertTrue(report['complete_original_header_pair_gate_executed'])
        self.assertTrue(report['input_and_stack_guards_verified'])
        self.assertFalse(report['original_copy_or_header_predicate_stubbed'])
        self.assertFalse(report['header_word_meanings_verified'])
        self.assertFalse(report['native_menu_transition_or_display_verified'])

    def test_harness_rejects_unbounded_or_ambiguous_case_sets_before_execution(self):
        for cases in ([], synthetic_read_cases() * 3, [{}], [dict(synthetic_read_cases()[0], reported_length=32769)]):
            with self.assertRaises(ValueError):
                verify_read_completion(self.source, cases)
        for pairs in ([], [(0, 0)] * 257, [(0,)], [(0, True)]):
            with self.assertRaises(ValueError):
                verify_header_pair_gate(self.source, pairs)


if __name__ == '__main__':
    unittest.main()
