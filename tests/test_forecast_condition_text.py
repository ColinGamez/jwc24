"""Selected actual native text consumers; no recovered labels/assets published."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.verify_forecast_condition_text import main, verify_condition_text


class ForecastConditionTextPublicTests(unittest.TestCase):
    def test_identity_refusal_precedes_optional_native_backend_import(self):
        with patch.dict('sys.modules', {'unicorn': None}):
            for value in (b'private-marker', bytearray(16), None):
                with self.assertRaisesRegex(ValueError, 'identity'):
                    verify_condition_text(value)

    def test_cli_failure_redacts_path_and_emits_no_report(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-marker')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(['private-marker'])
        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('private-marker', errors.getvalue())


class ForecastConditionTextOriginalTests(unittest.TestCase):
    def test_actual_pointer_lengths_and_line_control_branch_boundary(self):
        path = Path(__file__).resolve().parents[1] / (
            'private/forecast/snapshots/pre-jwc24-wad-install-20260802-054502/'
            'title-00010002-4841464a/content/0000000d.app')
        if not path.is_file():
            self.skipTest('Pinned private HAFJ application unavailable')
        if importlib.util.find_spec('unicorn') is None:
            self.skipTest('Optional native execution dependency unavailable')
        report = verify_condition_text(path.read_bytes())
        self.assertEqual(report['condition_label_pointer_handoff_cases'], 14)
        self.assertEqual(report['complete_original_primary_key_lookup_cases'], 14)
        self.assertEqual(report['complete_utf16_length_helper_cases'], 28)
        self.assertEqual(report['control_branch_cases'], 38)
        self.assertEqual(report['largest_tested_utf16_units'], 1024)
        self.assertTrue(report['source_static_inputs_and_guards_unchanged'])
        self.assertFalse(report['full_fitting_font_metrics_line_bounds_or_glyph_rendering_executed'])
        self.assertFalse(report['fixed_character_cap_established'])


if __name__ == '__main__':
    unittest.main()
