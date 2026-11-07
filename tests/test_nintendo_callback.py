"""Synthetic SDK getter observations; no actual HTTP response or source data."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from jwc24.nintendo_callback import (CONTEXT, ERROR, DETAIL, PHASE, RESPONSE,
                                     NintendoSDKEventInputs, apply_sdk_event4)
from jwc24.nintendo_request import INNER, TICK
from jwc24.nintendo_load import NintendoLoadError
from tests.test_nintendo_request import state as request_state, word
from tests.test_nintendo_http import state as loader_state, poll
from jwc24.nintendo_http import poll_http_state
from tools.verify_nintendo_callback import OBJECT_WORD, LOADER_CONTEXT_WORD, verify_callback_native


def request(*, shared=2, retry=-1, response=200, detail=0x55667788, flag=0,
            inner_callback=0x80026AE0, inner_context=OBJECT_WORD,
            outer_callback=0x800287C0, outer_context=LOADER_CONTEXT_WORD,
            started=(0, 10000), counter=7000):
    value = request_state(phase=shared, retry=retry)
    raw = bytearray(value.storage)
    for offset, item in ((INNER, 0x1234), (INNER + 8, inner_callback), (INNER + 12, inner_context),
                         (0x29AC, outer_callback), (0x29B0, outer_context), (INNER + 0x10, counter),
                         (INNER + 0xF8, started[0]), (INNER + 0xFC, started[1]),
                         (INNER + 0x100, 0xA1B2C3D4), (INNER + 0x118, 9),
                         (INNER + 0x11C, detail), (INNER + 0x120, response), (INNER + 0x128, flag)):
        struct.pack_into('>I', raw, offset, item)
    return replace(value, storage=bytes(raw))


def inputs(**changes):
    values = dict(event_word=4, sdk_handle_word=0x9999, descriptor=b'opaque SDK descriptor', frequency_word=4000)
    values.update(changes)
    return NintendoSDKEventInputs(**values)


def observations(before, *, error=0, detail=0, phase=4, response=200, tick=(0, 20000)):
    values = [(CONTEXT, OBJECT_WORD + INNER), (ERROR, error)]
    if error == 14:
        values.append((DETAIL, detail))
    values.append((PHASE, phase))
    if 4 <= phase <= 0x7FFFFFFF:
        values.append((RESPONSE, response))
    return tuple(values), (tick,) if before.shared_word == 2 else ()


def project(before=None, loader=None, event=None, **observed):
    before = request() if before is None else before
    loader = loader_state(copied_bytes=9, retry_word=before.retry_word) if loader is None else loader
    event = inputs() if event is None else event
    script, ticks = observations(before, **observed)
    return apply_sdk_event4(before, loader, event, loader_context_word=LOADER_CONTEXT_WORD,
                            sdk_results=script, tick_words=ticks)


def native_cases():
    cases = []
    def add(before, event=None, **observed):
        event = inputs() if event is None else event
        script, ticks = observations(before, **observed)
        cases.append((before, loader_state(copied_bytes=9, retry_word=before.retry_word), event, script, ticks))
    for shared in (0, 1, 2, 3, 4, 5, 0xFFFFFFFF):
        for error in (0, 8, 14, 1, 15, 0xFFFFFFFF):
            for phase in (0, 3, 4, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
                add(request(shared=shared), error=error, detail=(-10 & 0xFFFFFFFF), phase=phase, response=503)
    for retry in (-1, 0, 1):
        for flag in (0, 1, 2):
            for detail in (-10, -11, -12, -16, -4, 0, 1):
                add(request(retry=retry, flag=flag), error=14, detail=detail & 0xFFFFFFFF)
    for response in (0, 199, 200, 299, 300, 304, 401, 403, 404, 500, 503, 0x80000000, 0xFFFFFFFF):
        add(request(), response=response)
    for change in ({'inner_callback': 0}, {'inner_context': 0},
                   {'outer_callback': 0}, {'outer_context': 0}):
        for shared in (2, 4):
            add(request(shared=shared, **change), error=14, detail=(-10 & 0xFFFFFFFF))
    for start, finish, frequency in (((0, 0), (0, 0), 4), ((0, 0), (0, 1), 4),
                                    ((0, 1000), (0, 1999), 4000), ((0, 1000), (0, 2000), 4000),
                                    ((0xFFFFFFFF, 0xFFFFFFF0), (0, 10), 4),
                                    ((0, 0), (1, 0), 4), ((0, 0), (1, 1), 4),
                                    ((0, 0), (0xFFFFFFFF, 0xFFFFFFFF), 0xFFFFFFFF)):
        add(request(started=start), inputs(frequency_word=frequency), tick=finish)
    add(request(), inputs(descriptor=b''), phase=3)
    return cases


class NintendoCallbackTests(unittest.TestCase):
    def test_complete_event_four_produces_fields_and_original_consumer_state(self):
        result = project()
        self.assertEqual([x.address for x in result.calls], [CONTEXT, TICK, ERROR, PHASE, RESPONSE])
        self.assertEqual(result.calls[0].arguments, (0x9999,))
        self.assertEqual(next(x.arguments for x in result.calls if x.address == ERROR), (0x1234,))
        self.assertEqual(result.request.shared_word, 3)
        self.assertEqual(word(result.request.storage, INNER + 0x100), 700)
        self.assertEqual(word(result.request.storage, INNER + 0x118), 0)
        self.assertEqual(word(result.request.storage, INNER + 0x11C), 0x55667788)
        self.assertEqual(word(result.request.storage, INNER + 0x120), 200)
        self.assertEqual(result.loader.word_08, 3)
        self.assertEqual(result.loader.word_0c, 7000)
        self.assertEqual(result.loader.copied_bytes, 9)
        self.assertEqual(result.loader.buffer, loader_state().buffer)
        self.assertEqual(result.request.retry_word, result.loader.retry_word)
        self.assertEqual(result.loader.retry_word, 0)
        self.assertTrue(result.response_getter_called)
        self.assertFalse(result.metadata()['actual_http_response_or_authentication_verified'])

    def test_low_or_negative_sdk_phase_retains_prior_response_without_observation(self):
        for phase in (0, 1, 2, 3, 0x80000000, 0xFFFFFFFF):
            result = project(phase=phase)
            self.assertFalse(result.response_getter_called)
            self.assertTrue(result.metadata()['prior_response_word_retained'])
            self.assertEqual(word(result.request.storage, INNER + 0x120), 200)
            self.assertEqual(result.delivery.frame.word_10, 0)
            self.assertFalse(result.metadata()['actual_http_response_or_authentication_verified'])
        preserved_error = project(request(response=503), phase=3)
        self.assertEqual(preserved_error.delivery.frame.word_10, -107 & 0xFFFFFFFF)
        self.assertFalse(preserved_error.response_getter_called)
        self.assertTrue(preserved_error.metadata()['wrapper_return_word_zero'])
        polled = poll_http_state(preserved_error.loader, **poll())
        self.assertEqual(polled.raw_poll_result, -109)
        self.assertEqual(polled.manager_result, -107)

    def test_conditional_detail_getter_and_error_retry_coupling(self):
        for error in (0, 8, 1, 15):
            result = project(error=error)
            self.assertFalse(result.detail_getter_called)
            self.assertEqual(word(result.request.storage, INNER + 0x11C), 0x55667788)
        for retry in (-1, 0, 1):
            result = project(request(retry=retry), error=14, detail=(-10 & 0xFFFFFFFF))
            self.assertTrue(result.detail_getter_called)
            self.assertEqual(result.loader.word_08, 7 if retry == -1 else 6)
            self.assertEqual(result.loader.retry_word, 1 if retry == -1 else retry)
            self.assertEqual(result.request.retry_word, result.loader.retry_word)

    def test_shared_phase_transition_and_two_bypass_only_after_actual_transition(self):
        for shared, after in ((0, 0), (1, 1), (2, 3), (3, 3), (4, 5), (5, 5), (0xFFFFFFFF, 0xFFFFFFFF)):
            before = request(shared=shared)
            result = project(before, error=1)
            self.assertEqual(result.request.shared_word, after)
            self.assertEqual(sum(x.address == TICK for x in result.calls), int(shared == 2))
            if shared != 2:
                self.assertEqual(word(result.request.storage, INNER + 0x100), 0xA1B2C3D4)
            self.assertEqual(result.loader.word_08, 6)

    def test_four_callback_absence_layers_preserve_loader_and_still_update_sdk_fields(self):
        for change, inner, relay, frame in (({'inner_callback': 0}, False, False, False),
                                            ({'inner_context': 0}, True, False, False),
                                            ({'outer_callback': 0}, True, True, False),
                                            ({'outer_context': 0}, True, True, True)):
            before = request(**change)
            loader = loader_state(copied_bytes=9, skipped_input=True)
            result = project(before, loader, error=1, response=503)
            self.assertEqual(result.loader, loader)
            self.assertEqual(result.inner_callback_invoked, inner)
            self.assertEqual(result.manager_relay_invoked, relay)
            self.assertEqual(result.delivery is not None and result.delivery.frame is not None, frame)
            self.assertEqual(word(result.request.storage, INNER + 0x118), 1)
            self.assertEqual(word(result.request.storage, INNER + 0x120), 503)

    def test_header_first_bytes_clear_but_handle_error_opaque_tail_and_descriptor_stay(self):
        before = request()
        result = project(before)
        for offset in (0x18, 0x58, 0x78, 0xB8):
            self.assertEqual(result.request.storage[INNER + offset], 0)
            self.assertEqual(result.request.storage[INNER + offset + 1:INNER + offset + 8],
                             before.storage[INNER + offset + 1:INNER + offset + 8])
        for offset in (0, 4, 8, 12):
            self.assertEqual(word(result.request.storage, INNER + offset), word(before.storage, INNER + offset))
        self.assertEqual(result.request.storage[0x100:0x200], before.storage[0x100:0x200])

    def test_elapsed_signed_division_wrap_and_low_word_behavior_matches_original_formula(self):
        for start, finish, frequency, expected in (((0, 0), (0, 0), 4, 0),
                                                  ((0, 0), (0, 1), 4, 7000),
                                                  ((0xFFFFFFFF, 0xFFFFFFF0), (0, 10), 4, 7000 // 26),
                                                  ((0, 0), (1, 0), 4, 0),
                                                  ((0, 0), (1, 1), 4, 7000),
                                                  ((0, 0), (0xFFFFFFFF, 0xFFFFFFFF), 0xFFFFFFFF, 0)):
            result = project(request(started=start), event=inputs(frequency_word=frequency), tick=finish)
            self.assertEqual(word(result.request.storage, INNER + 0x100), expected)

    def test_foreign_callbacks_contexts_and_disagreeing_retry_are_not_redirected(self):
        for change in ({'inner_callback': 0x12345678}, {'inner_context': 0x81222222},
                       {'outer_callback': 0x12345678}, {'outer_context': 0x81222222}):
            with self.assertRaises(NintendoLoadError):
                project(request(**change))
        with self.assertRaises(NintendoLoadError):
            project(loader=loader_state(retry_word=0))
        before = request()
        script, ticks = observations(before)
        with self.assertRaises(NintendoLoadError):
            apply_sdk_event4(before, loader_state(), inputs(), loader_context_word=LOADER_CONTEXT_WORD,
                              sdk_results=((CONTEXT, 0), *script[1:]), tick_words=ticks)

    def test_unsupported_event_bounds_and_missing_extra_or_reordered_observations_reject(self):
        before = request()
        script, ticks = observations(before)
        for event in (inputs(event_word=1), inputs(event_word=2), inputs(event_word=3),
                      inputs(frequency_word=3), inputs(descriptor=b'x' * 257), inputs(event_word=True)):
            with self.assertRaises(NintendoLoadError):
                apply_sdk_event4(before, loader_state(), event, loader_context_word=LOADER_CONTEXT_WORD,
                                  sdk_results=script, tick_words=ticks)
        for bad, bad_ticks in ((script[:-1], ticks), (script[1:], ticks),
                               (script + ((DETAIL, 0),), ticks), (script, ()),
                               (script * 2, ticks), (script, ticks * 2)):
            with self.assertRaises(NintendoLoadError):
                apply_sdk_event4(before, loader_state(), inputs(), loader_context_word=LOADER_CONTEXT_WORD,
                                  sdk_results=bad, tick_words=bad_ticks)

    def test_private_words_and_descriptor_are_not_in_repr_or_metadata(self):
        event = inputs(descriptor=b'private-marker')
        result = project(event=event)
        self.assertNotIn('private-marker', repr(event))
        self.assertNotIn('private-marker', repr(result))
        self.assertNotIn('private-marker', str(result.metadata()))
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_callback_native(b'wrong original', request(), loader_state(), event,
                                    sdk_results=(), tick_words=())


class NintendoCallbackNativeTests(unittest.TestCase):
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

    def test_complete_original_event_four_producer_relay_and_http_consumer(self):
        for index, (before, loader, event, script, ticks) in enumerate(native_cases()):
            with self.subTest(case=index):
                report = verify_callback_native(self.source, before, loader, event,
                                                sdk_results=script, tick_words=ticks)
                self.assertFalse(report['original_wrapper_event_four_division_header_clear_relay_and_consumer_stubbed'])
                self.assertTrue(report['host_inspection_reads_share_emulated_bounds'])
                self.assertTrue(report['exact_storage_descriptor_context_arguments_state_and_guards_checked'])
