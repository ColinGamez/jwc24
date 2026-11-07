"""Synthetic membership guards and optional unchanged original condition slices."""
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from tests.test_forecast_resources import archive_fixture
from tools.verify_forecast_condition_semantics import (
    _member, main, verify_manual_membership, verify_native_semantics,
)


class ForecastSemanticsPublicTests(unittest.TestCase):
    def test_identity_refused_before_optional_execution_backend(self):
        with patch.dict('sys.modules', {'unicorn': None}):
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_native_semantics(b'private-marker')
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_manual_membership(b'private-marker', b'private-marker')

    def test_unique_manual_member_and_malformed_archive_guards(self):
        body = archive_fixture((b'html-jp.arc',))
        self.assertEqual(_member(body, b'html-jp.arc'), b'X')
        for names in ((b'other',), (b'html-jp.arc', b'html-jp.arc')):
            with self.assertRaisesRegex(ValueError, 'absent or ambiguous'):
                _member(archive_fixture(names), b'html-jp.arc')
        for offset, value in ((4, 0xFFFFFFFF), (12, 34), (40, 0xFFFFFFFF), (48, 0xFFFFFF)):
            malformed = bytearray(body)
            struct.pack_into('>I', malformed, offset, value)
            with self.assertRaises(ValueError):
                _member(bytes(malformed), b'html-jp.arc')

    def test_cli_error_redacts_private_path_and_emits_no_report(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-marker')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(['private-marker'] * 3)
        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('private-marker', errors.getvalue())


class ForecastSemanticsOriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1] / (
            'private/forecast/snapshots/pre-jwc24-wad-install-20260802-054502/'
            'title-00010002-4841464a/content')
        if not all((cls.root / name).is_file() for name in ('title.tmd', '0000000a.app', '0000000d.app')):
            raise unittest.SkipTest('Pinned private HAFJ manual/application unavailable')

    def test_retained_tmd_manual_nested_archive_and_actual_screenshot_membership(self):
        report = verify_manual_membership((self.root / 'title.tmd').read_bytes(),
                                          (self.root / '0000000a.app').read_bytes())
        self.assertTrue(report['retained_tmd_hash_size_match'])
        self.assertEqual((report['content_index'], report['content_id']), (10, 10))
        self.assertFalse(report['original_assets_or_captions_emitted'])
        self.assertFalse(report['nintendo_signature_or_independent_provenance_verified'])

    def test_actual_float_component_math_and_all_immediate_caller_suffixes(self):
        if importlib.util.find_spec('unicorn') is None:
            self.skipTest('Optional native execution dependency unavailable')
        report = verify_native_semantics((self.root / '0000000d.app').read_bytes())
        self.assertEqual(report['original_float_component_cases'], 84)
        self.assertEqual(report['selectors_and_texture_indices'], {2: [4, 0], 6: [4, 0, 18], 11: [0, 4]})
        self.assertEqual((report['immediate_call_sites'], report['selected_handoff_cases']), (15, 150))
        self.assertTrue(report['sun_first_x_and_y_less_than_cloud_for_selector2'])
        self.assertTrue(report['source_static_inputs_and_guards_unchanged'])
        self.assertFalse(report['paired_single_prolog_full_composition_loop_or_gx_executed'])
        self.assertFalse(report['indirect_call_inventory_or_whole_ui_clock_policy_verified'])
        self.assertFalse(report['native_arrow_temporal_meaning_verified'])


if __name__ == '__main__':
    unittest.main()
