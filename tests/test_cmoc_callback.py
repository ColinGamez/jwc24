"""Callback lifecycle: native flags, explicit transforms, no fabricated data."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from jwc24.cmoc_callback import CallbackState, process_body_event, finish_callback


def state(**changes):
    values = dict(response_flags=0, expected_wire_prefix=b'WIRE',
                  expected_cached_prefix=b'FD!!', decoded_body=b'',
                  hash_span_size=4, hash_enabled=True)
    values.update(changes)
    return CallbackState(**values)


def body_event(current, body=b'FD!!', *, wire=None):
    if wire is None:
        wire = current.expected_wire_prefix + bytes(128 - len(current.expected_wire_prefix))
    return dict(kind='body', wire_storage=wire,
                receive_end_offset=len(body) if current.response_flags & 0x80
                else current.hash_span_size + len(current.expected_wire_prefix) + 16,
                decoded_chunk=None if current.response_flags & 0x80 else body,
                raw_body=body if current.response_flags & 0x80 else None)


def finish_event(current, match=True):
    return dict(kind='finish', digest_matches=match if current.hash_enabled
                and not current.response_flags & 0x80 else None)


def native_cases():
    cases = []
    for flags in range(256):
        for body, match in ((b'FD!!-body', True), (b'other-body', False), (b'FD', False)):
            current = state(response_flags=flags)
            cases.append((current, (body_event(current, body), finish_event(current, match))))
    for raw in (False, True):
        for length in (0, 1, 12, 64):
            prefix = bytes(range(length))
            current = state(response_flags=0x80 if raw else 0, expected_wire_prefix=prefix,
                            expected_cached_prefix=prefix, hash_span_size=0)
            for body_length in sorted({max(0, length - 1), length, length + 1}):
                body = prefix[:body_length] + b'x' * max(0, body_length - length)
                cases.append((current, (body_event(current, body), finish_event(current))))
            for position in sorted({0, length // 2, length - 1}) if length else ():
                bad = bytearray(prefix)
                bad[position] ^= 0xFF
                cases.append((current, (body_event(current, bytes(bad), wire=bytes(bad) + bytes(128 - length)),
                                        finish_event(current))))
        current = state(response_flags=0x80 if raw else 0, expected_cached_prefix=b'FD!!-prefix')
        first = body_event(current, b'FD')
        next_current = process_body_event(current, **{k: v for k, v in first.items() if k != 'kind'}).state
        second_body = b'FD!!-prefix' if raw else b'!!-prefix'
        cases.append((current, (first, body_event(next_current, second_body), finish_event(next_current))))
        current = state(response_flags=0x80 if raw else 0)
        first = body_event(current)
        next_current = process_body_event(current, **{k: v for k, v in first.items() if k != 'kind'}).state
        cases.append((current, (first, body_event(next_current, b'other', wire=b'bad!' + bytes(124)),
                                finish_event(next_current))))
    for flags in (0, 4, 8, 12, 0x80, 0x84, 0x88, 0x8C):
        for enabled in (False, True):
            for match in (False, True):
                current = state(response_flags=flags, hash_enabled=enabled)
                cases.append((current, (finish_event(current, match),)))
    return cases


class CallbackTests(unittest.TestCase):
    def test_prefix_matching_mismatch_and_finalization_are_distinct(self):
        current = state()
        event = body_event(current)
        step = process_body_event(current, **{k: v for k, v in event.items() if k != 'kind'})
        self.assertEqual(step.state.response_flags, 0x0C)
        self.assertTrue(step.wire_prefix_compared)
        self.assertTrue(step.cached_prefix_compared)
        self.assertEqual(finish_callback(step.state, digest_matches=True).state.response_flags, 0x0E)
        bad = body_event(current, b'other', wire=b'bad!' + bytes(124))
        step = process_body_event(current, **{k: v for k, v in bad.items() if k != 'kind'})
        self.assertEqual(step.state.response_flags, 0x6C)
        self.assertEqual(finish_callback(step.state, digest_matches=False).state.response_flags, 0x7E)

    def test_short_body_finish_forces_twenty_without_a_completed_comparison(self):
        current = state()
        event = body_event(current, b'FD')
        step = process_body_event(current, **{k: v for k, v in event.items() if k != 'kind'})
        self.assertEqual(step.state.response_flags, 0x08)
        self.assertFalse(step.cached_prefix_compared)
        final = finish_callback(step.state, digest_matches=True)
        self.assertEqual(final.state.response_flags, 0x2E)
        self.assertTrue(final.forced_cached_comparison_at_finish)
        self.assertFalse(final.cached_prefix_compared)

    def test_raw_branch_total_size_replaces_body_and_skips_digest(self):
        current = state(response_flags=0x80, decoded_body=b'old')
        event = body_event(current, b'FD!!-new')
        step = process_body_event(current, **{k: v for k, v in event.items() if k != 'kind'})
        self.assertEqual(step.state.decoded_body, b'FD!!-new')
        self.assertEqual(step.padded_transform_size, 0)
        final = finish_callback(step.state, digest_matches=None)
        self.assertFalse(final.digest_boundary_consulted)
        with self.assertRaises(ValueError):
            finish_callback(step.state, digest_matches=True)

    def test_latched_prefix_checks_do_not_repeat_on_later_changed_bytes(self):
        current = state(response_flags=0x8C)
        event = body_event(current, b'other', wire=b'bad!' + bytes(124))
        step = process_body_event(current, **{k: v for k, v in event.items() if k != 'kind'})
        self.assertEqual(step.state.response_flags, 0x8C)
        self.assertFalse(step.wire_prefix_compared)
        self.assertFalse(step.cached_prefix_compared)

    def test_explicit_padded_backing_and_whole_buffer_bounds(self):
        current = state()
        base = dict(wire_storage=bytes(24), receive_end_offset=24, decoded_chunk=b'', raw_body=None)
        self.assertEqual(process_body_event(current, **base).padded_transform_size, 16)
        for changes in (dict(wire_storage=bytes(23)), dict(receive_end_offset=25),
                        dict(receive_end_offset=7), dict(decoded_chunk=b'x' * 1025),
                        dict(raw_body=b''), dict(wire_storage=bytes(0x441))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                process_body_event(current, **{**base, **changes})
        with self.assertRaises(ValueError):
            process_body_event(replace(current, decoded_body=bytes(4096)),
                               **{**base, 'decoded_chunk': b'x'})

    def test_empty_prefix_marks_checked_without_comparison_and_no_auth_claim(self):
        current = state(expected_wire_prefix=b'', expected_cached_prefix=b'', hash_span_size=0)
        step = process_body_event(current, wire_storage=b'', receive_end_offset=0,
                                  decoded_chunk=b'', raw_body=None)
        self.assertEqual(step.state.response_flags, 12)
        self.assertFalse(step.wire_prefix_compared)
        self.assertFalse(step.cached_prefix_compared)
        self.assertFalse(step.metadata()['service_authentication_verified'])

    def test_private_spans_hidden_and_invalid_input_does_not_echo(self):
        current = state(expected_wire_prefix=b'private-marker', expected_cached_prefix=b'private-marker',
                        decoded_body=b'private-marker')
        self.assertNotIn('private-marker', repr(current))
        final = finish_callback(current, digest_matches=False)
        self.assertNotIn('private-marker', repr(final))
        self.assertNotIn('private-marker', str(final.metadata()))
        for changes in (dict(response_flags=True), dict(response_flags=256),
                        dict(hash_span_size=-1), dict(hash_enabled=1),
                        dict(expected_wire_prefix=b'x' * 65), dict(decoded_body='private-marker')):
            with self.subTest(changes=changes), self.assertRaises(ValueError) as caught:
                state(**changes)
            self.assertNotIn('private-marker', str(caught.exception))

    def test_flags_compose_with_existing_header_gate_without_claiming_startup(self):
        from jwc24.cmoc_response_gate import evaluate_response_gate
        request = struct.pack('>HBBII', 0x4644, 1, 2, 3, 4) + bytes(20)
        changed = struct.pack('>HBBII', 0x4644, 2, 2, 3, 4) + bytes(20)
        for data, checked in ((request, False), (changed, True), (changed[:5], True)):
            current = state(response_flags=0x80, expected_wire_prefix=b'',
                            expected_cached_prefix=request[:12], hash_span_size=0, hash_enabled=False)
            step = process_body_event(current, wire_storage=b'', receive_end_offset=len(data),
                                      decoded_chunk=None, raw_body=data)
            final = finish_callback(step.state, digest_matches=None)
            gate = evaluate_response_gate(final.state.decoded_body, expected_request=request,
                                          http_status=200, x_result=0,
                                          response_flags=final.state.response_flags,
                                          limit_byte_2=2, learned_byte_3=2)
            self.assertEqual(bool(final.state.response_flags & 0x20), checked)
            self.assertEqual(gate.header_gate_passed, checked and len(data) >= 32)
            if len(data) < 32:
                self.assertEqual(gate.completion_code, 0x3D98D)
            elif not checked:
                self.assertEqual(gate.completion_code, 0)
                self.assertFalse(gate.body_header_checked)


class CallbackNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/cmoc/v512/0001-0000000c.app')
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese CMOC v512 executable unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_full_dispatcher_body_and_finalizer_matrix(self):
        from tools.verify_cmoc_callback import verify_callback_lifecycle
        for index, (current, events) in enumerate(native_cases()):
            with self.subTest(case=index):
                report = verify_callback_lifecycle(self.source, initial_state=current,
                                                   initial_wire_storage=bytes(128), events=events)
                self.assertTrue(report['input_backing_and_stack_guards_verified'])
                self.assertFalse(report['native_prefix_comparison_stubbed'])
                self.assertFalse(report['cryptography_or_authentication_verified'])
                self.assertEqual(report['counts']['dispatches'], len(events))
                self.assertEqual(report['counts']['native_prefix_comparisons'],
                                 sum(e['wire_prefix_compared'] + e['cached_prefix_compared'] for e in report['events']))

    def test_final_digest_requires_explicit_backing_even_when_result_is_supplied(self):
        from tools.verify_cmoc_callback import verify_callback_lifecycle
        with self.assertRaises(ValueError):
            verify_callback_lifecycle(self.source, initial_state=state(), initial_wire_storage=b'',
                                      events=(dict(kind='finish', digest_matches=True),))


if __name__ == '__main__':
    unittest.main()
