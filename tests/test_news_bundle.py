"""Explicit synthetic graph checks, never publisher content or a news service."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24.forecast import encode_lz10
from jwc24.news import NewsFormatError, inspect_news
from jwc24.news_bundle import inspect_news_bundle
from tests.test_news import change_word, synthetic_news
from tools.inspect_news_bundle import main


def older():
    return change_word(change_word(synthetic_news(reference_time=9999), 12, 9999), 128, 9999)


class NewsBundleTests(unittest.TestCase):
    def test_repeated_complete_snapshot_resolves_without_claiming_hourly_coverage(self):
        result = inspect_news_bundle([synthetic_news()] * 24)
        self.assertEqual(result.distinct_snapshots, 1)
        self.assertEqual(result.repeated_snapshots, 23)
        self.assertTrue(result.metadata()['cross_buffer_references_checked'])
        for key in ('time_slot_mapping_or_24_hour_coverage_verified', 'signatures_checked',
                    'current_validity_checked', 'native_delivery_or_rendering_verified'):
            self.assertFalse(result.metadata()[key])
        self.assertNotIn('Synthetic', repr(result))

    def test_cross_snapshot_topics_and_images_resolve_against_target_snapshot(self):
        latest = change_word(synthetic_news(reference_time=9999), 128, 9999)
        result = inspect_news_bundle([latest] + [older()] * 23)
        self.assertEqual(result.distinct_snapshots, 2)
        self.assertEqual(result.cross_buffer_topic_references, 1)
        self.assertEqual(result.cross_buffer_image_references, 1)

    def test_missing_snapshot_article_and_image_references_fail_without_pruning(self):
        latest = synthetic_news(reference_time=9998)
        self.assertEqual(inspect_news(latest).external_topic_references, 1)
        for latest in (latest, synthetic_news(reference_time=9999, reference_id=7),
                       change_word(synthetic_news(), 128, 9998),
                       change_word(change_word(synthetic_news(), 128, 9999), 132, 1)):
            with self.subTest(length=len(latest)), self.assertRaises(NewsFormatError):
                inspect_news_bundle([latest] + [older()] * 23)

    def test_conflicting_snapshot_definitions_and_mixed_locales_are_rejected(self):
        raw = synthetic_news()
        for other in (synthetic_news(body_text='Different synthetic text'),
                      change_word(older(), 20, 0x02000000)):
            with self.assertRaises(NewsFormatError):
                inspect_news_bundle([raw] + [other] * 23)

    def test_envelopes_are_structural_and_sentinels_are_not_invented_images(self):
        raw = change_word(change_word(synthetic_news(), 128, 9998), 132, 0xFFFFFFFF)
        envelopes = [bytes(320) + encode_lz10(raw)] * 24
        result = inspect_news_bundle(envelopes, enveloped=True)
        self.assertEqual(result.cross_buffer_image_references, 0)
        self.assertFalse(result.metadata()['signatures_checked'])

    def test_slot_and_aggregate_bounds_precede_decoding(self):
        raw = synthetic_news()
        for values in ([raw] * 23, [raw] * 25, [raw] * 23 + [None], bytes(24)):
            with self.assertRaises(NewsFormatError):
                inspect_news_bundle(values)
        with patch('jwc24.news_bundle.MAX_BUNDLE_BYTES', 10), \
             patch('jwc24.news_bundle.inspect_news', side_effect=AssertionError('decoded before bounds')):
            with self.assertRaises(NewsFormatError):
                inspect_news_bundle([raw] * 24)
        advertised = bytes(320) + b'\x10' + (2 * 1024 * 1024).to_bytes(3, 'little')
        with patch('jwc24.news_bundle.inspect_news_envelope', side_effect=AssertionError('decoded before aggregate bound')):
            with self.assertRaisesRegex(NewsFormatError, 'decoded byte limit'):
                inspect_news_bundle([advertised] * 24, enveloped=True)

    def test_cli_is_read_only_and_hides_paths_and_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private-marker'
            raw = synthetic_news()
            path.write_bytes(raw)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(['--raw', *([str(path)] * 24)]), 0)
            metadata = json.loads(output.getvalue())
            self.assertTrue(metadata['bundle_inspection_passed'])
            self.assertNotIn('private', output.getvalue())
            self.assertNotIn('Synthetic', output.getvalue())
            self.assertEqual(path.read_bytes(), raw)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(['--raw', str(path)]), 1)
            self.assertNotIn('private', output.getvalue())


class NewsBundleNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_news_native import NewsNativeTests
        NewsNativeTests.setUpClass()
        cls.source = NewsNativeTests.source

    def native(self, latest):
        from tools.verify_news_native import verify_news_buffers
        return verify_news_buffers(self.source, [latest] + [older()] * 23)

    def test_original_validator_resolves_cross_snapshot_article_and_image(self):
        latest = change_word(synthetic_news(reference_time=9999), 128, 9999)
        result = self.native(latest)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['mutated_slots'], [])
        self.assertEqual(inspect_news_bundle([latest] + [older()] * 23).distinct_snapshots, 2)

    def test_native_pruning_does_not_make_unresolved_topic_complete(self):
        latest = synthetic_news(reference_time=9998)
        result = self.native(latest)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['mutated_slots'], [0])
        with self.assertRaises(NewsFormatError):
            inspect_news_bundle([latest] + [older()] * 23)

    def test_native_bad_cross_snapshot_image_index_rejects_and_missing_snapshot_is_not_coverage(self):
        latest = change_word(change_word(synthetic_news(), 128, 9999), 132, 1)
        self.assertEqual(self.native(latest)['status'], -1)
        missing = change_word(synthetic_news(), 128, 9998)
        self.assertEqual(self.native(missing)['status'], 0)
        with self.assertRaises(NewsFormatError):
            inspect_news_bundle([missing] + [older()] * 23)
