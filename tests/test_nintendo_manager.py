"""Supplied manager-state projection and complete original callback composition."""
from dataclasses import replace
from pathlib import Path
import unittest

from jwc24.forecast import encode_lz10
from jwc24.nintendo_http import inspect_http_list_download, poll_http_state
from jwc24.nintendo_load import NintendoLoadError
from jwc24.nintendo_manager import (NintendoManagerState, apply_manager_callback,
                                    build_manager_frame)
from tests.test_nintendo_http import state, poll
from tests.test_nintendo_load import csdata, PREFIX
from tests.test_nintendo_listdata import synthetic_listdata
from tools.verify_nintendo_manager import LOADER_CONTEXT_WORD, verify_manager_native


def manager(**changes):
    fields = dict(manager_present=True, callback_present=True,
                  callback_context_word=LOADER_CONTEXT_WORD, shared_word=3,
                  word_2c20=0x773311, error_word_2d28=0, detail_word_2d2c=0,
                  response_word_2d30=200, flag_word_2d38=0)
    fields.update(changes)
    return NintendoManagerState(**fields)


def compose(snapshot=None, chunk=b'abcde', before=None):
    return apply_manager_callback(state() if before is None else before,
                                  manager() if snapshot is None else snapshot,
                                  chunk, loader_context_word=LOADER_CONTEXT_WORD)


