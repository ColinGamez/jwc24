"""Synthetic HFNJ task images and bounded original SDK caller comparisons."""
from dataclasses import replace
import contextlib
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from jwc24.body_check_tasks import BodyCheckTaskError, prepare_dataset_task
from tools.verify_body_check_tasks import fixture_configuration, main, verify_original_descriptor, verify_task_preparation


def existing_image(configuration):
    image = bytearray(prepare_dataset_task(configuration, existing_task=None).data)
    struct.pack_into('>H', image, 0, 5)  # Synthetic assigned SDK ID, never an IOS table slot.
    image[0x50:0x60] = b'unknown-preserve'
    return bytes(image)


def boundary_configurations():
    return [fixture_configuration(filename='x'),
            fixture_configuration(url='http://' + 'x' * 228, filename='f' * 63),
            fixture_configuration(flags_byte=0x80, priority=1, interval_minutes=360, server_interval_minutes=30),
            fixture_configuration(flags_byte=255, interval_minutes=10080, server_interval_minutes=20160),
            fixture_configuration(url='https://synthetic.invalid/', flags_word=4),
            fixture_configuration(url='https://synthetic.invalid/', flags_word=0xFFFFFFFF,
                                  opaque_word_1f8=0xFFFFFFFF)]


class BodyCheckTaskImageTests(unittest.TestCase):
    def test_explicit_new_local_image_has_no_assigned_task_or_registration_claim(self):
        c = fixture_configuration()
        result = prepare_dataset_task(c, existing_task=None)
        self.assertEqual(len(result.data), 512)
        self.assertEqual(struct.unpack_from('>HBB', result.data), (0xFFFF, 3, 0xC0))
        self.assertEqual(struct.unpack_from('>IIQH', result.data, 4),
                         (0xA, c.app_id, c.title_id, c.title_version))
        self.assertEqual(struct.unpack_from('>H', result.data, 0x18)[0], 100)
        self.assertEqual(struct.unpack_from('>HH', result.data, 0x1C), (1440, 1440))
        self.assertEqual(struct.unpack_from('>I', result.data, 0x1F8)[0], 0)
        self.assertEqual(result.data[0xB4:0xB4 + len(c.url) + 1], c.url.encode() + b'\0')
        self.assertEqual(result.data[0x1A0:0x1A0 + len(c.filename) + 1], c.filename.encode() + b'\0')
        for claim in ('sdk_context_or_task_database_verified', 'key_material_written', 'task_registered',
                      'scheduler_or_download_verified', 'signature_trust_or_native_ui_verified', 'profile_modified'):
            self.assertFalse(result.metadata()[claim])

    def test_existing_identity_id_and_unknown_bytes_survive_exact_field_changes(self):
        c = fixture_configuration()
        original = existing_image(c)
        changed = replace(c, filename='x', url='https://synthetic.invalid/', flags_word=4,
                          interval_minutes=720, priority=25, opaque_word_1f8=123)
        result = prepare_dataset_task(changed, existing_task=original)
        self.assertEqual(result.data[:3], original[:3])
        self.assertEqual(result.data[8:0x16], original[8:0x16])
        self.assertEqual(result.data[0x50:0x60], b'unknown-preserve')
        self.assertEqual(result.data[0x1A0:0x1A0 + len(c.filename) + 1], b'x\0' + original[0x1A2:0x1A0 + len(c.filename) + 1])
        self.assertEqual(original, existing_image(c))

    def test_short_filename_preserves_original_initializer_tail(self):
        image = prepare_dataset_task(fixture_configuration(filename='x'), existing_task=None).data
        self.assertEqual(image[0x1A0:0x1AC], b'x\0ntent.bin\0')

    def test_copy_capacity_policy_rejects_rewriting_or_unreviewed_strings(self):
        c = fixture_configuration(url='http://' + 'x' * 228, filename='f' * 63)
        self.assertEqual(len(prepare_dataset_task(c, existing_task=None).data), 512)
        for name, value in (('url', c.url + 'x'), ('filename', c.filename + 'f'),
                            ('url', 'ftp://private-marker/'), ('url', 'http://private\r\nmarker/'),
                            ('filename', '\u65e5\u672c\u8a9e'), ('filename', '')):
            with self.subTest(field=name), self.assertRaises(BodyCheckTaskError) as caught:
                prepare_dataset_task(replace(c, **{name: value}), existing_task=None)
            self.assertNotIn('private-marker', str(caught.exception))

    def test_scalar_boolean_and_existing_image_policies_are_explicit(self):
        c = fixture_configuration()
        for name, value in (('app_id', 0), ('title_id', 0), ('title_id', 1 << 32),
                            ('title_version', 65536), ('flags_byte', 127), ('flags_word', -1),
                            ('flags_word', True), ('interval_minutes', 359), ('interval_minutes', 10081),
                            ('server_interval_minutes', 29), ('priority', 0), ('priority', 101),
                            ('signing_key_present', 1), ('encryption_key_present', 'private-marker'),
                            ('evidence_ref', ''), ('evidence_ref', 'private\nmarker')):
            with self.subTest(field=name), self.assertRaises(BodyCheckTaskError):
                prepare_dataset_task(replace(c, **{name: value}), existing_task=None)
        with self.assertRaises(BodyCheckTaskError):
            prepare_dataset_task(replace(c, flags_word=4), existing_task=None)
        for image in (bytes(511), bytes(513), bytearray(existing_image(c))):
            with self.assertRaises(BodyCheckTaskError):
                prepare_dataset_task(c, existing_task=image)
        for offset in (2, 8, 12, 20):
            image = bytearray(existing_image(c)); image[offset] ^= 1
            with self.assertRaises(BodyCheckTaskError):
                prepare_dataset_task(c, existing_task=bytes(image))

    def test_key_presence_is_only_an_observed_request_predicate_and_values_are_private(self):
        for signing in (False, True):
            for encryption in (False, True):
                c = fixture_configuration(url='http://private-marker.invalid/', filename='private-marker',
                                          evidence_ref='private-marker', signing_key_present=signing,
                                          encryption_key_present=encryption)
                image = prepare_dataset_task(c, existing_task=None)
                self.assertEqual(image.key_import_requested, signing and encryption)
                self.assertNotIn('private-marker', repr(c))
                self.assertNotIn('private-marker', repr(image))
                self.assertNotIn('private-marker', str(image.metadata()))

    def test_wrong_original_and_ambiguous_outcomes_refuse_without_native_execution(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_task_preparation(b'private-marker', fixture_configuration(), existing_task=None)
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_original_descriptor(b'private-marker')

    def test_cli_error_excludes_private_input_paths(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-marker')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(main(['private-marker']), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('private-marker', errors.getvalue())


class BodyCheckTaskNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/body_check/v256/0001-0000000e.dol')
        if not path.is_file():
            raise unittest.SkipTest('Pinned private HFNJ v256 original unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_complete_original_descriptor_resources_allocation_and_failure(self):
        for result in (True, False):
            report = verify_original_descriptor(self.source, allocation_succeeds=result)
            self.assertTrue(report['original_resource_allocation_descriptor_caller_executed'])
            self.assertEqual(report['resource_lookup_calls'], 2)
            self.assertFalse(report['original_key_bodies_read'])
            self.assertFalse(report['task_registered'])

    def test_full_missing_and_existing_callers_execute_actual_local_sdk_for_each_key_predicate(self):
        for existing in (False, True):
            for signing in (False, True):
                for encryption in (False, True):
                    c = fixture_configuration(signing_key_present=signing, encryption_key_present=encryption)
                    report = verify_task_preparation(self.source, c,
                        existing_task=existing_image(c) if existing else None)
                    self.assertEqual(report['native_return'], 0)
                    self.assertTrue(report['local_task_image_matches'])
                    self.assertEqual(report['initializer_kinds'], [] if existing else [3])
                    self.assertEqual(report['key_import_calls'], int(signing and encryption))
                    self.assertEqual(report['events'][-1], 'update' if existing else 'add')
                    self.assertEqual(report['vff_create_sizes'], [32768])
                    self.assertEqual(len(report['original_local_setter_entries']), 8)
                    self.assertTrue(report['immutable_inputs_and_object_stack_global_guards_verified'])
                    self.assertFalse(report['task_registration_or_persistence_verified'])

    def test_actual_sdk_boundary_values_and_existing_unknown_tail_preservation(self):
        for c in boundary_configurations():
            for existing in (False, True):
                report = verify_task_preparation(self.source, c,
                    existing_task=existing_image(fixture_configuration()) if existing else None)
                self.assertEqual(report['native_return'], 0)
                self.assertTrue(report['local_task_image_matches'])
        report = verify_task_preparation(self.source, fixture_configuration(), existing_task=None,
                                         outcomes={'find_vff': 0})
        self.assertEqual(report['vff_create_sizes'], [])
        self.assertEqual(report['native_return'], 0)

    def test_external_failures_preserve_native_partial_progress_without_registered_success(self):
        c = fixture_configuration()
        cases = [('lookup', -3, None, 16, 'lookup'), ('find_vff', -1, None, 16, 'find_vff'),
                 ('create_vff', -1, None, 12, 'create_vff'), ('keys', -1, None, 12, 'keys'),
                 ('add', -1, None, 12, 'add'), ('update', -1, existing_image(c), 12, 'update')]
        for boundary, status, previous, code, last in cases:
            report = verify_task_preparation(self.source, c, existing_task=previous, outcomes={boundary: status})
            self.assertEqual(report['native_return'], code)
            self.assertEqual(report['events'][-1], last)
            self.assertFalse(report['task_registration_or_persistence_verified'])
        for outcomes in ({'private-marker': 0}, {'add': True}, {'add': 1 << 31}):
            with self.assertRaises(ValueError):
                verify_task_preparation(self.source, c, existing_task=None, outcomes=outcomes)
        with self.assertRaises(ValueError):
            verify_task_preparation(self.source, c, existing_task=existing_image(c), outcomes={'lookup': -13})
