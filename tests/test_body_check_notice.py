"""Synthetic state/headers; original message resource stays private and unchanged."""
import contextlib
from dataclasses import replace
import importlib.util
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import zlib

from jwc24.body_check import BodyCheckFormatError
from jwc24.body_check_notice import (BodyCheckNoticeError, BodyCheckNoticeUnsupported,
    inspect_dataset_notice, plan_header_notice)
from tools.verify_body_check_notice import (audit_message_membership, fixture_context,
    main, verify_message_binding, verify_notice_path)


def header(first, second, suffix=b''):
    data = bytearray(bytes(12) + struct.pack('>HH', first, second) + suffix)
    struct.pack_into('>I', data, 0, zlib.crc32(data[4:16]))
    return bytes(data)


def native_path_cases():
    cases = []
    for first, second in ((0, 0), (0, 1), (1, 0), (1, 1), (1, 65535), (2, 0), (65535, 0)):
        for busy in (False, True):
            for advance, later in ((False, None), (True, False), (True, True)):
                cases.append((first, second, fixture_context(transition_dialog_busy=busy,
                              advance_selector=advance, selector_dialog_busy=later)))
    return cases


class BodyCheckNoticeTests(unittest.TestCase):
    def test_notice_requires_explicit_later_phase_and_independent_ui_samples(self):
        queued = plan_header_notice(True, context=fixture_context(advance_selector=False, selector_dialog_busy=None))
        self.assertEqual((queued.next_state, queued.selector, queued.control), (0x33, 0x2D, 1))
        self.assertIsNone(queued.message_id)
        self.assertFalse(queued.selector_advanced)
        for transition_busy in (False, True):
            for later_busy in (False, True):
                result = plan_header_notice(True, context=fixture_context(
                    transition_dialog_busy=transition_busy, selector_dialog_busy=later_busy))
                self.assertEqual(result.dialog_close_requested, transition_busy)
                self.assertEqual(result.next_state, 0x33 if later_busy else 0x2D)
                self.assertEqual(result.message_id, None if later_busy else 0x754C)
                self.assertEqual(result.message_variant, None if later_busy else 0)
                self.assertFalse(result.metadata()['message_rendered'])
                self.assertFalse(result.metadata()['header_word_meanings_verified'])

    def test_false_pair_requests_the_separate_context_path_without_a_notice(self):
        result = plan_header_notice(False, context=fixture_context())
        self.assertEqual(result.next_state, 0x2B)
        self.assertTrue(result.secondary_context_call_requested)
        self.assertIsNone(result.message_id)
        self.assertFalse(result.selector_advanced)

    def test_blocked_context_does_not_read_or_claim_a_valid_header(self):
        for flags in (0x100, 0x200, 0x300, 0xFFFFFFFF):
            context = fixture_context(gate_context_word8=flags)
            result = inspect_dataset_notice(b'', context=context)
            self.assertIsNone(result.header)
            self.assertFalse(result.decision.header_gate_evaluated)
            self.assertIsNone(result.decision.next_state)
            self.assertFalse(result.metadata()['header_crc_checked'])
        for context in (fixture_context(manager_latched_flag=True),
                        fixture_context(secondary_context_word8=0x1000)):
            with self.assertRaises(BodyCheckNoticeUnsupported):
                inspect_dataset_notice(b'', context=context)

    def test_safe_crc_handoff_preserves_opaque_pair_and_trailing_bytes(self):
        for pair, message in (((0, 0), None), ((1, 0), None), ((1, 1), 0x754C), ((2, 0), 0x754C)):
            data = header(*pair, suffix=b'synthetic opaque payload')
            result = inspect_dataset_notice(data, context=fixture_context())
            self.assertEqual(result.decision.message_id, message)
            self.assertTrue(result.metadata()['header_crc_checked'])
            self.assertFalse(result.metadata()['payload_integrity_checked'])
            self.assertFalse(result.metadata()['record_semantics_checked'])
            self.assertFalse(result.metadata()['dataset_freshness_or_authentication_verified'])
            changed = bytearray(data); changed[-1] ^= 1
            self.assertEqual(result, inspect_dataset_notice(bytes(changed), context=fixture_context()))
        corrupted = bytearray(header(2, 0)); corrupted[5] ^= 1
        with self.assertRaises(BodyCheckFormatError):
            inspect_dataset_notice(bytes(corrupted), context=fixture_context())
        with self.assertRaises(BodyCheckFormatError):
            inspect_dataset_notice(bytes(15), context=fixture_context())

    def test_context_predicates_widths_and_phase_ambiguity_refuse_without_echo(self):
        c = fixture_context()
        for name, value in (('gate_context_word8', -1), ('secondary_context_word8', 1 << 32),
                            ('gate_context_word8', True), ('manager_latched_flag', 1),
                            ('transition_dialog_busy', 'private-marker'), ('advance_selector', 1),
                            ('selector_dialog_busy', None)):
            with self.subTest(field=name), self.assertRaises(BodyCheckNoticeError) as caught:
                plan_header_notice(True, context=replace(c, **{name: value}))
            self.assertNotIn('private-marker', str(caught.exception))
        for value in (0, 1, 'private-marker'):
            with self.assertRaises(BodyCheckNoticeError):
                plan_header_notice(value, context=c)
        with self.assertRaises(BodyCheckNoticeError):
            plan_header_notice(None, context=c)
        with self.assertRaises(BodyCheckNoticeError):
            plan_header_notice(True, context=replace(c, advance_selector=False))
        for data in (bytearray(header(2, 0)), bytes(32769), 'private-marker'):
            with self.assertRaises(BodyCheckNoticeError):
                inspect_dataset_notice(data, context=c)

    def test_wrong_original_resource_or_wad_refuses_before_optional_backends(self):
        for operation in (lambda: verify_notice_path(b'private-marker', 2, 0, context=fixture_context()),
                          lambda: verify_message_binding(b'private-marker', b'private-marker'),
                          lambda: audit_message_membership(b'private-marker', b'private-marker')):
            with self.assertRaisesRegex(ValueError, 'fingerprint') as caught:
                operation()
            self.assertNotIn('private-marker', str(caught.exception))

    def test_cli_missing_input_never_echoes_private_paths(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-marker')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(main(['private-marker', 'private-marker']), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('private-marker', errors.getvalue())


class BodyCheckNoticeNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/body_check/v256/0001-0000000e.dol')
        if not path.is_file():
            raise unittest.SkipTest('Pinned private HFNJ original unavailable')
        if any(importlib.util.find_spec(module) is None for module in ('unicorn', 'capstone')):
            raise unittest.SkipTest('Optional native reverse-engineering dependencies unavailable')
        cls.source = path.read_bytes()

    def test_complete_native_gate_transition_and_explicit_later_selector_phases(self):
        cases = native_path_cases()
        self.assertEqual(len(cases), 42)
        for first, second, context in cases:
            report = verify_notice_path(self.source, first, second, context=context)
            self.assertTrue(report['independent_handoff_supported'])
            self.assertTrue(report['immutable_input_state_stack_and_global_guards_verified'])
            self.assertFalse(report['original_header_transition_selector_branches_stubbed'])
            self.assertFalse(report['original_ui_rendered'])

    def test_actual_context_masks_and_explicitly_unimplemented_alternate_handler(self):
        contexts = [fixture_context(gate_context_word8=flags)
                    for flags in (0x100, 0x200, 0x300, 0xFFFFFFFF)]
        contexts += [fixture_context(secondary_context_word8=flags) for flags in (0x10, 0x1010)]
        contexts += [fixture_context(manager_latched_flag=True),
                     fixture_context(secondary_context_word8=0x1000)]
        for context in contexts:
            report = verify_notice_path(self.source, 2, 0, context=context)
            self.assertTrue(report['immutable_input_state_stack_and_global_guards_verified'])
            self.assertFalse(report['alternate_error_handler_executed'])

    def test_original_bmg_constructor_and_getter_select_exact_private_record(self):
        path = Path('private/body_check/v256/health_message.bmg')
        if not path.is_file():
            self.skipTest('Pinned private message resource unavailable')
        report = verify_message_binding(self.source, path.read_bytes())
        self.assertEqual((report['message_id'], report['variant'], report['selected_mid']),
                         (0x754C, 0, 0x754C00))
        self.assertTrue(report['original_bmg_constructor_and_getter_executed'])
        self.assertTrue(report['resource_and_guards_unchanged'])
        self.assertFalse(report['lookup_or_service_boundaries_stubbed'])
        self.assertFalse(report['message_text_published'])


class BodyCheckNoticeMembershipTests(unittest.TestCase):
    def test_retained_message_is_exact_member_of_pinned_wad_content(self):
        wad = Path('Stock WADs/Wii Fit Body Check Channel (Japan) (Channel).wad')
        bmg = Path('private/body_check/v256/health_message.bmg')
        if not wad.is_file() or not bmg.is_file():
            self.skipTest('Pinned private title/resource inputs unavailable')
        if importlib.util.find_spec('libWiiPy') is None:
            self.skipTest('Optional local WAD audit dependency unavailable')
        report = audit_message_membership(wad.read_bytes(), bmg.read_bytes())
        self.assertTrue(report['content_matches_tmd_hash_and_size'])
        self.assertTrue(report['exact_resource_membership_verified'])
        self.assertFalse(report['nintendo_signature_or_independent_archive_provenance_verified'])
        self.assertFalse(report['original_bytes_keys_or_message_text_published'])
