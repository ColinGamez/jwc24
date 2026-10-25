"""Japanese retail validator comparisons on generated synthetic buffers only."""
import os
from pathlib import Path
import struct
import unittest

from jwc24.news import NewsFormatError, inspect_news
from tests.test_news import change_word, reseal, synthetic_news
from tools.verify_news_native import verify_news_buffers


class NewsNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (Path(os.environ.get('APPDATA', ''))
                / 'Dolphin Emulator/Wii/title/00010002/4841474a/content/0000000b.app')
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese News v7 executable unavailable')
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependency unavailable')
        cls.source = path.read_bytes()

    def native(self, raw, **kwargs):
        return verify_news_buffers(self.source, [raw] * 24, **kwargs)

    def test_original_validator_crc_and_five_native_record_tables_execute(self):
        result = self.native(synthetic_news())
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['selected_slot'], 0)
        self.assertEqual(result['counts']['crc_calls'], 24)
        self.assertEqual(result['mutated_slots'], [])
        self.assertFalse(result['native_validator_and_crc_stubbed'])
        self.assertTrue(result['input_and_stack_guards_verified'])

    def test_missing_hourly_slot_is_separate_from_single_buffer_validity(self):
        raw = synthetic_news()
        inspect_news(raw)
        result = verify_news_buffers(self.source, [raw] + [None] * 23)
        self.assertEqual(result['status'], -2)
        self.assertEqual(result['selected_slot'], 0)
        self.assertEqual(result['refresh_mask'], 0xFFFFFF)
        self.assertEqual(result['counts']['calendar_calls'], 1)

    def test_crc_size_and_version_failures_follow_original_paths(self):
        raw = synthetic_news()
        damaged = bytearray(raw)
        damaged[-3] ^= 1
        for data, status in ((bytes(damaged), -1), (change_word(raw, 4, len(raw) - 1), -1),
                             (change_word(raw, 0, 0x10000), -3)):
            with self.subTest(status=status):
                self.assertEqual(self.native(data)['status'], status)
                with self.assertRaises(NewsFormatError):
                    inspect_news(data)
        self.assertEqual(self.native(change_word(raw, 0, 0xFFFF))['status'], 0)

    def test_native_header_flags_and_language_boundaries(self):
        for offset, value in ((28, 7), (45, 2), (46, 2)):
            raw = bytearray(synthetic_news())
            raw[offset] = value
            with self.subTest(offset=offset):
                self.assertEqual(self.native(reseal(raw))['status'], -1)
        raw[28:44] = bytes(16)
        self.assertEqual(self.native(reseal(raw))['status'], -1)

    def test_all_five_native_table_bounds_reject_oversized_and_unaligned(self):
        raw = synthetic_news()
        for count_offset in (52, 60, 68, 76, 84):
            for offset, value in ((count_offset, 1000), (count_offset + 4, 105)):
                with self.subTest(offset=offset):
                    self.assertEqual(self.native(change_word(raw, offset, value))['status'], -1)

    def test_selected_article_source_location_and_picture_indices(self):
        raw = synthetic_news()
        for offset in (120, 124, 132):
            with self.subTest(offset=offset):
                self.assertEqual(self.native(change_word(raw, offset, 1))['status'], -1)
                self.assertEqual(self.native(change_word(raw, offset, 0xFFFFFFFF))['status'], 0)

    def test_unknown_article_and_large_body_prune_latest_topic_in_native_ram(self):
        for raw in (synthetic_news(reference_id=9), synthetic_news(body_text='x' * 10000)):
            with self.subTest(size=len(raw)):
                result = self.native(raw)
                self.assertEqual(result['status'], 0)
                self.assertEqual(result['mutated_slots'], [0])
                with self.assertRaises(NewsFormatError):
                    inspect_news(raw)

    def test_native_time_checks_are_distinct_and_end_is_inclusive(self):
        raw = synthetic_news()
        self.assertEqual(self.native(raw, current_minute=11000)['status'], 0)
        self.assertEqual(self.native(raw, current_minute=11001)['status'], -2)
        self.assertEqual(self.native(change_word(raw, 24, 11440))['status'], 0)
        self.assertEqual(self.native(change_word(raw, 24, 11441))['status'], -1)

    def test_expired_buffer_with_server_message_is_not_a_current_news_claim(self):
        raw = synthetic_news()
        title = struct.unpack_from('>I', raw, 148)[0]
        raw = change_word(change_word(raw, 16, 9999), 48, title)
        self.assertEqual(self.native(raw)['status'], 0)
        result = inspect_news(raw)
        self.assertTrue(result.metadata()['server_message_present'])
        self.assertFalse(result.metadata()['current_validity_checked'])

    def test_native_wrapped_count_is_trapped_by_read_guard_not_called_valid(self):
        raw = change_word(synthetic_news(), 76, 0x10000000)
        with self.assertRaisesRegex(ValueError, 'read exceeds synthetic input bounds'):
            self.native(raw)
        with self.assertRaises(NewsFormatError):
            inspect_news(raw)

    def test_local_headline_and_utf16_checks_are_stricter_than_this_native_pass(self):
        raw = synthetic_news()
        for offset, value in ((100, len(raw) + 4), (144, 1)):
            with self.subTest(offset=offset):
                self.assertEqual(self.native(change_word(raw, offset, value))['status'], 0)
                with self.assertRaises(NewsFormatError):
                    inspect_news(change_word(raw, offset, value))

    def test_wrong_source_and_invalid_slot_inputs_are_rejected_without_echo(self):
        for source, slots in ((b'private-source', [None] * 24),
                              (self.source, [None] * 23),
                              (self.source, [b'private-news'] * 24)):
            with self.subTest(length=len(slots)), self.assertRaises(ValueError) as caught:
                verify_news_buffers(source, slots)
            self.assertNotIn('private-news', str(caught.exception))
            self.assertNotIn('private-source', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
