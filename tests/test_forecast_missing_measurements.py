"""Independent byte assertions for native unavailable-value preservation."""
from dataclasses import replace
import struct
import unittest
import zlib

from jwc24.forecast import (
    CURRENT_FORECAST, FORECAST_HEADER, SHORT_HEADER,
    CompactLocationForecast, CurrentWeatherRecord, ForecastDay, ForecastLocation,
    ForecastWeekDay, LocationForecast, build_location_forecast_payload,
    build_short_payload, decode_lz10, encode_lz10, validate_forecast, validate_short,
)


class ForecastMissingMeasurementTests(unittest.TestCase):
    now = 1_800_000_000
    location = ForecastLocation(1, 10, 2, 'Synthetic city', 'Synthetic region', 'Synthetic country', 36, 139)
    day = ForecastDay(0xFFFF, (0xFFFF,) * 4, -128, -128, -128, -128,
                      (0, 25, 100, 255), 255, 12, 7, 0, 0, 0)

    def full(self, *, compact=False, day=None):
        day = self.day if day is None else day
        if compact:
            values = {'short_forecasts': [CompactLocationForecast(1, 10, 2, self.now, day, day)]}
        else:
            week = ForecastWeekDay(0xFFFF, -128, -128, -128, -128, -1)
            values = {'forecasts': [LocationForecast(1, 10, 2, self.now, day, day, (week,) * 7)]}
        return build_location_forecast_payload([self.location], generated_unix_timestamp=self.now, **values)

    def test_long_and_compact_daily_slots_preserve_distinct_values_and_missing_sentinels(self):
        for compact in (False, True):
            compressed = self.full(compact=compact)
            validate_forecast(compressed, signed=False)
            raw = decode_lz10(compressed)
            fields = FORECAST_HEADER.unpack_from(raw)
            start = fields[14 if compact else 12]
            for day in range(2):
                base = start + 16 + day * 28
                self.assertEqual(raw[base:base + 10], b'\xff' * 10)
                self.assertEqual(raw[base + 10:base + 18], b'\x80' * 8)
                self.assertEqual(tuple(raw[base + 18:base + 22]), (0, 25, 100, 255))
                self.assertEqual(raw[base + 22], 255)

    def test_builder_requires_four_explicit_probabilities_and_rejects_invalid_source_numbers(self):
        for values in ((10,) * 3, (10,) * 5):
            with self.assertRaisesRegex(ValueError, 'four explicit'):
                self.full(day=replace(self.day, precipitation=values))
        for value in (-1, 101, 254, 256, True, 10.5, None):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'precipitation'):
                self.full(day=replace(self.day, precipitation=(value, 10, 20, 30)))

    def test_decoded_probabilities_use_native_range_in_every_daily_slot(self):
        for compact in (False, True):
            original = decode_lz10(self.full(compact=compact))
            fields = FORECAST_HEADER.unpack_from(original)
            start = fields[14 if compact else 12]
            for day in range(2):
                for slot in range(4):
                    for value in (101, 254):
                        raw = bytearray(original)
                        raw[start + 16 + day * 28 + 18 + slot] = value
                        struct.pack_into('>I', raw, 8, zlib.crc32(raw[12:]) & 0xFFFFFFFF)
                        with self.subTest(compact=compact, day=day, slot=slot, value=value), \
                                self.assertRaisesRegex(ValueError, 'precipitation'):
                            validate_forecast(encode_lz10(bytes(raw)), signed=False)

    def test_current_temperature_never_wraps_into_a_measurement_or_missing_sentinel(self):
        record = CurrentWeatherRecord(1, 10, 2, self.now, 0xFFFF, -128, -128, 255, 12, 7)
        for value in (-128, -127, 0, 127):
            compressed = build_short_payload([replace(record, temperature_celsius=value,
                                                       temperature_fahrenheit=value)],
                                               generated_unix_timestamp=self.now)
            validate_short(compressed, signed=False)
            raw = decode_lz10(compressed)
            fields = CURRENT_FORECAST.unpack_from(raw, SHORT_HEADER.size)
            self.assertEqual(fields[7:9], (value & 255, value & 255))
        for name in ('temperature_celsius', 'temperature_fahrenheit'):
            for value in (-129, 128, 256, True, 10.5):
                with self.subTest(field=name, value=value), self.assertRaisesRegex(ValueError, 'temperature'):
                    build_short_payload([replace(record, **{name: value})],
                                        generated_unix_timestamp=self.now)

    def test_builders_preserve_missing_wind_direction_and_reject_invalid_directions(self):
        record = CurrentWeatherRecord(1, 10, 2, self.now, 0xFFFF, -128, -128, 255, 12, 7)
        for value in (-1, 17, 254, True, 1.5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'wind direction'):
                build_short_payload([replace(record, wind_direction=value)], generated_unix_timestamp=self.now)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'wind direction'):
                self.full(day=replace(self.day, wind_direction=value))

    def test_native_zero_wind_direction_is_preserved_without_assigning_a_meaning(self):
        record = CurrentWeatherRecord(1, 10, 2, self.now, 0xFFFF, -128, -128, 0, 0, 0)
        compressed = build_short_payload([record], generated_unix_timestamp=self.now)
        validate_short(compressed, signed=False)
        self.assertEqual(CURRENT_FORECAST.unpack_from(decode_lz10(compressed), SHORT_HEADER.size)[9], 0)
        for compact in (False, True):
            compressed = self.full(compact=compact, day=replace(self.day, wind_direction=0,
                                                               wind_speed_metric=0, wind_speed_imperial=0))
            validate_forecast(compressed, signed=False)
            raw = decode_lz10(compressed)
            start = FORECAST_HEADER.unpack_from(raw)[14 if compact else 12]
            self.assertEqual(raw[start + 38], 0)
            self.assertEqual(raw[start + 66], 0)
