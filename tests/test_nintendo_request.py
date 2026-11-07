"""Synthetic HATJ request setup; no actual device UA, endpoint or provider data."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from jwc24.nintendo_load import NintendoLoadError
from jwc24.nintendo_request import (STORAGE_BYTES, INNER, CREATE, DESTROY, HEADER,
                                    CONFIGURE, SELECT, OPTION, SEND, LAST_ERROR, TICK,
                                    NintendoRequestState, NintendoRequestInputs,
                                    prepare_request, submit_request)
from tools.verify_nintendo_request import OBJECT_WORD, verify_request_native


def word(data, offset):
    return struct.unpack_from('>I', data, offset)[0]


def state(*, phase=1, retry=-1, old_handle=0, opaque_detail=0x99112233):
    raw = bytearray((index * 37 + 11) % 256 for index in range(STORAGE_BYTES))
    for offset, value in ((0, 0x88776655), (INNER, old_handle), (INNER + 0x124, opaque_detail)):
        struct.pack_into('>I', raw, offset, value)
    return NintendoRequestState(OBJECT_WORD, bytes(raw), phase, retry)


def inputs(**changes):
    values = dict(reference=b'https://synthetic.invalid/catalog', receive_word=0x81200000,
                  capacity_word=4096, callback_word=0x800287C0, callback_context_word=0x81010010,
                  user_agent=b'Synthetic test UA', referer=None, range_word=0)
    values.update(changes)
    return NintendoRequestInputs(**values)


def outcomes(before, request, *, old_destroy=0, created=0x1234, last_error=1,
             configuration=(0, 0, 0), failed_header=None, header_result=0xFFFFFFFF,
             send_result=0, final_destroy=0):
    """Explicit synthetic SDK fixture; these outcomes are not production defaults."""
    script = []
    ticks = ()
    if before.shared_word not in (1, 3, 5) or request.capacity_word == 0:
        return (), ticks
    if word(before.storage, INNER):
        script.append((DESTROY, old_destroy))
        if old_destroy:
            return tuple(script), ticks
    script.append((CREATE, created))
    if created == 0:
        return tuple(script + [(LAST_ERROR, last_error)]), ticks
    script.extend(zip((CONFIGURE, SELECT, OPTION), configuration))
    for name, present in ((b'User-Agent', True), (b'Referer', request.referer is not None),
                          (b'Range', request.range_word != 0)):
        if present:
            script.append((HEADER, header_result if failed_header == name else 0))
            if failed_header == name:
                return tuple(script + [(DESTROY, final_destroy)]), ticks
    script.append((SEND, send_result))
    if send_result:
        script.append((DESTROY, final_destroy))
    else:
        ticks = ((0x12345678, 0x9ABCDEF0),)
    return tuple(script), ticks


def project(before=None, request=None, **fixture):
    before = state() if before is None else before
    request = inputs() if request is None else request
    script, ticks = outcomes(before, request, **fixture)
    return prepare_request(before, request, sdk_results=script, tick_words=ticks)


def native_cases():
    cases = []
    def add(before, request, **fixture):
        script, ticks = outcomes(before, request, **fixture)
        cases.append((before, request, script, ticks, 'prepare'))
    for phase in (0, 1, 2, 3, 4, 5, 6, 7, 0xFFFFFFFF):
        for old_handle in (0, 0x5678):
            add(state(phase=phase, old_handle=old_handle), inputs(referer=b'', range_word=1))
    for retry in (-1, 0, 1):
        for ua in (b'', b'A' * 23, b'A' * 24, b'A' * 25, b'A' * 80):
            for ref in (None, b'', b'R' * 63, b'R' * 64):
                add(state(retry=retry), inputs(user_agent=ua, referer=ref, range_word=0xFFFFFFFF))
    for error in (-1, *range(17), 0x7FFFFFFF, 0x80000000):
        add(state(), inputs(), created=0, last_error=error & 0xFFFFFFFF)
    for destroyed in (1, 3, 0xFFFFFFFF):
        add(state(old_handle=0x5678), inputs(), old_destroy=destroyed)
    for header in (b'User-Agent', b'Referer', b'Range'):
        for destroyed in (0, 3, 0xFFFFFFFF):
            add(state(old_handle=0x5678), inputs(referer=b'synthetic ref', range_word=1),
                failed_header=header, final_destroy=destroyed)
    for sent in (1, 8, 14, 15, 0xFFFFFFFF):
        for destroyed in (0, 2, 0xFFFFFFFF):
            add(state(), inputs(), send_result=sent, final_destroy=destroyed)
    for capacity in (0, 1, 0x1FC7CC):
        add(state(), inputs(capacity_word=capacity, callback_word=0, callback_context_word=0))
    add(state(), inputs(), configuration=(0xFFFFFFFF, 3, 1))
    for phase in (0, 1, 2, 3, 4, 5, 6, 0xFFFFFFFF):
        for handle in (0, 0x5678):
            before = state(phase=phase, old_handle=handle)
            for sent in (0, 1, 14, 0xFFFFFFFF):
                script, ticks = (), ()
                if phase in (1, 3, 5):
                    script = ((SEND, sent),) + (((DESTROY, 3),) if sent and handle else ())
                    ticks = ((0, 0xFFFFFFFF),) if sent == 0 else ()
                cases.append((before, None, script, ticks, 'submit'))
    return cases


class NintendoRequestTests(unittest.TestCase):
    def test_full_setup_keeps_header_order_and_explicit_native_pointer_words(self):
        request = inputs(referer=b'https://synthetic.invalid/source', range_word=5)
        result = project(request=request)
        self.assertEqual(result.result, 0)
        self.assertEqual([x.address for x in result.calls],
                         [CREATE, CONFIGURE, SELECT, OPTION, HEADER, HEADER, HEADER, SEND, TICK])
        self.assertEqual(result.calls[0].arguments, (request.reference, 0, request.receive_word,
                         request.capacity_word, 0x80027E40, OBJECT_WORD + INNER))
        self.assertEqual([x.arguments[1:] for x in result.calls if x.address == HEADER],
                         [(b'User-Agent', request.user_agent), (b'Referer', request.referer), (b'Range', b'bytes=5-')])
        raw = result.state.storage
        self.assertEqual(word(raw, 0x29AC), request.callback_word)
        self.assertEqual(word(raw, 0x29B0), request.callback_context_word)
        self.assertEqual(word(raw, INNER + 8), 0x80026AE0)
        self.assertEqual(word(raw, INNER + 12), OBJECT_WORD)
        self.assertEqual(result.state.shared_word, 2)
        self.assertEqual(word(raw, INNER + 0xF8), 0x12345678)
        self.assertEqual(word(raw, INNER + 0x10C), 0x9ABCDEF0)

    def test_user_agent_and_referer_truncation_preserve_opaque_storage_tail(self):
        before = state()
        result = project(before, inputs(user_agent=b'U' * 40, referer=b'R' * 80))
        headers = [x.arguments for x in result.calls if x.address == HEADER]
        self.assertEqual(headers[0][2], b'U' * 24)
        self.assertEqual(headers[1][2], b'R' * 63)
        raw = result.state.storage
        self.assertEqual(raw[INNER + 0x78:INNER + 0x91], b'U' * 24 + b'\0')
        self.assertEqual(raw[INNER + 0x91:INNER + 0xB8], before.storage[INNER + 0x91:INNER + 0xB8])
        self.assertEqual(raw[0x100:0x200], before.storage[0x100:0x200])

    def test_absent_referer_and_range_zero_differ_from_explicit_empty_referer(self):
        absent = project()
        empty = project(request=inputs(referer=b''))
        self.assertEqual(sum(x.address == HEADER for x in absent.calls), 1)
        self.assertEqual([x.arguments[1:] for x in empty.calls if x.address == HEADER],
                         [(b'User-Agent', b'Synthetic test UA'), (b'Referer', b'')])
        maximum = project(request=inputs(range_word=0xFFFFFFFF))
        self.assertEqual(next(x.arguments[2] for x in maximum.calls
                             if x.address == HEADER and x.arguments[1] == b'Range'), b'bytes=4294967295-')

    def test_invalid_phase_and_zero_capacity_store_callback_before_failure(self):
        for before, request in ((state(phase=2, old_handle=0x5678), inputs()),
                                (state(old_handle=0x5678), inputs(capacity_word=0))):
            result = project(before, request)
            self.assertEqual(result.calls, ())
            self.assertEqual(result.result, -109)
            self.assertEqual(word(result.state.storage, 0), 0x99112233)
            self.assertEqual(word(result.state.storage, INNER), 0x5678)
            self.assertEqual(word(result.state.storage, 0x29AC), request.callback_word)

    def test_initial_release_failure_resets_then_stores_destroy_result(self):
        result = project(state(old_handle=0x5678), old_destroy=0xFFFFFFFF)
        self.assertEqual([x.address for x in result.calls], [DESTROY])
        self.assertEqual(result.result, -109)
        for offset in (0, 8, 12, 0x10, 0x14, 0x118, 0x120):
            self.assertEqual(word(result.state.storage, INNER + offset), 0)
        self.assertEqual(word(result.state.storage, INNER + 4), 0xFFFFFFFF)
        self.assertEqual(word(result.state.storage, 0), 0x99112233)

    def test_header_failure_keeps_preexisting_detail_and_callback_context(self):
        for name in (b'User-Agent', b'Referer', b'Range'):
            result = project(request=inputs(referer=b'synthetic', range_word=1),
                             failed_header=name, final_destroy=0xFFFFFFFF)
            self.assertEqual(result.result, -109)
            self.assertEqual(word(result.state.storage, INNER), 0)
            self.assertEqual(word(result.state.storage, INNER + 8), 0x80026AE0)
            self.assertEqual(word(result.state.storage, INNER + 12), OBJECT_WORD)
            self.assertEqual(word(result.state.storage, 0), 0x99112233)
            self.assertEqual(word(result.state.storage, INNER + 0x124), 0x99112233)
            self.assertFalse(any(x.address == SEND for x in result.calls))
            for offset in (0x18, 0x58, 0x78, 0xB8):
                self.assertEqual(result.state.storage[INNER + offset], 0)

    def test_send_failure_maps_send_value_and_overwrites_destroy_error_after_cleanup(self):
        result = project(send_result=8, final_destroy=3)
        self.assertEqual(result.result, -109)
        self.assertEqual(word(result.state.storage, INNER + 4), 8)
        self.assertEqual(word(result.state.storage, INNER + 0x124), 260800)
        self.assertEqual(word(result.state.storage, 0), 260800)
        self.assertEqual(word(result.state.storage, INNER + 8), 0)
        # An actual mapping hole can leave outer detail zero while setup fails.
        hole = project(send_result=14)
        self.assertEqual(hole.result, -109)
        self.assertEqual(word(hole.state.storage, 0), 0)

    def test_create_failure_uses_separately_supplied_last_error(self):
        result = project(created=0, last_error=0xFFFFFFFF)
        self.assertEqual([x.address for x in result.calls], [CREATE, LAST_ERROR])
        self.assertEqual(word(result.state.storage, INNER + 0x124), 260001)
        self.assertEqual(word(result.state.storage, 0), 260001)
        self.assertEqual(result.result, -109)

    def test_opaque_configuration_return_words_are_ignored_not_reported_as_auth(self):
        for retry, selector in ((-1, 0), (0, 0), (1, 1)):
            result = project(state(retry=retry), configuration=(0xFFFFFFFF, 3, 7))
            self.assertEqual(next(x.arguments for x in result.calls if x.address == SELECT), (0x1234, selector))
            self.assertEqual(result.result, 0)
            self.assertFalse(result.metadata()['network_authentication_or_catalog_completion_verified'])

    def test_direct_submit_preserves_stage_result_and_does_not_copy_outer_error(self):
        before = state(phase=2)
        result = submit_request(before, sdk_results=(), tick_words=())
        self.assertEqual(result.result, 7)
        self.assertEqual(result.state, before)
        before = state(old_handle=0x5678)
        failed = submit_request(before, sdk_results=((SEND, 1), (DESTROY, 0xFFFFFFFF)), tick_words=())
        self.assertEqual(failed.result, 3)
        self.assertEqual(word(failed.state.storage, 0), word(before.storage, 0))
        self.assertEqual(word(failed.state.storage, INNER + 4), 1)

    def test_missing_extra_or_wrong_order_sdk_and_tick_outcomes_reject(self):
        before, request = state(), inputs()
        script, ticks = outcomes(before, request)
        for wrong, wrong_ticks in ((script[:-1], ticks), (script + ((SEND, 0),), ticks),
                                   (script[1:], ticks), (script, ()), (script, ticks + ticks)):
            with self.assertRaises(NintendoLoadError):
                prepare_request(before, request, sdk_results=wrong, tick_words=wrong_ticks)
        with self.assertRaises(NintendoLoadError):
            prepare_request(before, request, sdk_results=[(CREATE, 0)], tick_words=())
        with self.assertRaises(NintendoLoadError):
            prepare_request(before, request, sdk_results=((CREATE, 0),) * 17, tick_words=())
        with self.assertRaises(NintendoLoadError):
            prepare_request(before, request, sdk_results=(), tick_words=((0, 0),) * 2)

    def test_bounds_explicit_strings_and_repr_privacy(self):
        for bad in (replace(state(), object_word=0), replace(state(), storage=b''),
                    replace(state(), retry_word=2), replace(state(), shared_word=True)):
            with self.assertRaises(NintendoLoadError):
                prepare_request(bad, inputs(), sdk_results=(), tick_words=())
        for bad in (inputs(reference=b''), inputs(reference=b'x' * 512),
                    inputs(user_agent=b'a\0b'), inputs(referer=bytearray()),
                    inputs(capacity_word=0xFFFFFFFF), inputs(range_word=True)):
            with self.assertRaises(NintendoLoadError):
                prepare_request(state(), bad, sdk_results=(), tick_words=())
        request = inputs(reference=b'https://private-marker.invalid/', user_agent=b'private-marker')
        result = project(request=request)
        self.assertNotIn('private-marker', repr(request))
        self.assertNotIn('private-marker', repr(result))
        self.assertNotIn('private-marker', repr(result.calls))
        self.assertNotIn('private-marker', str(result.metadata()))
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_request_native(b'wrong original', state(), inputs=request,
                                  sdk_results=(), tick_words=(), entry='prepare')


class NintendoRequestNativeTests(unittest.TestCase):
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

    def test_original_setup_create_header_cleanup_and_submission_branches(self):
        for index, (before, request, script, ticks, entry) in enumerate(native_cases()):
            with self.subTest(case=index):
                report = verify_request_native(self.source, before, inputs=request, sdk_results=script,
                                                tick_words=ticks, entry=entry)
                self.assertFalse(report['original_setup_create_cleanup_headers_submission_and_error_conversion_stubbed'])
                self.assertFalse(report['device_configuration_generator_executed'])
                self.assertFalse(report['referenced_sdk_resources_read'])
                self.assertTrue(report['exact_storage_arguments_outcome_sequence_and_guards_checked'])