def native_cases():
    cases = []
    for error in (-2, -1, *range(18), 0x7FFFFFFF, 0x80000000):
        for flag in (0, 1, 2):
            cases.append((state(), manager(error_word_2d28=error & 0xFFFFFFFF,
                                           flag_word_2d38=flag), b'abcde'))
    for detail in (*range(-17, 2), 0x7FFFFFFF, 0x80000000):
        for retry in (-1, 0, 1):
            cases.append((state(retry_word=retry), manager(error_word_2d28=14,
                          detail_word_2d2c=detail & 0xFFFFFFFF), b'abcde'))
    for response in (0, 1, 198, 199, 200, 201, 298, 299, 300, 301, 304,
                     400, 401, 403, 404, 500, 503, 504, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
        for error in (0, 8):
            for flag in (0, 1, 2):
                cases.append((state(), manager(error_word_2d28=error, response_word_2d30=response,
                                               flag_word_2d38=flag), b'abcde'))
    for copied in (0, 59, 60, 64):
        for chunk in (b'', b'abcde'):
            for shared in (0, 2, 3, 4, 5, 0xFFFFFFFF):
                cases.append((state(copied_bytes=copied), manager(shared_word=shared,
                              error_word_2d28=14, detail_word_2d2c=(-10 & 0xFFFFFFFF)), chunk))
    for availability in ({'manager_present': False}, {'callback_present': False},
                          {'callback_context_word': 0}):
        for chunk in (b'', b'abcde'):
            cases.append((state(copied_bytes=59), manager(**availability), chunk))
    # Larger copy executes the original PPC floating-point/memcpy paths too.
    cases.append((state(buffer=b'Q' * 4096), manager(), bytes(range(256)) * 8))
    return cases


class NintendoManagerTests(unittest.TestCase):
    def test_success_frame_and_consumer_keep_supplied_words_and_context(self):
        result = compose()
        self.assertEqual(result.frame.word_08, 3)
        self.assertEqual(result.frame.word_0c, 0x773311)
        self.assertEqual(result.frame.callback_context_word, LOADER_CONTEXT_WORD)
        self.assertEqual((result.frame.word_10, result.frame.word_14), (0, 0))
        self.assertEqual(result.state.buffer[:5], b'abcde')
        self.assertEqual((result.state.copied_bytes, result.state.word_08,
                          result.state.retry_word), (5, 3, 0))
        for error in (0, 8):
            for response in range(200, 300):
                frame = build_manager_frame(manager(error_word_2d28=error,
                                                     response_word_2d30=response), b'')
                self.assertEqual((frame.word_10, frame.word_14), (0, 0))

    def test_special_and_signed_response_values_preserve_error_precedence(self):
        for status, error in ((503, -107), (404, -108), (304, -209), (401, -209),
                              (403, -209), (500, -209), (400, -109),
                              (0x80000000, -109), (0xFFFFFFFF, -109)):
            for flag in (0, 1, 2):
                frame = build_manager_frame(manager(response_word_2d30=status, flag_word_2d38=flag), b'')
                wanted = -110 if error == -109 and flag == 1 else error
                self.assertEqual(frame.word_10, wanted & 0xFFFFFFFF)
                self.assertEqual(frame.word_14, (status + 268000) & 0xFFFFFFFF)
        frame = build_manager_frame(manager(error_word_2d28=1, response_word_2d30=404), b'')
        self.assertEqual((frame.word_10, frame.word_14), (-109 & 0xFFFFFFFF, 260100))

    def test_actual_inner_numeric_maps_include_holes_and_outside_domains(self):
        for error in range(-2, 18):
            frame = build_manager_frame(manager(error_word_2d28=error & 0xFFFFFFFF), b'')
            if error in (0, 8):
                self.assertEqual((frame.word_10, frame.word_14), (0, 0))
                continue
            wanted = 260001 if error == -1 else 260000 + 100 * error if 1 <= error <= 13 or error == 15 else 0
            self.assertEqual(frame.word_14, wanted if error != 14 else 261400)
        for detail in range(-17, 2):
            frame = build_manager_frame(manager(error_word_2d28=14,
                                                detail_word_2d2c=detail & 0xFFFFFFFF), b'')
            self.assertEqual(frame.word_14, 261400 - detail if -16 <= detail <= 0 and detail != -4 else 0)

    def test_retry_details_reach_actual_consumer_and_latch_only_from_minus_one(self):
        for detail in (-10, -11, -12, -16):
            for retry in (-1, 0, 1):
                result = compose(manager(error_word_2d28=14, detail_word_2d2c=detail & 0xFFFFFFFF),
                                 before=state(retry_word=retry))
                self.assertEqual(result.callback.retry_scheduled, retry == -1)
                self.assertEqual(result.state.word_08, 7 if retry == -1 else 6)
                self.assertEqual(result.state.retry_word, 1 if retry == -1 else retry)

    def test_shared_two_bypasses_errors_after_copy_and_null_context_preserves_state(self):
        original = state()
        result = compose(manager(shared_word=2, error_word_2d28=1), before=original)
        self.assertEqual(result.state.word_08, original.word_08)
        self.assertEqual(result.state.error_word_1c, original.error_word_1c)
        self.assertEqual(result.state.retry_word, original.retry_word)
        self.assertEqual(result.state.copied_bytes, 5)
        for change in ({'manager_present': False}, {'callback_present': False}, {'callback_context_word': 0}):
            result = compose(manager(**change), before=original)
            self.assertEqual(result.state, original)
            self.assertIsNone(result.callback)
            self.assertEqual(result.frame is not None, 'callback_context_word' in change)

    def test_context_is_not_redirected_to_another_supplied_loader(self):
        other = manager(callback_context_word=0x12345678)
        self.assertEqual(build_manager_frame(other, b'').callback_context_word, 0x12345678)
        with self.assertRaisesRegex(NintendoLoadError, 'context'):
            compose(other)
        # An absent manager/callback invokes no context, even if its stored word differs.
        self.assertIsNone(compose(replace(other, manager_present=False)).frame)
        with self.assertRaises(NintendoLoadError):
            apply_manager_callback(state(), manager(), b'', loader_context_word=0)

    def test_dropped_body_remains_incomplete_despite_zero_derived_error(self):
        original = state(copied_bytes=60)
        result = compose(before=original)
        self.assertEqual(result.frame.word_10, 0)
        self.assertEqual(result.state.word_08, 3)
        self.assertEqual(result.state.copied_bytes, 60)
        self.assertTrue(result.state.skipped_input)
        projected = poll_http_state(result.state, **poll())
        with self.assertRaises(NintendoLoadError):
            inspect_http_list_download(csdata([0]), projected, service_prefix=PREFIX, language_code=0)

    def test_actual_compressed_body_retained_across_manager_callback_and_list_handoff(self):
        body = encode_lz10(synthetic_listdata())
        result = compose(chunk=body, before=state(buffer=b'Q' * (len(body) + 10)))
        projected = poll_http_state(result.state, **poll())
        inspection = inspect_http_list_download(csdata([0]), projected, service_prefix=PREFIX, language_code=0)
        self.assertEqual(inspection.listdata.software_rows[0].title, 'Synthetic title \u65e5\u672c\u8a9e \U0001F30F')
        self.assertEqual(result.state.buffer[result.state.copied_bytes:], b'Q' * 10)
        self.assertFalse(result.metadata()['network_authentication_or_catalog_completion_verified'])

    def test_strict_explicit_input_and_private_values_do_not_leak(self):
        for invalid in (replace(manager(), manager_present=1), replace(manager(), callback_present=0),
                        replace(manager(), shared_word=True), replace(manager(), detail_word_2d2c=-1),
                        replace(manager(), response_word_2d30=0x100000000),
                        replace(manager(), callback_context_word='private-marker')):
            with self.assertRaises(NintendoLoadError) as caught:
                build_manager_frame(invalid, b'')
            self.assertNotIn('private-marker', str(caught.exception))
        with self.assertRaises(NintendoLoadError):
            build_manager_frame(None, b'')
        with self.assertRaises(NintendoLoadError):
            build_manager_frame(manager(), bytearray())
        result = compose(chunk=b'private-marker')
        self.assertNotIn('private-marker', repr(result))
        self.assertNotIn('private-marker', repr(result.frame))
        self.assertNotIn('private-marker', str(result.metadata()))
        self.assertNotIn(str(LOADER_CONTEXT_WORD), repr(manager()))
        self.assertFalse(result.frame.metadata()['inner_state_independently_verified'])

    def test_native_harness_rejects_wrong_original_before_execution(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_manager_native(b'unverified-original', state(), manager(), b'')


class NintendoManagerNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/nintendo/v1792/0001-0000003e.app')
        if not path.is_file():
            raise unittest.SkipTest('Private pinned Nintendo Channel executable is unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional Capstone/Unicorn verification dependencies are unavailable')
        cls.source = path.read_bytes()

    def test_original_thunk_relay_frame_context_error_maps_and_callback_copy(self):
        for index, (before, snapshot, chunk) in enumerate(native_cases()):
            with self.subTest(case=index):
                report = verify_manager_native(self.source, before, snapshot, chunk)
                self.assertFalse(report['original_thunk_relay_predicates_error_maps_and_callback_stubbed'])
                self.assertFalse(report['original_byte_copy_stubbed'])
                self.assertTrue(report['immutable_input_output_state_and_stack_guards_verified'])

    def test_original_compressed_list_bytes_through_manager_and_consumer(self):
        body = encode_lz10(synthetic_listdata())
        report = verify_manager_native(self.source, state(buffer=b'Q' * (len(body) + 10)), manager(), body)
        self.assertEqual(report['retained_bytes'], len(body))
        self.assertEqual(report['counts']['native_copy'], 1)
