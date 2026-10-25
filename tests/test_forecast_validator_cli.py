from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jwc24.forecast import ForecastLocation, build_location_forecast_payload, build_short_payload
from tools import validate_forecast_payloads as validator


class ForecastValidatorCLITests(unittest.TestCase):
    generated = 1_800_000_000

    def invoke(self, *, now, require_current=True, forecast_minutes=90, short_minutes=63):
        with tempfile.TemporaryDirectory() as directory:
            forecast = Path(directory) / "forecast.bin"
            short = Path(directory) / "short.bin"
            # Validators inspect the signed envelope's native body; this fixture
            # intentionally has no cryptographic signature, just its fixed envelope.
            forecast.write_bytes(bytes(320) + build_location_forecast_payload(
                [ForecastLocation(1, 13, 1, "Test city", "Test region", "Japan", 35.68, 139.76)],
                generated_unix_timestamp=self.generated, validity_minutes=forecast_minutes,
            ))
            short.write_bytes(bytes(320) + build_short_payload(
                [], generated_unix_timestamp=self.generated, validity_minutes=short_minutes,
            ))
            argv = ["validate_forecast_payloads", str(forecast), str(short)]
            if require_current:
                argv.append("--require-current")
            with patch("sys.argv", argv), patch.object(validator.time, "time", return_value=now), patch("builtins.print"):
                return validator.main()

    def test_require_current_rejects_expired_forecast(self):
        with self.assertRaisesRegex(ValueError, "forecast.bin is outside"):
            self.invoke(now=self.generated + 90 * 60, short_minutes=120)

    def test_require_current_rejects_expired_short_at_close_boundary(self):
        with self.assertRaisesRegex(ValueError, "short.bin is outside"):
            self.invoke(now=self.generated + 63 * 60)

    def test_require_current_accepts_open_boundary_and_current_files(self):
        self.assertEqual(self.invoke(now=self.generated), 0)
        self.assertEqual(self.invoke(now=self.generated + 30 * 60), 0)

    def test_require_current_rejects_future_files(self):
        with self.assertRaisesRegex(ValueError, "forecast.bin is outside"):
            self.invoke(now=self.generated - 60)

    def test_default_allows_historical_inspection(self):
        self.assertEqual(self.invoke(now=self.generated + 24 * 3600, require_current=False), 0)


if __name__ == "__main__":
    unittest.main()
