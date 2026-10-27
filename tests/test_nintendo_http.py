"""Synthetic callback byte/state cases, never native service responses."""
from dataclasses import replace
from pathlib import Path
import unittest

from jwc24.forecast import encode_lz10
from jwc24.nintendo_http import (NintendoHTTPState, apply_http_callback,
                                 inspect_http_list_download, poll_http_state)
from jwc24.nintendo_load import NintendoLoadError
from tests.test_nintendo_load import csdata, PREFIX
from tests.test_nintendo_listdata import synthetic_listdata


def state(**changes):
    initial = dict(buffer=b'Q' * 64, copied_bytes=0, word_04=2, word_08=2,
                   word_0c=17, error_word_1c=0, error_word_20=0,
                   manager_error_word_2a70=0x1234, manager_error_word_2a74=0x5678,
                   retry_word=-1, skipped_input=False)
    initial.update(changes)
    return NintendoHTTPState(**initial)


def callback(**changes):
    initial = dict(chunk=b'abcde', word_08=2, word_0c=7, word_10=0, word_14=0)
    initial.update(changes)
    return initial


def poll(**changes):
    initial = dict(timer_expired=False, manager_27140_result=0,
                   request_manager_available=True, request_26c80_result=0,
                   request_26c80_error_word=0x7788)
    initial.update(changes)
    return initial


def native_callbacks():
    cases = []
    for copied in (0, 59, 60, 64):
        for size in (0, 5):
            for word08 in (0, 2):
                cases.append((state(copied_bytes=copied), callback(chunk=b'x' * size, word_08=word08)))
    for retry in (-1, 0, 1):
        for detail in (0x3FD21, 0x3FD22, 0x3FD23, 0x3FD24, 0x3FD25, 0x3FD28):
            for word08 in (0, 2):
                cases.append((state(retry_word=retry), callback(word_08=word08, word_10=0xFFFFFF93,
                                                                word_14=detail)))
    return cases


def native_polls():
    cases = []
    for word04 in (0, 1, 2, 3, 4):
        for phase in range(9):
            for expired in (False, True):
                cases.append((state(word_04=word04, word_08=phase), poll(timer_expired=expired)))
    for error in (0, 1, 0xFFFFFF93):
        cases.append((state(word_08=6, error_word_1c=error, error_word_20=77), poll()))
        cases.append((state(word_04=0, error_word_1c=error, error_word_20=77), poll()))
    for result in (-9, 0, 1):
        cases.append((state(word_08=4), poll(manager_27140_result=result)))
        cases.append((state(word_08=7, copied_bytes=5, skipped_input=True), poll(request_26c80_result=result)))
    cases.append((state(word_08=7, copied_bytes=5), poll(request_manager_available=False)))
    for phase in (3, 4):
        cases.append((state(word_08=phase), poll(request_manager_available=False)))
    return cases


