from __future__ import annotations

import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from jwc24.forecast import (
    CurrentWeatherRecord, ForecastLocation, WeatherConditionText,
    build_location_forecast_payload, build_short_payload, encode_lz10,
    sign_compressed_payload,
)
from jwc24.forecast_bundle import validate_forecast_bundle
from tools import validate_forecast_bundle as cli


class ForecastBundleTests(unittest.TestCase):
    generated = 1_800_000_000

    def pair(self, *, key=(1, 10, 2), condition=0x1001, duplicates=False,
             conflict=False, short_time=None, observation_time=None,
             short_country=1, short_language=0):
        full = build_location_forecast_payload(
            [ForecastLocation(1, 10, 2, 'Test city', 'Test region', 'Test country', 36, 139),
             ForecastLocation(1, 13, 1, 'Second city', 'Second region', 'Test country', 35, 139)],
            condition_texts=[WeatherConditionText(0x1001, 1, 'Test condition')],
            generated_unix_timestamp=self.generated,
        )
        record = CurrentWeatherRecord(
            *key, observation_time if observation_time is not None else self.generated,
            condition, 20, 68, 4, 12, 7,
        )
        short = build_short_payload(
            [record, replace(record, temperature_celsius=21)] if conflict else [record] * (2 if duplicates else 1),
            generated_unix_timestamp=short_time if short_time is not None else self.generated,
            country_code=short_country, language_code=short_language,
        )
        return bytes(320) + full, bytes(320) + short

    def test_subset_of_catalog_is_valid_but_never_claims_authenticity(self):
        result = validate_forecast_bundle(*self.pair())
        self.assertEqual((result.forecast.locations, result.short.current_forecasts), (2, 1))
        self.assertFalse(result.signatures_verified)
        self.assertFalse(result.current_windows_checked)
        metadata = result.metadata()
        self.assertFalse(metadata['installed_client_trust_checked'])
        self.assertFalse(metadata['native_delivery_or_rendering_checked'])
        self.assertNotIn('Test city', json.dumps(metadata))

    def test_rejects_current_record_whose_location_is_absent(self):
        with self.assertRaisesRegex(ValueError, 'missing catalog location'):
            validate_forecast_bundle(*self.pair(key=(1, 47, 999)))

    def test_retains_identical_duplicates_and_rejects_conflicting_current_rows(self):
        result = validate_forecast_bundle(*self.pair(duplicates=True))
        self.assertEqual(result.short.current_forecasts, 2)
        self.assertEqual(result.repeated_current_keys, 1)
        with self.assertRaisesRegex(ValueError, 'conflicting duplicate location'):
            validate_forecast_bundle(*self.pair(conflict=True))

    def test_rejects_current_condition_missing_from_full_dictionary(self):
        with self.assertRaisesRegex(ValueError, 'missing weather condition'):
            validate_forecast_bundle(*self.pair(condition=0x1002))

    def test_missing_condition_sentinel_is_preserved(self):
        self.assertEqual(validate_forecast_bundle(*self.pair(condition=0xFFFF)).short.current_forecasts, 1)

    def test_rejects_mismatched_country_or_language(self):
        for args in ({'short_country': 2}, {'short_language': 1}):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, 'locale'):
                validate_forecast_bundle(*self.pair(**args))

    def test_rejects_disjoint_and_touching_validity_windows(self):
        for shift in (90 * 60, 100 * 60):
            with self.subTest(shift=shift), self.assertRaisesRegex(ValueError, 'do not overlap'):
                validate_forecast_bundle(*self.pair(short_time=self.generated + shift))

    def test_current_open_and_close_boundaries(self):
        self.assertTrue(validate_forecast_bundle(*self.pair(), current_unix_timestamp=self.generated).current_windows_checked)
        for shift in (-60, 63 * 60):
            with self.subTest(shift=shift), self.assertRaisesRegex(ValueError, 'outside its current'):
                validate_forecast_bundle(*self.pair(), current_unix_timestamp=self.generated + shift)

    def test_current_envelope_does_not_establish_observation_freshness(self):
        # Provider-specific observation age policy is deliberately separate.
        result = validate_forecast_bundle(
            *self.pair(observation_time=self.generated - 365 * 24 * 3600),
            current_unix_timestamp=self.generated,
        )
        metadata = result.metadata()
        self.assertTrue(metadata['current_windows_checked'])
        self.assertFalse(metadata['observation_timestamps_checked'])

    def test_tiny_native_headers_raise_value_error(self):
        tiny = bytes(320) + encode_lz10(b'\0')
        full, short = self.pair()
        for pair in ((tiny, short), (full, tiny)):
            with self.subTest(pair=pair), self.assertRaisesRegex(ValueError, 'truncated native header'):
                validate_forecast_bundle(*pair)

    def test_cli_reports_scope_and_current_check_without_profile_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            full_path, short_path = Path(directory) / 'forecast.bin', Path(directory) / 'short.bin'
            full, short = self.pair()
            full_path.write_bytes(full)
            short_path.write_bytes(short)
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch.object(cli.time, 'time', return_value=self.generated):
                self.assertEqual(cli.main([str(full_path), str(short_path), '--require-current']), 0)
            report = json.loads(output.getvalue())
            self.assertTrue(report['current_windows_checked'])
            self.assertFalse(report['signatures_verified_against_supplied_key'])
            self.assertEqual(full_path.read_bytes(), full)
            self.assertEqual(short_path.read_bytes(), short)
            self.assertEqual(sorted(path.name for path in Path(directory).iterdir()), ['forecast.bin', 'short.bin'])


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL not installed')
class ForecastBundleSignatureTests(unittest.TestCase):
    generated = ForecastBundleTests.generated
    pair = ForecastBundleTests.pair

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='jwc24-test-forecast-')
        cls.private_key = Path(cls.directory.name) / 'private.pem'
        cls.public_key = Path(cls.directory.name) / 'public.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048',
                        '-out', str(cls.private_key)], capture_output=True, check=True, timeout=30)
        subprocess.run(['openssl', 'pkey', '-in', str(cls.private_key), '-pubout', '-out', str(cls.public_key)],
                       capture_output=True, check=True, timeout=15)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def signed_pair(self):
        return tuple(sign_compressed_payload(payload[320:], self.private_key) for payload in self.pair())

    def test_supplied_key_authenticates_both_generated_envelopes(self):
        result = validate_forecast_bundle(*self.signed_pair(), public_key=self.public_key)
        self.assertTrue(result.signatures_verified)

    def test_signature_corruption_in_either_file_is_rejected(self):
        pair = self.signed_pair()
        for index in (0, 1):
            changed = list(pair)
            data = bytearray(changed[index])
            data[80] ^= 1
            changed[index] = bytes(data)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'does not verify'):
                validate_forecast_bundle(*changed, public_key=self.public_key)

    def test_unavailable_verifier_has_fixed_error(self):
        pair = self.signed_pair()
        with patch('jwc24.forecast_bundle.subprocess.run', side_effect=FileNotFoundError('private path')):
            with self.assertRaisesRegex(ValueError, '^Forecast signature verification could not run$'):
                validate_forecast_bundle(*pair, public_key=self.public_key)


if __name__ == '__main__':
    unittest.main()
