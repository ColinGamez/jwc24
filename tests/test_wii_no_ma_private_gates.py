"""Fixture-gate behavior without private Wii no Ma data or native claims."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.wii_no_ma_private_fixtures import PRIVATE_INPUTS, requires_private_wii_no_ma


class WiiNoMaPrivateGateTests(unittest.TestCase):
    def test_missing_primary_input_skips_with_a_specific_nonsecret_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            primary = Path(directory) / 'private-marker.json'
            with patch.dict(PRIVATE_INPUTS, {'test': ('synthetic primary catalog', primary, None)}):
                @requires_private_wii_no_ma('test')
                def integration():
                    self.fail('A missing primary fixture must not execute the integration')
                with self.assertRaisesRegex(unittest.SkipTest, '^Private Wii no Ma synthetic primary catalog unavailable$'):
                    integration()

    def test_existing_fixture_pins_its_environment_and_restores_the_previous_value(self):
        with tempfile.TemporaryDirectory() as directory:
            primary = Path(directory) / 'catalog.json'
            primary.write_text('{}', encoding='utf-8')
            with patch.dict(PRIVATE_INPUTS, {'test': ('synthetic catalog', primary, 'JWC24_TEST_FIXTURE')}), \
                 patch.dict(os.environ, {'JWC24_TEST_FIXTURE': 'previous'}):
                @requires_private_wii_no_ma('test')
                def integration():
                    self.assertEqual(os.environ['JWC24_TEST_FIXTURE'], str(primary.resolve()))
                    return 'checked'
                self.assertEqual(integration(), 'checked')
                self.assertEqual(os.environ['JWC24_TEST_FIXTURE'], 'previous')

    def test_present_but_corrupt_fixture_and_missing_asserted_asset_are_not_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            primary = Path(directory) / 'catalog.json'
            primary.write_bytes(b'corrupt-fixture')
            with patch.dict(PRIVATE_INPUTS, {'test': ('synthetic catalog', primary, None)}):
                @requires_private_wii_no_ma('test')
                def corrupt_integration():
                    raise ValueError('Actual parser rejected present fixture')
                @requires_private_wii_no_ma('test')
                def absent_asset():
                    return (primary.parent / 'required-secondary.mii').read_bytes()
                with self.assertRaises(ValueError):
                    corrupt_integration()
                with self.assertRaises(FileNotFoundError):
                    absent_asset()

    def test_wrong_file_type_and_unreadable_input_are_failures_not_missing_fixture_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            primary = Path(directory)
            with patch.dict(PRIVATE_INPUTS, {'test': ('synthetic catalog', primary, None)}):
                @requires_private_wii_no_ma('test')
                def integration():
                    self.fail('An invalid primary input must not run integration code')
                with self.assertRaisesRegex(AssertionError, 'not a regular file'):
                    integration()
                with patch.object(Path, 'stat', side_effect=PermissionError('unreadable')):
                    with self.assertRaises(PermissionError):
                        integration()


if __name__ == '__main__':
    unittest.main()
