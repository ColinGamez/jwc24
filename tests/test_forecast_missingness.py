"""Public policy cases and optional private-original branch comparisons."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from jwc24.forecast_index_policy import (IndexRow, native_direction_admitted,
                                        project_indices)
from tools.verify_forecast_missingness import original_image, verify


EMPTY = ((), (), ())


class ForecastIndexPolicyTests(unittest.TestCase):
    def test_ff_skips_membership_without_creating_rows(self):
        result = project_indices((255, 255, 255), EMPTY,
                                 selector_word=0, incoming_word=0x24681357)
        self.assertEqual(result.validation_word, 0x24681357)
        self.assertEqual(result.first_matches, (None, None, None))
        self.assertFalse(result.any_available)
        self.assertEqual(result.combined_value_modes, ('original_missing_string',) * 3)
        self.assertEqual(result.uv_only_value_mode, 'skip')
        self.assertEqual(project_indices((255, 255, 255), EMPTY, selector_word=0,
                                        incoming_word=0xFFFFFFFF).validation_word, 0xFFFFFFFF)

    def test_nonzero_selector_only_bypasses_laundry_and_pollen_membership(self):
        for selector in (1, 0xFFFFFFFF):
            accepted = project_indices((255, 0, 254), EMPTY,
                                       selector_word=selector, incoming_word=7)
            self.assertEqual(accepted.validation_word, 7)
            rejected = project_indices((0, 255, 255), EMPTY,
                                       selector_word=selector, incoming_word=7)
            self.assertEqual(rejected.validation_word, 0xFFFFFFFF)
        self.assertEqual(project_indices((255, 0, 254), EMPTY, selector_word=0,
                                        incoming_word=7).validation_word, 0xFFFFFFFF)

    def test_first_duplicate_and_explicit_ff_rows_remain_matchable(self):
        rows = (IndexRow(7, False), IndexRow(7, True), IndexRow(255, True))
        result = project_indices((7, 255, 7), (rows,) * 3,
                                 selector_word=0, incoming_word=0)
        self.assertEqual(result.first_matches, (0, 2, 0))
        self.assertEqual(result.validation_word, 0)
        self.assertTrue(result.any_available)
        self.assertTrue(result.uv_available)
        self.assertEqual(result.combined_helper_calls, (False, False, False))
        self.assertEqual(result.combined_value_modes,
                         ('integer', 'original_missing_string', 'integer'))

    def test_ff_row_availability_does_not_imply_numeric_or_image_presentation(self):
        rows = ((IndexRow(255, True),), (), ())
        result = project_indices((255, 255, 255), rows, selector_word=0, incoming_word=0)
        self.assertTrue(result.uv_available)
        self.assertTrue(result.any_available)
        self.assertFalse(result.combined_helper_calls[0])
        self.assertTrue(result.uv_only_helper_call)
        self.assertEqual(result.uv_only_value_mode, 'original_missing_string')

    def test_non_ff_null_text_still_selects_numeric_value(self):
        rows = ((IndexRow(0, False),), (IndexRow(7, True),), ())
        result = project_indices((0, 7, 255), rows, selector_word=0, incoming_word=0)
        self.assertEqual(result.combined_helper_calls, (False, True, False))
        self.assertEqual(result.combined_value_modes,
                         ('integer', 'integer', 'original_missing_string'))
        self.assertTrue(result.uv_only_helper_call)
        self.assertEqual(result.uv_only_value_mode, 'integer')

    def test_direction_validator_admits_zero_without_promising_render_safety(self):
        admitted = {value for value in range(256) if native_direction_admitted(value)}
        self.assertEqual(admitted, set(range(17)) | {255})

    def test_policy_requires_explicit_bounded_inputs(self):
        for value in (-1, 256, True, '255'):
            with self.assertRaises(ValueError):
                IndexRow(value, True)
            with self.assertRaises(ValueError):
                native_direction_admitted(value)
        with self.assertRaises(ValueError):
            IndexRow(0, 1)
        for kwargs in ({'selector_word': -1, 'incoming_word': 0},
                       {'selector_word': 0, 'incoming_word': 1 << 32}):
            with self.assertRaises(ValueError):
                project_indices((255, 255, 255), EMPTY, **kwargs)
        with self.assertRaises(ValueError):
            project_indices((255,), EMPTY, selector_word=0, incoming_word=0)
        with self.assertRaises(ValueError):
            project_indices((255, 255, 255), ((255,), (), ()),
                            selector_word=0, incoming_word=0)

    def test_unknown_original_refused_before_optional_dependency_import(self):
        with tempfile.TemporaryDirectory(prefix='jwc24-forecast-index-') as temporary:
            path = Path(temporary) / 'unverified.app'
            path.write_bytes(b'unverified')
            with self.assertRaisesRegex(ValueError, 'identity'):
                original_image(path)


class ForecastOriginalIndexTests(unittest.TestCase):
    def test_original_validation_lookup_and_display_branches(self):
        root = Path(__file__).resolve().parents[1]
        default = root / ('private/forecast/snapshots/pre-jwc24-wad-install-20260802-054502/'
                          'title-00010002-4841464a/content/0000000d.app')
        path = Path(os.environ.get('JWC24_FORECAST_ORIGINAL', str(default)))
        if not path.is_file():
            self.skipTest('Pinned private original HAFJ v7 input is not available')
        if importlib.util.find_spec('unicorn') is None:
            self.skipTest('Optional Unicorn reverse-engineering dependency is not installed')
        report = verify(path)
        self.assertEqual(report['comparisons']['direction'], 256)
        self.assertEqual(report['direction_admitted_cases'], 18)
        self.assertEqual(report['comparisons']['index_validation'], 3584)
        self.assertEqual(report['comparisons']['lookup'], 3840)
        self.assertEqual(report['comparisons']['availability'], 1372)
        self.assertEqual(report['comparisons']['combined_display'], 686)
        self.assertEqual(report['comparisons']['uv_only_display'], 686)
        self.assertEqual(report['comparisons']['direction_ff_suppression'], 2)
        self.assertEqual(report['total_comparisons'], 10426)
        for key in ('guarded_original_reads_and_writes', 'unchanged_original_sections_and_file',
                    'original_string_copy_and_integer_helpers_executed'):
            self.assertTrue(report[key])
        for key in ('cooked_table_constructor_executed', 'full_validator_executed',
                    'full_layout_selection_executed', 'native_pixels_or_service_verified',
                    'provider_conversion_implemented', 'speed_units_or_all_wind_combinations_verified'):
            self.assertFalse(report[key])
