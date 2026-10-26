"""Original display-model checks on explicit synthetic News records only."""
from copy import deepcopy
import os
from pathlib import Path
import struct
import unittest
import zlib

from jwc24.news import NewsFormatError, inspect_news
from jwc24.news_records import encode_news_records
from tests.test_news_records import explicit_records
from tools.verify_news_headline_model import verify_news_headline_model


class HeadlineModelInputTests(unittest.TestCase):
    def test_wrong_original_input_rejects_without_echoing_content(self):
        with self.assertRaises(ValueError) as caught:
            verify_news_headline_model(b'private-marker', b'private-input',
                                       expected_title='private-copy', expected_source_name=None)
        self.assertNotIn('private', str(caught.exception))


class NewsHeadlineModelNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (Path(os.environ.get('APPDATA', ''))
                / 'Dolphin Emulator/Wii/title/00010002/4841474a/content/0000000b.app')
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese News v7 executable unavailable')
        try:
            import capstone  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def verify(self, spec, *, raw=None, index=0):
        article = spec['articles'][index]
        name = (None if article['source_index'] is None
                else spec['sources'][article['source_index']]['name'])
        return verify_news_headline_model(
            self.source, encode_news_records(spec) if raw is None else raw,
            expected_title=article['title'], expected_source_name=name, article_index=index)

    def test_complete_constructor_and_native_utf16_helpers_copy_title_and_source(self):
        result = self.verify(explicit_records())
        self.assertTrue(result['constructor_finished'])
        self.assertTrue(result['exact_display_text_verified'])
        self.assertTrue(result['source_name_appended'])
        self.assertEqual(result['counts']['allocations'], 4)
        self.assertEqual(result['counts']['native_wcslen_calls'], 1)
        self.assertEqual(result['counts']['native_wcscpy_calls'], 1)
        self.assertEqual(result['counts']['native_wcscat_calls'], 2)
        self.assertEqual(result['counts']['ticker_header_reads'], 0)
        self.assertEqual(result['counts']['ticker_table_reads'], 0)
        self.assertTrue(result['input_and_output_guards_verified'])
        self.assertFalse(result['native_constructor_or_strings_stubbed'])
        self.assertFalse(result['ticker_table_consumer_verified'])
        self.assertFalse(result['buffer_validation_signatures_delivery_or_rendering_verified'])

    def test_separate_ticker_text_is_not_used_by_this_article_constructor(self):
        for headlines in ([], ['Explicit synthetic ticker'],
                          ['別の合成テロップ 🌏', 'Second synthetic ticker']):
            with self.subTest(count=len(headlines)):
                spec = explicit_records()
                spec['headlines'] = headlines
                result = self.verify(spec)
                self.assertTrue(result['exact_display_text_verified'])
                self.assertEqual(result['counts']['ticker_header_reads'], 0)
                self.assertEqual(result['counts']['ticker_table_reads'], 0)

    def test_invalid_ticker_table_is_a_negative_scope_control_not_valid_news(self):
        spec = explicit_records()
        raw = bytearray(encode_news_records(spec))
        struct.pack_into('>II', raw, 96, 0xFFFFFFFF, 0xFFFFFFFC)
        struct.pack_into('>I', raw, 8, zlib.crc32(raw[12:]))
        with self.assertRaises(NewsFormatError):
            inspect_news(bytes(raw))
        result = self.verify(spec, raw=bytes(raw))
        self.assertTrue(result['exact_display_text_verified'])
        self.assertEqual(result['counts']['ticker_header_reads'], 0)
        self.assertFalse(result['ticker_table_consumer_verified'])

    def test_absent_references_preserve_exact_supplied_title_without_source_suffix(self):
        spec = explicit_records()
        spec['sources'] = spec['locations'] = spec['images'] = []
        spec['articles'][0].update(source_index=None, location_index=None,
                                  picture_timestamp=0, picture_index=None,
                                  title='  合成タイトル\n日本語 🌏  ')
        result = self.verify(spec)
        self.assertTrue(result['exact_display_text_verified'])
        self.assertFalse(result['source_name_appended'])
        self.assertEqual(result['counts']['allocations'], 3)
        self.assertEqual(result['counts']['native_wcscat_calls'], 0)

    def test_later_article_is_resolved_by_identifier_through_native_stride(self):
        spec = explicit_records()
        second = deepcopy(spec['articles'][0])
        second.update(identifier=0x55667788, title='Second synthetic title 日本語')
        spec['articles'].append(second)
        result = self.verify(spec, index=1)
        self.assertTrue(result['article_title_reference_verified'])
        self.assertTrue(result['exact_display_text_verified'])

    def test_bad_title_pointer_traps_at_native_copy_without_echoing_input(self):
        spec = explicit_records()
        raw = bytearray(encode_news_records(spec))
        article = struct.unpack_from('>I', raw, 64)[0]
        struct.pack_into('>I', raw, article + 32, len(raw) + 4)
        with self.assertRaises(ValueError) as caught:
            self.verify(spec, raw=bytes(raw))
        self.assertNotIn(spec['articles'][0]['title'], str(caught.exception))
        self.assertIn('bounds', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
