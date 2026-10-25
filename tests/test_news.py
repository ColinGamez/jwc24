"""Synthetic News structural cases; no original assets or publisher articles."""
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from jwc24.forecast import encode_lz10
from jwc24.news import NewsFormatError, inspect_news, inspect_news_envelope
from tools.inspect_news import main


def reseal(raw):
    data = bytearray(raw)
    struct.pack_into('>I', data, 8, zlib.crc32(data[12:]) & 0xFFFFFFFF)
    return bytes(data)


def change_word(raw, offset, value):
    data = bytearray(raw)
    struct.pack_into('>I', data, offset, value)
    return reseal(data)


def synthetic_news(*, body_text='Synthetic article body \u672c\u6587',
                   reference_time=10000, reference_id=0x11223344):
    """Independent explicit fixture writer for tests only; no publication API."""
    data = bytearray(244)  # 104-byte header, six tables, one timestamp pair.
    struct.pack_into('>7I', data, 0, 512, 0, 0, 10000, 11000, 0x01000000, 10000)
    data[28:44] = b'\0' + b'\xFF' * 15
    data[47] = 30
    for offset, table in ((52, 104), (60, 116), (68, 160), (76, 188),
                          (84, 204), (96, 228)):
        struct.pack_into('>II', data, offset, 1, table)
    struct.pack_into('>HH', data, 92, 480, 0)

    def text(value):
        offset = len(data)
        encoded = value.encode('utf-16-be')
        data.extend(encoded + b'\0\0')
        data.extend(bytes(-len(data) % 4))
        return len(encoded), offset

    title_size, title = text('Synthetic headline \u65e5\u672c\u8a9e \U0001F30F')
    body_size, body = text(body_text)
    name_size, name = text('Synthetic source')
    copyright_size, copyright_offset = text('Synthetic copyright')
    _, place = text('Synthetic location')
    image = len(data)
    image_bytes = b'synthetic-media-not-a-jpeg'
    data.extend(image_bytes)
    data.extend(bytes(-len(data) % 4))
    struct.pack_into('>3I', data, 104, 0, 1, 236)
    struct.pack_into('>11I', data, 116, 0x11223344, 0, 0, 10000, 0,
                     10000, 10000, title_size, title, body_size, body)
    struct.pack_into('>BBH6I', data, 160, 1, 1, 0, 0, 0, name_size,
                     name, copyright_size, copyright_offset)
    struct.pack_into('>IhhBBHB3x', data, 188, place, 100, 200, 1, 2, 3, 6)
    struct.pack_into('>6I', data, 204, 0, 0, 0, 0, len(image_bytes), image)
    struct.pack_into('>2I', data, 228, title_size, title)
    struct.pack_into('>2I', data, 236, reference_time, reference_id)
    struct.pack_into('>I', data, 4, len(data))
    return reseal(data)


