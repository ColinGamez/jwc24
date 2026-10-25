"""Original task setup/reader contracts; synthetic services and private code."""
import os
from pathlib import Path
import unittest

from tools.verify_news_tasks import (verify_queued_task_settings, verify_reader_slot_order,
                                     verify_subtask_filename, verify_task_registration)


class NewsTaskHarnessInputTests(unittest.TestCase):
    def test_wrong_source_is_rejected_without_private_content(self):
        for run in (verify_queued_task_settings, verify_reader_slot_order,
                    verify_subtask_filename, verify_task_registration):
            with self.subTest(run=run.__name__), self.assertRaises(ValueError) as caught:
                run(b'private-source-marker')
            self.assertNotIn('private-source-marker', str(caught.exception))

    def test_fixture_option_types_and_bounds_are_checked_before_native_imports(self):
        cases = ((verify_queued_task_settings, {'interval': True}),
                 (verify_queued_task_settings, {'count': 65536}),
                 (verify_queued_task_settings, {'queued_count': 9}),
                 (verify_task_registration, {'interval': 0}),
                 (verify_task_registration, {'fail_service': 'private-unknown-service'}),
                 (verify_reader_slot_order, {'hour': 24}),
                 (verify_reader_slot_order, {'hour': True}),
                 (verify_subtask_filename, {'slot': 24}),
                 (verify_subtask_filename, {'capacity': 0}))
        for run, kwargs in cases:
            with self.subTest(run=run.__name__, kwargs=kwargs), self.assertRaises(ValueError):
                run(b'', **kwargs)


class NewsTaskNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (Path(os.environ.get('APPDATA', ''))
                / 'Dolphin Emulator/Wii/title/00010002/4841474a/content/0000000b.app')
        if not path.is_file():
            raise unittest.SkipTest('Private original Japanese News v7 code unavailable')
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependency unavailable')
        cls.source = path.read_bytes()

    def test_one_news_task_has_24_subtask_bits_and_original_local_filename(self):
        result = verify_task_registration(self.source)
        self.assertEqual(result['native_return'], 0)
        self.assertEqual(result['setter_arguments'], {
            'init_task': 1, 'create_vf': 0x3A0000,
            'set_url': {'matches_explicit_fixture_url': True},
            'set_server_interval': 1440,
            'set_subtask_parameters': [2, 0xFFFFFF, 0x103],
            'set_priority': 100, 'set_flags': 0x40000000,
            'set_interval': 30, 'set_retry_margin': 720, 'set_count': 240,
        })
        self.assertEqual(result['sdk_calls_stubbed'].count('add_task'), 1)
        self.assertEqual(result['native_formatted_filenames'], ['2.bin'])
        self.assertTrue(result['original_integer_filename_formatter_executed'])
        self.assertTrue(result['guard_checks_passed'])
        self.assertFalse(result['sdk_storage_and_task_commit_executed'])
        self.assertFalse(result['full_first_run_or_download_verified'])

    def test_matching_existing_task_updates_count_without_recreating_it(self):
        result = verify_task_registration(self.source, existing=True)
        self.assertEqual(result['native_return'], 0)
        self.assertEqual(result['setter_arguments'], {'set_count': 240})
        self.assertIn('update_task', result['sdk_calls_stubbed'])
        self.assertNotIn('add_task', result['sdk_calls_stubbed'])
        self.assertNotIn('init_task', result['sdk_calls_stubbed'])
        self.assertFalse(result['original_integer_filename_formatter_executed'])

    def test_schedule_inputs_transfer_without_inventing_sdk_acceptance(self):
        result = verify_task_registration(self.source, interval=45, count=480)
        self.assertEqual(result['setter_arguments']['set_interval'], 45)
        self.assertEqual(result['setter_arguments']['set_count'], 480)
        result = verify_task_registration(self.source, count=65535)
        self.assertEqual(result['setter_arguments']['set_count'], 0xFFFFFFFF)
        self.assertFalse(result['sdk_storage_and_task_commit_executed'])

    def test_injected_sdk_errors_stop_later_task_operations(self):
        for name in ('set_url', 'set_flags', 'set_count', 'add_task'):
            with self.subTest(name=name):
                result = verify_task_registration(self.source, fail_service=name)
                self.assertEqual(result['native_return'], -6)
                self.assertTrue(result['sdk_failure_injected'])
                self.assertEqual(result['sdk_calls_stubbed'][-1], name)
                self.assertNotIn('post_commit_task_helper', result['sdk_calls_stubbed'])

    def test_actual_queue_creator_defaults_and_nonzero_schedule(self):
        result = verify_queued_task_settings(self.source)
        self.assertEqual(result['settings'], {'job_kind': 2, 'task_type': 2,
                                             'interval': 30, 'count': 240,
                                             'max_vf_bytes': 0x3A0000})
        self.assertEqual(result['native_return'], 0)
        self.assertFalse(result['real_worker_scheduler_or_task_registration_verified'])
        self.assertEqual(verify_queued_task_settings(self.source, interval=45, count=480)['settings'],
                         dict(result['settings'], interval=45, count=480))

    def test_actual_queue_creator_rejects_full_or_refused_submission(self):
        full = verify_queued_task_settings(self.source, queued_count=8)
        self.assertEqual((full['native_return'], full['submitted_descriptors']), (-1, 0))
        refused = verify_queued_task_settings(self.source, queue_accept=False)
        self.assertEqual((refused['native_return'], refused['submitted_descriptors']), (-1, 1))

    def test_original_filename_getter_maps_every_slot_with_capacity_checks(self):
        for slot in range(24):
            with self.subTest(slot=slot):
                result = verify_subtask_filename(self.source, slot=slot, capacity=9)
                self.assertEqual(result['native_return'], 0)
                self.assertEqual(result['synthetic_local_filename'], f'2.bin.{slot:02d}')
                self.assertTrue(result['original_sdk_getter_and_formatters_executed'])
                self.assertFalse(result['remote_url_or_download_verified'])
        self.assertEqual(verify_subtask_filename(self.source, capacity=8)['native_return'], -11)
        self.assertEqual(verify_subtask_filename(self.source, subtasks_enabled=False, capacity=6)
                         ['synthetic_local_filename'], '2.bin')

    def test_original_reader_visits_every_hour_slot_backwards_modulo24(self):
        for hour in range(24):
            with self.subTest(hour=hour):
                result = verify_reader_slot_order(self.source, hour=hour)
                self.assertEqual(result['requested_slots'], [(hour - offset) % 24 for offset in range(24)])
                self.assertEqual(result['cleared_buffer_slots'], [])
                self.assertTrue(result['guard_checks_passed'])
                self.assertFalse(result['download_or_real_storage_verified'])

    def test_original_early_loader_result_clears_remaining_synthetic_slots(self):
        for hour in (0, 3, 23):
            with self.subTest(hour=hour):
                result = verify_reader_slot_order(self.source, hour=hour, stop_after_current=True)
                self.assertEqual(result['requested_slots'], [hour])
                self.assertEqual(result['cleared_buffer_slots'], list(range(24)))


if __name__ == '__main__':
    unittest.main()
