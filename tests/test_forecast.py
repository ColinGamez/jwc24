from __future__ import annotations

import struct
import unittest
import zlib
from unittest.mock import patch

from jwc24.forecast import (
    FORECAST_HEADER,
    LOCATION,
    SHORT_HEADER,
    CurrentWeatherRecord,
    ForecastLocation,
    ForecastDay,
    ForecastWeekDay,
    LocationForecast,
    WeatherConditionText,
    WeatherIndexText,
    build_location_forecast_payload,
    build_short_payload,
    decode_lz10,
    encode_lz10,
    sign_compressed_payload,
    validate_forecast,
    validate_short,
)
from jwc24.server import _nintendo_lz10_literal


class ForecastPayloadTests(unittest.TestCase):
    def test_compresses_repetitive_lz10_payload(self) -> None:
        raw = (b"forecast-table-" * 1024) + bytes(range(256))
        compressed = encode_lz10(raw)
        self.assertEqual(decode_lz10(compressed), raw)
        self.assertLess(len(compressed), len(raw) // 4)

    def make_short(self, *, checksum_delta: int = 0) -> bytes:
        raw = bytearray(
            SHORT_HEADER.pack(0, SHORT_HEADER.size, 0, 100, 163, 1, 0, 0, 0, SHORT_HEADER.size)
        )
        checksum = (zlib.crc32(raw[12:]) + checksum_delta) & 0xFFFFFFFF
        struct.pack_into(">I", raw, 8, checksum)
        return bytes(320) + _nintendo_lz10_literal(bytes(raw))

    def test_accepts_empty_signed_short_payload(self) -> None:
        summary = validate_short(self.make_short())
        self.assertEqual(summary.country_code, 1)
        self.assertEqual(summary.language_code, 0)
        self.assertEqual(summary.current_forecasts, 0)

    def test_rejects_bad_crc(self) -> None:
        with self.assertRaisesRegex(ValueError, "CRC32 mismatch"):
            validate_short(self.make_short(checksum_delta=1))

    def test_builds_native_short_payload(self) -> None:
        compressed = build_short_payload(
            [
                CurrentWeatherRecord(
                    1, 10, 2, 1_800_000_000, 0x1234, -2, 28, 4, 12, 7
                )
            ],
            generated_unix_timestamp=1_800_000_000,
        )
        summary = validate_short(compressed, signed=False)
        self.assertEqual(summary.current_forecasts, 1)
        self.assertEqual(summary.country_code, 1)

    def test_builds_generic_location_catalog(self) -> None:
        compressed = build_location_forecast_payload(
            [
                ForecastLocation(1, 1, 1, "札幌市", "北海道", "日本", 43.06, 141.35),
                ForecastLocation(1, 10, 2, "高崎市", "群馬県", "日本", 36.32, 139.00),
                ForecastLocation(1, 13, 1, "東京都", "東京都", "日本", 35.68, 139.76),
            ],
            generated_unix_timestamp=1_800_000_000,
        )
        summary = validate_forecast(compressed, signed=False)
        self.assertEqual(summary.locations, 3)
        self.assertEqual(
            [record.city for record in summary.location_records],
            ["札幌市", "高崎市", "東京都"],
        )

    def test_builds_complete_location_forecast_row(self) -> None:
        location = ForecastLocation(1, 10, 2, "高崎市", "群馬県", "日本", 36.32, 139.0)
        day = ForecastDay(
            0x1001,
            (0x1001, 0x1001, 0x1002, 0x1002),
            31,
            23,
            88,
            73,
            (10, 20, 30, 20),
            4,
            12,
            7,
            5,
            4,
            1,
        )
        week_day = ForecastWeekDay(0x1001, 31, 23, 88, 73, 20)
        compressed = build_location_forecast_payload(
            [location],
            forecasts=[LocationForecast(1, 10, 2, 1_800_000_000, day, day, (week_day,) * 7)],
            condition_texts=[WeatherConditionText(0x1001, 1, "晴れ")],
            uv_texts=[WeatherIndexText(5, "やや強い")],
            laundry_texts=[WeatherIndexText(4, "乾きよし")],
            pollen_texts=[WeatherIndexText(1, "少ない")],
            generated_unix_timestamp=1_800_000_000,
        )
        summary = validate_forecast(compressed, signed=False)
        self.assertEqual(summary.long_forecasts, 1)
        self.assertEqual(summary.locations, 1)
        self.assertEqual(summary.weather_conditions, 1)
        self.assertEqual(summary.uv_indices, 1)
        self.assertEqual(summary.laundry_indices, 1)
        self.assertEqual(summary.pollen_counts, 1)

    @patch("jwc24.forecast.subprocess.run")
    def test_signs_stock_envelope(self, run) -> None:
        run.return_value.stdout = b"S" * 256
        compressed = self.make_short()[320:]
        signed = sign_compressed_payload(compressed, "private.pem")
        self.assertEqual(signed[:64], bytes(64))
        self.assertEqual(signed[64:320], b"S" * 256)
        self.assertEqual(signed[320:], compressed)
        self.assertEqual(run.call_args.kwargs["input"], compressed)

    def test_parses_japanese_location_table(self) -> None:
        city = "高崎市".encode("utf-16-be") + b"\0\0"
        region = "群馬県".encode("utf-16-be") + b"\0\0"
        country = "日本".encode("utf-16-be") + b"\0\0"
        location_offset = FORECAST_HEADER.size
        city_offset = location_offset + LOCATION.size
        region_offset = city_offset + len(city)
        country_offset = region_offset + len(region)
        location = LOCATION.pack(
            1,
            10,
            2,
            city_offset,
            region_offset,
            country_offset,
            round(36.32 * 8192 / 45),
            round(139.00 * 8192 / 45),
            1,
            2,
            0,
        )
        body = location + city + region + country
        size = FORECAST_HEADER.size + len(body)
        table_fields = [0] + [0, 0] * 6 + [1, location_offset]
        header = bytearray(
            FORECAST_HEADER.pack(0, size, 0, 100, 190, 1, 0, 0, 1, 0, *table_fields)
        )
        raw = header + body
        struct.pack_into(">I", raw, 8, zlib.crc32(raw[12:]) & 0xFFFFFFFF)
        payload = bytes(320) + _nintendo_lz10_literal(bytes(raw))
        summary = validate_forecast(payload)
        self.assertEqual(summary.locations, 1)
        self.assertEqual(summary.location_records[0].city, "高崎市")
        self.assertEqual(summary.location_records[0].region, "群馬県")
        self.assertAlmostEqual(summary.location_records[0].latitude, 36.32, places=2)


if __name__ == "__main__":
    unittest.main()