class NewsInspectionTests(unittest.TestCase):
    def test_all_six_tables_and_japanese_surrogate_text_decode(self):
        result = inspect_news(synthetic_news())
        self.assertEqual((result.topics, len(result.articles), result.sources,
                          result.locations, result.images, result.headlines), (1, 1, 1, 1, 1, 1))
        self.assertEqual(result.articles[0].text, 'Synthetic article body \u672c\u6587')
        self.assertIn('\U0001F30F', result.articles[0].headline)
        metadata = json.dumps(result.metadata())
        self.assertNotIn('Synthetic', metadata)
        self.assertNotIn('11223344', metadata)
        self.assertNotIn('Synthetic', repr(result))
        self.assertFalse(result.metadata()['signatures_checked'])
        self.assertFalse(result.metadata()['cross_buffer_references_checked'])

    def test_lz10_envelope_is_only_structural_and_not_signature_success(self):
        raw = synthetic_news()
        result = inspect_news_envelope(bytes(320) + encode_lz10(raw))
        self.assertEqual(result.byte_length, len(raw))
        self.assertFalse(result.metadata()['signatures_checked'])
        for bad in (bytes(324), bytes(320) + b'\x10\xFF\xFF\xFF',
                    bytes(320) + encode_lz10(raw)[:-8]):
            with self.subTest(length=len(bad)), self.assertRaises(NewsFormatError):
                inspect_news_envelope(bad)

    def test_crc_declared_size_and_version_high_word_fail(self):
        raw = synthetic_news()
        changed = bytearray(raw)
        changed[-3] ^= 1
        for bad in (bytes(changed), change_word(raw, 4, len(raw) - 1),
                    change_word(raw, 0, 0x10000), b'\0' * 103):
            with self.subTest(length=len(bad)), self.assertRaises(NewsFormatError):
                inspect_news(bad)
        self.assertEqual(inspect_news(change_word(raw, 0, 0xFFFF)).version, 0xFFFF)

    def test_language_terminator_codes_and_boolean_flags_are_checked(self):
        for offset, value in ((28, 7), (45, 2), (46, 2)):
            raw = bytearray(synthetic_news())
            raw[offset] = value
            with self.subTest(offset=offset), self.assertRaises(NewsFormatError):
                inspect_news(reseal(raw))
        raw[28:44] = bytes(16)
        with self.assertRaises(NewsFormatError):
            inspect_news(reseal(raw))

    def test_all_table_bounds_alignment_counts_and_header_aliases_fail(self):
        raw = synthetic_news()
        for count_offset in (52, 60, 68, 76, 84, 96):
            for offset, value in ((count_offset, 0xFFFFFFFF),
                                  (count_offset + 4, len(raw) + 4),
                                  (count_offset + 4, 105), (count_offset + 4, 4)):
                with self.subTest(field=offset, value=value), self.assertRaises(NewsFormatError):
                    inspect_news(change_word(raw, offset, value))
        with self.assertRaisesRegex(NewsFormatError, 'overlap'):
            inspect_news(change_word(raw, 64, 104))

    def test_local_article_indices_and_topic_identity_are_checked(self):
        raw = synthetic_news()
        for offset in (120, 124, 132):
            with self.subTest(offset=offset), self.assertRaises(NewsFormatError):
                inspect_news(change_word(raw, offset, 1))
            self.assertEqual(len(inspect_news(change_word(raw, offset, 0xFFFFFFFF)).articles), 1)
        with self.assertRaisesRegex(NewsFormatError, 'missing local article'):
            inspect_news(synthetic_news(reference_id=9))

    def test_cross_hour_references_are_retained_as_unresolved(self):
        raw = synthetic_news(reference_time=9999, reference_id=9)
        result = inspect_news(change_word(raw, 128, 9998))
        self.assertEqual(result.external_topic_references, 1)
        self.assertEqual(result.external_image_references, 1)
        self.assertFalse(result.metadata()['cross_buffer_references_checked'])

    def test_utf16_odd_sizes_terminators_and_body_pruning_threshold(self):
        raw = synthetic_news()
        for offset, value in ((144, 1), (148, 245), (152, 1), (156, 4), (188, 0)):
            with self.subTest(offset=offset), self.assertRaises(NewsFormatError):
                inspect_news(change_word(raw, offset, value))
        title_offset = struct.unpack_from('>I', raw, 148)[0]
        title_size = struct.unpack_from('>I', raw, 144)[0]
        broken = bytearray(raw)
        broken[title_offset:title_offset + 2] = b'\xD8\0'
        with self.assertRaises(NewsFormatError):
            inspect_news(reseal(broken))
        broken = bytearray(raw)
        broken[title_offset + title_size:title_offset + title_size + 2] = b'\0x'
        with self.assertRaises(NewsFormatError):
            inspect_news(reseal(broken))
        self.assertEqual(len(inspect_news(synthetic_news(body_text='x' * 9999)).articles), 1)
        with self.assertRaises(NewsFormatError):
            inspect_news(synthetic_news(body_text='x' * 10000))

    def test_source_flags_and_image_payload_boundaries_are_checked(self):
        raw = synthetic_news()
        for offset, value in ((160, 7), (161, 0)):
            changed = bytearray(raw)
            changed[offset] = value
            with self.subTest(offset=offset), self.assertRaises(NewsFormatError):
                inspect_news(reseal(changed))
        for offset, value in ((164, 1), (220, 0), (224, 0), (224, len(raw))):
            with self.subTest(offset=offset), self.assertRaises(NewsFormatError):
                inspect_news(change_word(raw, offset, value))

    def test_cli_bounds_and_scope_hide_path_and_article_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private-selector-news.bin'
            path.write_bytes(synthetic_news())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path), '--raw']), 0)
            self.assertTrue(json.loads(output.getvalue())['structural_inspection_passed'])
            self.assertNotIn('private-selector', output.getvalue())
            self.assertNotIn('Synthetic', output.getvalue())
            path.write_bytes(b'private article data')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path), '--raw']), 1)
            self.assertNotIn('private', output.getvalue())

    def test_aggregate_decoded_text_budget_prevents_reference_expansion(self):
        with patch('jwc24.news.MAX_DECODED_TEXT_BYTES', 10):
            with self.assertRaisesRegex(NewsFormatError, 'aggregate byte limit'):
                inspect_news(synthetic_news())


if __name__ == '__main__':
    unittest.main()
