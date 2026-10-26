"""Private original optional; identity refusal always runs without Unicorn."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from tools.verify_forecast_precipitation import original_block, verify


class ForecastOriginalPrecipitationTests(unittest.TestCase):
    def test_refuses_unverified_image_before_emulation(self):
        with tempfile.TemporaryDirectory(prefix='jwc24-forecast-proof-') as temporary:
            root = Path(temporary).resolve()
            self.assertEqual(root.parent, Path(tempfile.gettempdir()).resolve())
            path = root / 'unverified.app'
            path.write_bytes(b'not an original application')
            with self.assertRaisesRegex(ValueError, 'identity'):
                original_block(path)

    def test_all_four_original_probability_bytes_exhaustively(self):
        root = Path(__file__).resolve().parents[1]
        default = root / ('private/forecast/snapshots/pre-jwc24-wad-install-20260802-054502/'
                          'title-00010002-4841464a/content/0000000d.app')
        path = Path(os.environ.get('JWC24_FORECAST_ORIGINAL', str(default)))
        if not path.is_file():
            self.skipTest('Pinned private original HAFJ v7 input is not available')
        if importlib.util.find_spec('unicorn') is None:
            self.skipTest('Optional Unicorn reverse-engineering dependency is not installed')
        report = verify(path)
        self.assertEqual(report['cases'], 1024)
        self.assertEqual(report['preserved_zero_cases'], 408)
        self.assertEqual(report['set_minus_one_cases'], 616)
        self.assertTrue(report['read_only_code_and_record_pages'])
        self.assertTrue(report['immutable_input_guards_verified'])
        for claim in ('hooks_or_service_mocks', 'full_validator_executed',
                      'caller_result_propagation_verified', 'native_ui_verified'):
            self.assertFalse(report[claim])