class NintendoHTTPTests(unittest.TestCase):
    def test_copy_and_nonerror_completion_preserve_skipped_input_as_distinct(self):
        original = state(copied_bytes=60)
        result = apply_http_callback(original, **callback(word_08=0))
        self.assertTrue(result.input_skipped)
        self.assertEqual(result.retained_bytes, 0)
        self.assertEqual(result.state.copied_bytes, 60)
        self.assertEqual(result.state.buffer, original.buffer)
        self.assertEqual(result.state.word_08, 3)
        self.assertEqual(result.state.retry_word, 0)
        self.assertTrue(result.state.skipped_input)
        fitting = apply_http_callback(state(copied_bytes=59), **callback())
        self.assertEqual(fitting.state.buffer[-5:], b'abcde')
        self.assertEqual(fitting.state.copied_bytes, 64)
        self.assertEqual(fitting.state.word_08, 2)

    def test_callback_opaque_word08_controls_state_handling_and_retry_word(self):
        untouched = apply_http_callback(state(), **callback(chunk=b'', word_10=1, word_14=0x3FD22))
        self.assertEqual(untouched.state.word_08, 2)
        self.assertEqual(untouched.state.word_0c, 17)
        self.assertEqual(untouched.state.retry_word, -1)
        retried = apply_http_callback(state(), **callback(word_08=0, word_10=1, word_14=0x3FD22))
        self.assertTrue(retried.retry_scheduled)
        self.assertEqual((retried.state.word_04, retried.state.word_08, retried.state.retry_word), (2, 7, 1))
        exhausted = apply_http_callback(retried.state, **callback(word_08=0, word_10=1, word_14=0x3FD22))
        self.assertFalse(exhausted.retry_scheduled)
        self.assertEqual((exhausted.state.word_08, exhausted.state.error_word_1c), (6, 1))

    def test_negative_poll_and_normalized_zero_or_positive_are_not_data_completion(self):
        for error in (0, 1, 0xFFFFFF93):
            for value in (state(word_04=0, error_word_1c=error), state(word_08=6, error_word_1c=error)):
                result = poll_http_state(value, **poll())
                self.assertLess(result.raw_poll_result, 0)
                self.assertEqual(result.manager_result, error if error < 0x80000000 else error - 0x100000000)
                self.assertFalse(result.native_data_phase_reached)
                with self.assertRaises(NintendoLoadError):
                    inspect_http_list_download(csdata([0]), result, service_prefix=PREFIX, language_code=0)

    def test_restart_resets_retained_count_but_does_not_invent_body_bytes(self):
        before = state(word_08=7, copied_bytes=5, skipped_input=True)
        result = poll_http_state(before, **poll())
        self.assertTrue(result.restart_called)
        self.assertTrue(result.request_26c80_called)
        self.assertEqual((result.state.word_04, result.state.word_08, result.state.copied_bytes), (2, 2, 0))
        self.assertEqual(result.state.word_0c, 0)
        self.assertEqual(result.state.buffer, before.buffer)
        self.assertFalse(result.state.skipped_input)
        self.assertFalse(result.native_data_phase_reached)
        failed = poll_http_state(before, **poll(request_26c80_result=-1))
        self.assertEqual(failed.manager_result, -109)
        self.assertEqual(failed.state.copied_bytes, 0)

    def test_exact_retained_raw_or_compressed_body_drives_existing_language_and_record_decoder(self):
        body = synthetic_listdata()
        for wire in (body, encode_lz10(body)):
            initial = state(buffer=b'\xA5' * (len(wire) + 64))
            first = apply_http_callback(initial, **callback(chunk=wire[:100]))
            last = apply_http_callback(first.state, **callback(chunk=wire[100:], word_08=0))
            ready = poll_http_state(last.state, **poll())
            result = inspect_http_list_download(csdata([0]), ready, service_prefix=PREFIX, language_code=0)
            self.assertTrue(ready.native_data_phase_reached)
            self.assertEqual(result.listdata.software_rows[0].title, 'Synthetic title \u65e5\u672c\u8a9e \U0001F30F')
            self.assertNotIn('Synthetic title', repr(ready))
            self.assertNotIn('Synthetic title', str(ready.metadata()))
            self.assertFalse(result.metadata()['authentication_or_freshness_verified'])
            with self.assertRaises(NintendoLoadError):
                inspect_http_list_download(csdata([1]), ready, service_prefix=PREFIX, language_code=0)
            # Even a native data phase cannot excuse previously dropped input.
            with self.assertRaises(NintendoLoadError):
                inspect_http_list_download(csdata([0]), replace(ready, state=replace(ready.state, skipped_input=True)),
                                            service_prefix=PREFIX, language_code=0)

    def test_explicit_types_and_bounds_reject_without_echo(self):
        for bad in (state(copied_bytes=65), state(word_08='private-marker'), state(retry_word=True),
                    state(buffer=bytearray(64)), state(skipped_input=1)):
            with self.assertRaises(ValueError) as caught:
                apply_http_callback(bad, **callback())
            self.assertNotIn('private-marker', str(caught.exception))
        for values in (callback(chunk=bytearray(1)), callback(word_10=-1), callback(word_14=True)):
            with self.assertRaises(ValueError):
                apply_http_callback(state(), **values)
        projected = poll_http_state(state(), **poll())
        with self.assertRaises(NintendoLoadError):
            inspect_http_list_download(csdata([0]), replace(projected, raw_poll_result=False),
                                        service_prefix=PREFIX, language_code=0)
        from tools.verify_nintendo_http import verify_http_native
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_http_native(b'unverified-original', state(), callback=callback())


class NintendoHTTPNativeTests(unittest.TestCase):
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

    def test_complete_native_callback_copy_and_retry_or_error_branches(self):
        from tools.verify_nintendo_http import verify_http_native
        for index, (before, inputs) in enumerate(native_callbacks()):
            with self.subTest(case=index):
                report = verify_http_native(self.source, before, callback=inputs)
                self.assertFalse(report['original_callback_copy_and_state_branches_stubbed'])
                self.assertTrue(report['immutable_input_output_state_and_stack_guards_verified'])

    def test_complete_native_virtual_poll_restart_wrapper_and_result_normalizer(self):
        from tools.verify_nintendo_http import verify_http_native
        for index, (before, inputs) in enumerate(native_polls()):
            with self.subTest(case=index):
                report = verify_http_native(self.source, before, poll=inputs)
                self.assertFalse(report['original_poll_restart_and_normalizer_stubbed'])
                self.assertTrue(report['immutable_input_output_state_and_stack_guards_verified'])
