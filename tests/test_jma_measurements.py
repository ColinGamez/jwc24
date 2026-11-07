"""Physical conversion and missingness cases; no requests or private originals."""
from dataclasses import replace
from decimal import localcontext
import unittest

from jwc24.forecast import (
    CURRENT_FORECAST, SHORT_HEADER, CurrentWeatherRecord, build_short_payload,
    decode_lz10, validate_short,
)
from jwc24.jma_measurements import POLICY_ID, ROUNDING, project_observation
from jwc24.jma_weather import JMAError
from tests.test_jma_weather import observations, station_record_fixture


KEY = "20260102133000"


def source(*, temp=(5.2, 0), speed=(1.25, 0), direction=(4, 0)):
    data = station_record_fixture()
    for name, pair in (("temp", temp), ("wind", speed), ("windDirection", direction)):
        if pair is None:
            data[KEY].pop(name, None)
        else:
            data[KEY][name] = list(pair)
    return observations(data)


def project(value=None, **kwargs):
    return project_observation(source() if value is None else value, KEY,
                               rounding=ROUNDING, **kwargs)


class MeasurementProjectionTests(unittest.TestCase):
    def test_physical_units_are_converted_before_independent_rounding(self):
        value = project(source(temp=(0.3, 0), speed=(1.25, 0)))
        self.assertEqual((value.temperature_celsius, value.temperature_fahrenheit), (0, 33))
        self.assertEqual((value.wind_direction, value.wind_speed_metric, value.wind_speed_imperial), (4, 5, 3))
        self.assertEqual(value.policy_id, POLICY_ID)
        self.assertEqual(value.unavailable_reasons, ())

    def test_signed_half_ties_are_explicit_and_decimal_context_independent(self):
        for raw, expected in ((-1.5, -2), (-0.5, -1), (0.5, 1), (1.5, 2)):
            with self.subTest(raw=raw), localcontext() as context:
                context.prec = 2
                value = project(source(temp=(raw, 0)))
                self.assertEqual(value.temperature_celsius, expected)
        # 0.125 m/s is 0.45 km/h and must not be rounded before conversion.
        self.assertEqual(project(source(speed=(0.125, 0))).wind_speed_metric, 0)

    def test_real_zero_and_all_reviewed_direction_values_are_preserved(self):
        for direction in range(17):
            with self.subTest(direction=direction):
                value = project(source(temp=(0, 0), speed=(0, 0), direction=(direction, 0)))
                self.assertEqual((value.temperature_celsius, value.temperature_fahrenheit), (0, 32))
                self.assertEqual((value.wind_direction, value.wind_speed_metric, value.wind_speed_imperial),
                                 (direction, 0, 0))

    def test_calm_does_not_invent_zero_speed_or_north_for_missing_speed(self):
        for speed in (None, (None, 6), (0, 1)):
            with self.subTest(speed=speed):
                value = project(source(speed=speed, direction=(0, 0)))
                self.assertEqual((value.wind_direction, value.wind_speed_metric, value.wind_speed_imperial),
                                 (255, 255, 255))
                self.assertIn("wind:incomplete_pair_suppressed", value.unavailable_reasons)

    def test_absent_missing_and_qualified_temperature_are_distinct_not_zero(self):
        for raw, reason in ((None, "absent"), ((None, 6), "missing"), ((0, 1), "qualified")):
            value = project(source(temp=raw))
            self.assertEqual((value.temperature_celsius, value.temperature_fahrenheit), (-128, -128))
            self.assertIn("temp:" + reason, value.unavailable_reasons)

    def test_every_nonzero_qc_is_unavailable_even_when_jma_client_accepts_qc_one(self):
        for qc in range(1, 8):
            value = project(source(temp=(5, qc), speed=(2, 0), direction=(4, qc)))
            self.assertEqual(value.temperature_celsius, -128)
            self.assertEqual(value.wind_direction, 255)
        selected = source(temp=(5, 1)).records[0].value("temp")
        self.assertTrue(selected.normal_in_jma_client)

    def test_missing_direction_suppresses_complete_wind_pair_without_affecting_temperature(self):
        value = project(source(direction=None))
        self.assertEqual(value.temperature_celsius, 5)
        self.assertEqual((value.wind_direction, value.wind_speed_metric, value.wind_speed_imperial),
                         (255, 255, 255))
        self.assertIn("windDirection:absent", value.unavailable_reasons)

    def test_source_dates_values_qc_station_and_receipt_remain_exact(self):
        original = source(temp=(0.3, 0))
        value = project(original)
        self.assertIs(value.source_record, original.records[0])
        self.assertIs(value.station, original.station)
        self.assertIs(value.source_receipt, original.receipt)
        self.assertEqual(value.source_record.value("temp").raw_value, 0.3)
        self.assertLess(value.source_record.observed_utc, original.receipt.retrieved_end_utc)
        self.assertFalse(hasattr(value, "local_unix_timestamp"))
        self.assertFalse(hasattr(value, "condition_code"))

    def test_explicit_record_selection_never_uses_latest_or_a_default(self):
        original = source()
        second = replace(original.records[0], source_time_key_jst="20260102134000")
        pair = replace(original, records=(*original.records, second))
        self.assertIs(project(pair).source_record, original.records[0])
        for key in ("latest", "", "20260102132000", None):
            with self.assertRaises(JMAError):
                project_observation(pair, key, rounding=ROUNDING)
        with self.assertRaises(JMAError):
            project(replace(original, records=(original.records[0],) * 2))

    def test_rounding_policy_must_be_explicit_and_supported(self):
        with self.assertRaises(TypeError):
            project_observation(source(), KEY)
        for rounding in (None, "bankers", "floor", True):
            with self.assertRaises(JMAError):
                project_observation(source(), KEY, rounding=rounding)

    def test_overflow_never_wraps_clamps_or_turns_into_missing(self):
        # Native missing markers must never be produced by valid-value overflow.
        for temp in (-127.5, 53.1, 128):
            with self.subTest(temp=temp), self.assertRaisesRegex(JMAError, "native range"):
                project(source(temp=(temp, 0)))
        self.assertEqual(project(source(temp=(52.7, 0))).temperature_fahrenheit, 127)
        self.assertEqual(project(source(speed=(70.69, 0))).wind_speed_metric, 254)
        with self.assertRaisesRegex(JMAError, "native range"):
            project(source(speed=(70.7, 0)))
        with self.assertRaisesRegex(JMAError, "negative"):
            project(source(speed=(-0.1, 0)))

    def test_constructed_duplicate_or_wrong_field_contract_rejects(self):
        original = source()
        record = original.records[0]
        with self.assertRaisesRegex(JMAError, "duplicate"):
            project(replace(original, records=(replace(record, values=record.values * 2),)))
        wind = record.value("wind")
        for change in ({"unit": "km/h"}, {"period_seconds": 3600}, {"supported_unit": False},
                       {"raw_value": True}, {"raw_value": float("inf")}, {"qc": True}):
            values = tuple(replace(v, **change) if v is wind else v for v in record.values)
            with self.subTest(change=change), self.assertRaises(JMAError):
                project(replace(original, records=(replace(record, values=values),)))

    def test_projected_fields_pack_into_existing_native_builder_without_new_clocks_or_sky(self):
        value = project(source(speed=(None, 6), direction=(0, 0)))
        # Explicit synthetic identity/clock are supplied by this test, not projection.
        record = CurrentWeatherRecord(1, 10, 2, 1_800_000_000, 0xFFFF,
            value.temperature_celsius, value.temperature_fahrenheit, value.wind_direction,
            value.wind_speed_metric, value.wind_speed_imperial)
        binary = build_short_payload([record], generated_unix_timestamp=1_800_000_000)
        validate_short(binary, signed=False)
        fields = CURRENT_FORECAST.unpack_from(decode_lz10(binary), SHORT_HEADER.size)
        self.assertEqual(fields[5], 0xFFFF)
        self.assertEqual(fields[7:12], (5, 41, 255, 255, 255))


if __name__ == "__main__":
    unittest.main()
