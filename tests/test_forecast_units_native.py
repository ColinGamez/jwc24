"""Original consumers optional; no private text, assets or live settings in tests."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.verify_forecast_units import _image, main, verify_condition_dispatch, verify_temperature_format_prefix, verify_wind


class ForecastUnitsPublicTests(unittest.TestCase):
    def test_identity_refusal_precedes_optional_native_import(self):
        for operation in (_image, verify_wind, verify_condition_dispatch, verify_temperature_format_prefix):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(ValueError, 'identity') as caught:
                    operation(b'private-input-marker')
                self.assertNotIn('private-input-marker', str(caught.exception))

    def test_nonimmutable_inputs_refuse_without_coercion(self):
        for value in (bytearray(16), memoryview(bytes(16)), None, 'private-input-marker'):
            with self.assertRaisesRegex(ValueError, 'identity'):
                _image(value)

    def test_cli_unavailable_original_is_redacted(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-path-marker')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(['private-path-marker'])
        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('private-path-marker', errors.getvalue())


class ForecastUnitsOriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / (
            'private/forecast/snapshots/pre-jwc24-wad-install-20260802-054502/'
            'title-00010002-4841464a/content/0000000d.app')
        if not path.is_file():
            raise unittest.SkipTest('Pinned private HAFJ v7 original unavailable')
        if importlib.util.find_spec('unicorn') is None:
            raise unittest.SkipTest('Optional native execution dependency unavailable')
        cls.source = path.read_bytes()

    def test_actual_byte_selection_full_original_formatter_and_missing_branch_boundary(self):
        report = verify_wind(self.source)
        self.assertEqual(report['cases'], 1152)
        self.assertEqual(report['complete_original_formatter_cases'], 1142)
        self.assertEqual(report['observed_invalid_read_cases'], 2)
        self.assertEqual(report['missing_direction_suppressed_cases'], 8)
        self.assertEqual(report['settings_selector_zero']['day_offset'], 24)
        self.assertEqual(report['settings_selector_zero']['display_unit'], 'mph')
        self.assertEqual(report['settings_selector_one']['day_offset'], 23)
        self.assertEqual(report['settings_selector_one']['display_unit'], 'km/h')
        self.assertTrue(report['caller_byte_selection_and_japanese_dispatch_executed'])
        self.assertTrue(report['complete_original_formatter_and_helpers_executed_for_successful_cases'])
        self.assertTrue(report['input_settings_static_and_guards_unchanged'])
        self.assertFalse(report['helpers_or_service_boundaries_stubbed'])
        self.assertFalse(report['fractional_provider_rounding_verified'])
        self.assertFalse(report['native_ui_rendered'])
        self.assertFalse(report['real_settings_profile_or_device_io'])
        self.assertEqual(report['isolated_invalid_read_boundary']['pc'], '0x8016f574')
        self.assertEqual([row['meaning'] for row in report['native_direction_labels']],
                         ['calm', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N'])
        self.assertTrue(report['nonzero_direction_label_arguments_executed'])

    def test_actual_numerical_condition_dispatch_is_not_a_provider_mapping(self):
        report = verify_condition_dispatch(self.source)
        self.assertEqual(report['cases'], 262)
        self.assertEqual(report['native_low15_selector_range'], [0, 126])
        self.assertTrue(report['high_bit_preserved_as_separate_argument'])
        self.assertTrue(report['original_selector_and_table_executed'])
        self.assertTrue(report['source_and_guards_unchanged'])
        self.assertEqual(report['complete_original_lookup_cases'], 60)
        self.assertTrue(report['primary_u16_key_distinct_from_secondary_u16_graphical_selector'])
        self.assertTrue(report['absent_key_getter_returns_ffff'])
        self.assertFalse(report['original_lookup_stubbed'])
        self.assertIn(100, report['in_range_unmapped_selectors'])
        self.assertFalse(report['pre_graphics_prefix_or_drawing_suffix_executed'])
        self.assertFalse(report['jma_or_provider_semantic_mapping_verified'])
        self.assertFalse(report['original_graphics_rendered'])

    def test_actual_integer_temperature_prefix_does_not_invent_fractional_rounding(self):
        report = verify_temperature_format_prefix(self.source)
        self.assertEqual(report['cases'], 256)
        self.assertEqual(report['preserved_signed_integer_cases'], 255)
        self.assertEqual(report['missing_minus_128_cases'], 1)
        self.assertTrue(report['source_and_guards_unchanged'])
        self.assertTrue(report['original_prefix_and_string_numeric_helpers_executed'])
        self.assertFalse(report['helpers_stubbed'])
        self.assertFalse(report['fractional_provider_rounding_or_unit_conversion_verified'])
        self.assertFalse(report['temperature_field_selection_or_full_draw_function_executed'])
        self.assertFalse(report['native_ui_rendered'])
