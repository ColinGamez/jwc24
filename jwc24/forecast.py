"""Parsers and validators for native Wii Forecast Channel payloads."""

from __future__ import annotations

import struct
import subprocess
import zlib
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path


SIGNATURE_ENVELOPE_SIZE = 64 + 256
FORECAST_HEADER = struct.Struct(">5I B3x 4B 15I")
SHORT_HEADER = struct.Struct(">5I B3x BB2x 2I")
CURRENT_FORECAST = struct.Struct(">BBHIIHBBBBBBHH")
LONG_FORECAST = struct.Struct(">BBHIII5H8b10B5H8b10B" + "H5bB" * 7)
SHORT_FORECAST = struct.Struct(">BBHIII5H8b10B5H8b10B")
WEATHER_CONDITION = struct.Struct(">HHI")
INDEX_TEXT = struct.Struct(">B3xI")
LOCATION = struct.Struct(">BBHIIIhhBBH")
WII_EPOCH_UNIX = 946684800


@dataclass(frozen=True)
class CurrentWeatherRecord:
    country_code: int
    region_code: int
    location_code: int
    local_unix_timestamp: int
    condition_code: int
    temperature_celsius: int
    temperature_fahrenheit: int
    wind_direction: int
    wind_speed_metric: int
    wind_speed_imperial: int


@dataclass(frozen=True)
class ForecastLocation:
    country_code: int
    region_code: int
    location_code: int
    city: str
    region: str
    country: str
    latitude: float
    longitude: float
    zoom_near: int = 1
    zoom_far: int = 2


@dataclass(frozen=True)
class ForecastDay:
    condition_code: int
    six_hour_condition_codes: tuple[int, int, int, int]
    high_celsius: int
    low_celsius: int
    high_fahrenheit: int
    low_fahrenheit: int
    precipitation: tuple[int, int, int, int]
    wind_direction: int
    wind_speed_metric: int
    wind_speed_imperial: int
    uv_index: int
    laundry_index: int
    pollen_count: int


@dataclass(frozen=True)
class ForecastWeekDay:
    condition_code: int
    high_celsius: int
    low_celsius: int
    high_fahrenheit: int
    low_fahrenheit: int
    precipitation: int


@dataclass(frozen=True)
class LocationForecast:
    country_code: int
    region_code: int
    location_code: int
    local_unix_timestamp: int
    today: ForecastDay
    tomorrow: ForecastDay
    week: tuple[
        ForecastWeekDay,
        ForecastWeekDay,
        ForecastWeekDay,
        ForecastWeekDay,
        ForecastWeekDay,
        ForecastWeekDay,
        ForecastWeekDay,
    ]


@dataclass(frozen=True)
class CompactLocationForecast:
    country_code: int
    region_code: int
    location_code: int
    local_unix_timestamp: int
    today: ForecastDay
    tomorrow: ForecastDay


@dataclass(frozen=True)
class WeatherConditionText:
    code_primary: int
    code_secondary: int
    text: str


@dataclass(frozen=True)
class WeatherIndexText:
    code: int
    text: str


def unix_to_wii_minutes(timestamp: int) -> int:
    if timestamp < WII_EPOCH_UNIX:
        raise ValueError("timestamp predates the Wii weather epoch")
    return (timestamp - WII_EPOCH_UNIX) // 60


def encode_lz10_literal(payload: bytes) -> bytes:
    if len(payload) >= 1 << 24:
        raise ValueError("payload is too large for the LZ10 header")
    output = bytearray(b"\x10" + len(payload).to_bytes(3, "little"))
    for position in range(0, len(payload), 8):
        output.append(0)
        output.extend(payload[position : position + 8])
    return bytes(output)


def encode_lz10(payload: bytes) -> bytes:
    """Greedily compress bytes using Nintendo's 4 KiB-window LZ10 format."""
    if len(payload) >= 1 << 24:
        raise ValueError("payload is too large for the LZ10 header")
    output = bytearray(b"\x10" + len(payload).to_bytes(3, "little"))
    positions: dict[bytes, deque[int]] = defaultdict(deque)
    cursor = 0

    def remember(position: int) -> None:
        if position + 3 > len(payload):
            return
        key = payload[position : position + 3]
        bucket = positions[key]
        bucket.append(position)
        while bucket and position - bucket[0] > 4096:
            bucket.popleft()

    while cursor < len(payload):
        flag_offset = len(output)
        output.append(0)
        flags = 0
        for bit in range(8):
            if cursor >= len(payload):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(payload):
                bucket = positions.get(payload[cursor : cursor + 3], ())
                for candidate in reversed(bucket):
                    distance = cursor - candidate
                    if distance > 4096:
                        break
                    length = 3
                    maximum = min(18, len(payload) - cursor)
                    while (
                        length < maximum
                        and payload[candidate + length] == payload[cursor + length]
                    ):
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                        if length == maximum:
                            break
            if best_length >= 3:
                flags |= 1 << (7 - bit)
                pair = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend(pair.to_bytes(2, "big"))
                start = cursor
                cursor += best_length
                for position in range(start, cursor):
                    remember(position)
            else:
                output.append(payload[cursor])
                remember(cursor)
                cursor += 1
        output[flag_offset] = flags
    return bytes(output)


def build_short_payload(
    records: list[CurrentWeatherRecord] | tuple[CurrentWeatherRecord, ...],
    *,
    generated_unix_timestamp: int,
    country_code: int = 1,
    language_code: int = 0,
    validity_minutes: int = 63,
) -> bytes:
    """Build an unsigned, LZ10-compressed native short.bin body."""
    opened = unix_to_wii_minutes(generated_unix_timestamp)
    rows = bytearray()
    for record in records:
        rows.extend(
            CURRENT_FORECAST.pack(
                record.country_code,
                record.region_code,
                record.location_code,
                unix_to_wii_minutes(record.local_unix_timestamp),
                opened,
                record.condition_code,
                0,
                record.temperature_celsius & 0xFF,
                record.temperature_fahrenheit & 0xFF,
                record.wind_direction,
                record.wind_speed_metric,
                record.wind_speed_imperial,
                0,
                0xFFFF,
            )
        )
    size = SHORT_HEADER.size + len(rows)
    raw = bytearray(
        SHORT_HEADER.pack(
            0,
            size,
            0,
            opened,
            opened + validity_minutes,
            country_code,
            language_code,
            0,
            len(records),
            SHORT_HEADER.size,
        )
    )
    raw.extend(rows)
    struct.pack_into(">I", raw, 8, zlib.crc32(raw[12:]) & 0xFFFFFFFF)
    return encode_lz10(bytes(raw))


def _encode_coordinate(value: float, *, latitude: bool) -> int:
    limit = 90 if latitude else 180
    if not -limit <= value <= limit:
        raise ValueError(f"coordinate outside {-limit}..{limit}: {value}")
    encoded = round(value * 8192 / 45)
    return max(-32768, min(32767, encoded))


def build_location_forecast_payload(
    locations: list[ForecastLocation] | tuple[ForecastLocation, ...],
    *,
    forecasts: list[LocationForecast] | tuple[LocationForecast, ...] = (),
    short_forecasts: list[CompactLocationForecast] | tuple[CompactLocationForecast, ...] = (),
    condition_texts: list[WeatherConditionText] | tuple[WeatherConditionText, ...] = (),
    uv_texts: list[WeatherIndexText] | tuple[WeatherIndexText, ...] = (),
    laundry_texts: list[WeatherIndexText] | tuple[WeatherIndexText, ...] = (),
    pollen_texts: list[WeatherIndexText] | tuple[WeatherIndexText, ...] = (),
    generated_unix_timestamp: int,
    country_code: int = 1,
    language_code: int = 0,
    temperature_flag: int = 0,
    validity_minutes: int = 90,
) -> bytes:
    """Build a native forecast.bin containing an arbitrary location catalog."""
    if not locations:
        raise ValueError("at least one location is required")
    keys = [(item.country_code, item.region_code, item.location_code) for item in locations]
    if len(keys) != len(set(keys)):
        raise ValueError("location keys must be unique")

    text_start = FORECAST_HEADER.size + len(locations) * LOCATION.size
    text = bytearray()
    text_offsets: dict[str, int] = {}

    def add_text(value: str, *, optional: bool = False) -> int:
        if not value:
            if optional:
                return 0
            raise ValueError("city names cannot be empty")
        if value in text_offsets:
            return text_offsets[value]
        offset = text_start + len(text)
        text.extend(value.encode("utf-16-be") + b"\0\0")
        while len(text) % 4:
            text.append(0)
        text_offsets[value] = offset
        return offset

    rows = bytearray()
    for item in locations:
        rows.extend(
            LOCATION.pack(
                item.country_code,
                item.region_code,
                item.location_code,
                add_text(item.city),
                add_text(item.region, optional=True),
                add_text(item.country, optional=True),
                _encode_coordinate(item.latitude, latitude=True),
                _encode_coordinate(item.longitude, latitude=False),
                item.zoom_near,
                item.zoom_far,
                0,
            )
        )

    opened = unix_to_wii_minutes(generated_unix_timestamp)
    location_keys = set(keys)
    forecast_keys = [
        (item.country_code, item.region_code, item.location_code) for item in forecasts
    ]
    # Nintendo's Japanese catalog intentionally contains two duplicated long
    # forecast keys after its location-name deduplication pass. Preserve that
    # accepted legacy layout; location rows themselves must remain unique.
    missing = set(forecast_keys) - location_keys
    if missing:
        raise ValueError(f"forecast records reference missing locations: {sorted(missing)}")
    short_keys = [
        (item.country_code, item.region_code, item.location_code)
        for item in short_forecasts
    ]
    if len(short_keys) != len(set(short_keys)):
        raise ValueError("short forecast keys must be unique")
    missing = set(short_keys) - location_keys
    if missing:
        raise ValueError(f"short forecasts reference missing locations: {sorted(missing)}")

    generated = unix_to_wii_minutes(generated_unix_timestamp)
    long_rows = bytearray()

    def day_values(day: ForecastDay) -> list[int]:
        return [
            day.condition_code,
            *day.six_hour_condition_codes,
            day.high_celsius,
            -128,
            day.low_celsius,
            -128,
            day.high_fahrenheit,
            -128,
            day.low_fahrenheit,
            -128,
            *day.precipitation,
            day.wind_direction,
            day.wind_speed_metric,
            day.wind_speed_imperial,
            day.uv_index,
            day.laundry_index,
            day.pollen_count,
        ]

    for item in forecasts:
        if len(item.week) != 7:
            raise ValueError("each location forecast must contain exactly seven week days")
        values = [
            item.country_code,
            item.region_code,
            item.location_code,
            unix_to_wii_minutes(item.local_unix_timestamp),
            generated,
            0,
            *day_values(item.today),
            *day_values(item.tomorrow),
        ]
        for day in item.week:
            values.extend(
                [
                    day.condition_code,
                    day.high_celsius,
                    day.low_celsius,
                    day.high_fahrenheit,
                    day.low_fahrenheit,
                    day.precipitation,
                    0,
                ]
            )
        long_rows.extend(LONG_FORECAST.pack(*values))

    short_rows = bytearray()
    for item in short_forecasts:
        today = day_values(item.today)
        tomorrow = day_values(item.tomorrow)
        values = [
            item.country_code,
            item.region_code,
            item.location_code,
            unix_to_wii_minutes(item.local_unix_timestamp),
            generated,
            0,
            *today[:-3],
            0xFF,
            0xFF,
            0xFF,
            *tomorrow,
        ]
        short_rows.extend(SHORT_FORECAST.pack(*values))

    base_size = (
        FORECAST_HEADER.size
        + len(rows)
        + len(text)
        + len(long_rows)
        + len(short_rows)
    )
    long_offset = FORECAST_HEADER.size + len(rows) + len(text) if forecasts else 0
    short_offset = long_offset + len(long_rows) if short_forecasts else 0

    def text_section(
        records: list[WeatherConditionText] | tuple[WeatherConditionText, ...]
        | list[WeatherIndexText] | tuple[WeatherIndexText, ...],
        item_struct: struct.Struct,
        start: int,
    ) -> bytes:
        table = bytearray()
        strings = bytearray()
        string_start = start + len(records) * item_struct.size
        for item in records:
            if not item.text:
                raise ValueError("weather lookup text cannot be empty")
            offset = string_start + len(strings)
            if isinstance(item, WeatherConditionText):
                table.extend(item_struct.pack(item.code_primary, item.code_secondary, offset))
            else:
                table.extend(item_struct.pack(item.code, offset))
            strings.extend(item.text.encode("utf-16-be") + b"\0\0")
            while len(strings) % 4:
                strings.append(0)
        return bytes(table + strings)

    lookup_data = bytearray()
    lookup_offsets: dict[str, int] = {}
    # Match the stock generator's physical section order. Header offsets still
    # make each section independently addressable.
    lookup_specs = (
        ("laundry", laundry_texts, INDEX_TEXT),
        ("condition", condition_texts, WEATHER_CONDITION),
        ("uv", uv_texts, INDEX_TEXT),
        ("pollen", pollen_texts, INDEX_TEXT),
    )
    for name, records, item_struct in lookup_specs:
        offset = base_size + len(lookup_data) if records else 0
        lookup_offsets[name] = offset
        lookup_data.extend(text_section(records, item_struct, offset))

    size = base_size + len(lookup_data)
    table_fields = [
        0,
        len(forecasts),
        long_offset,
        len(short_forecasts),
        short_offset,
        len(condition_texts),
        lookup_offsets["condition"],
        len(uv_texts),
        lookup_offsets["uv"],
        len(laundry_texts),
        lookup_offsets["laundry"],
        len(pollen_texts),
        lookup_offsets["pollen"],
        len(locations),
        FORECAST_HEADER.size,
    ]
    raw = bytearray(
        FORECAST_HEADER.pack(
            0,
            size,
            0,
            opened,
            opened + validity_minutes,
            country_code,
            language_code,
            temperature_flag,
            1,
            0,
            *table_fields,
        )
    )
    raw.extend(rows)
    raw.extend(text)
    raw.extend(long_rows)
    raw.extend(short_rows)
    raw.extend(lookup_data)
    struct.pack_into(">I", raw, 8, zlib.crc32(raw[12:]) & 0xFFFFFFFF)
    return encode_lz10(bytes(raw))


def sign_compressed_payload(compressed: bytes, private_key: str | Path) -> bytes:
    """Wrap compressed Forecast data in the stock SHA-1/RSA envelope."""
    result = subprocess.run(
        ["openssl", "dgst", "-sha1", "-sign", str(private_key)],
        input=compressed,
        capture_output=True,
        check=True,
    )
    signature = result.stdout
    if len(signature) != 256:
        raise ValueError(
            f"expected a 256-byte RSA signature, received {len(signature)} bytes"
        )
    return bytes(64) + signature + compressed


def decode_lz10(payload: bytes) -> bytes:
    if len(payload) < 4 or payload[0] != 0x10:
        raise ValueError("payload is not Nintendo LZ10")
    expected = int.from_bytes(payload[1:4], "little")
    source = 4
    output = bytearray()
    while len(output) < expected:
        if source >= len(payload):
            raise ValueError("truncated LZ10 flag group")
        flags = payload[source]
        source += 1
        for bit in range(7, -1, -1):
            if len(output) >= expected:
                break
            if flags & (1 << bit):
                if source + 2 > len(payload):
                    raise ValueError("truncated LZ10 back-reference")
                pair = int.from_bytes(payload[source : source + 2], "big")
                source += 2
                length = (pair >> 12) + 3
                distance = (pair & 0xFFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ10 back-reference")
                for _ in range(length):
                    output.append(output[-distance])
                    if len(output) == expected:
                        break
            else:
                if source >= len(payload):
                    raise ValueError("truncated LZ10 literal")
                output.append(payload[source])
                source += 1
    return bytes(output)


def unwrap_signed_payload(payload: bytes) -> bytes:
    if len(payload) <= SIGNATURE_ENVELOPE_SIZE:
        raise ValueError("Forecast payload is shorter than its signature envelope")
    compressed = payload[SIGNATURE_ENVELOPE_SIZE:]
    return decode_lz10(compressed)


def _validate_common(raw: bytes, header_size: int) -> tuple[int, int, int, int, int]:
    if len(raw) < header_size:
        raise ValueError("Forecast payload header is truncated")
    version, file_size, checksum, opened, closed = struct.unpack_from(">5I", raw)
    if version != 0:
        raise ValueError(f"unsupported Forecast payload version {version}")
    if file_size != len(raw):
        raise ValueError(f"file size mismatch: header={file_size}, actual={len(raw)}")
    actual_checksum = zlib.crc32(raw[12:]) & 0xFFFFFFFF
    if checksum != actual_checksum:
        raise ValueError(
            f"CRC32 mismatch: header={checksum:08x}, actual={actual_checksum:08x}"
        )
    if closed < opened:
        raise ValueError("payload close timestamp precedes its open timestamp")
    return version, file_size, checksum, opened, closed


@dataclass(frozen=True)
class ForecastSummary:
    file_size: int
    open_timestamp: int
    close_timestamp: int
    country_code: int
    language_code: int
    temperature_flag: int
    long_forecasts: int
    short_forecasts: int
    weather_conditions: int
    uv_indices: int
    laundry_indices: int
    pollen_counts: int
    locations: int
    location_records: tuple["LocationRecord", ...]


@dataclass(frozen=True)
class LocationRecord:
    country_code: int
    region_code: int
    location_code: int
    city: str
    region: str
    country: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class ShortSummary:
    file_size: int
    open_timestamp: int
    close_timestamp: int
    country_code: int
    language_code: int
    current_forecasts: int


def _check_table(raw: bytes, name: str, count: int, offset: int, item_size: int) -> None:
    if count == 0:
        return
    if offset < FORECAST_HEADER.size or offset + count * item_size > len(raw):
        raise ValueError(f"{name} table is outside the payload")


def _read_utf16be(raw: bytes, offset: int, field: str, *, optional: bool = False) -> str:
    if optional and offset == 0:
        return ""
    if offset < FORECAST_HEADER.size or offset >= len(raw) or offset & 1:
        raise ValueError(f"{field} text offset is invalid: {offset}")
    end = offset
    while end + 2 <= len(raw) and raw[end : end + 2] != b"\x00\x00":
        end += 2
    if end + 2 > len(raw):
        raise ValueError(f"{field} text is not null terminated")
    try:
        return raw[offset:end].decode("utf-16-be")
    except UnicodeDecodeError as error:
        raise ValueError(f"{field} text is not valid UTF-16BE") from error


def _table_keys(
    raw: bytes,
    count: int,
    offset: int,
    item_size: int,
    *,
    allow_duplicates: bool = False,
) -> set[tuple[int, int, int]]:
    keys: set[tuple[int, int, int]] = set()
    for position in range(count):
        key = struct.unpack_from(">BBH", raw, offset + position * item_size)
        if key in keys and not allow_duplicates:
            raise ValueError(f"duplicate location key {key} in forecast table")
        keys.add(key)
    return keys


def _validate_wind_direction(value: int, label: str) -> None:
    if value not in range(1, 17) and value != 0xFF:
        raise ValueError(f"{label} has invalid wind direction {value}")


def validate_forecast(payload: bytes, *, signed: bool = True) -> ForecastSummary:
    raw = unwrap_signed_payload(payload) if signed else decode_lz10(payload)
    fields = FORECAST_HEADER.unpack_from(raw)
    _version, size, _crc, opened, closed = _validate_common(raw, FORECAST_HEADER.size)
    country, language, temperature = fields[5], fields[6], fields[7]
    table_fields = fields[10:]
    names = ("long forecast", "short forecast", "weather condition", "UV", "laundry", "pollen", "location")
    sizes = (
        LONG_FORECAST.size,
        SHORT_FORECAST.size,
        WEATHER_CONDITION.size,
        INDEX_TEXT.size,
        INDEX_TEXT.size,
        INDEX_TEXT.size,
        LOCATION.size,
    )
    counts = []
    offsets = []
    for position, (name, item_size) in enumerate(zip(names, sizes)):
        count = table_fields[1 + position * 2]
        offset = table_fields[2 + position * 2]
        _check_table(raw, name, count, offset, item_size)
        counts.append(count)
        offsets.append(offset)

    long_keys = _table_keys(
        raw, counts[0], offsets[0], LONG_FORECAST.size, allow_duplicates=True
    )
    short_keys = _table_keys(raw, counts[1], offsets[1], SHORT_FORECAST.size)
    for position in range(counts[0]):
        values = LONG_FORECAST.unpack_from(
            raw, offsets[0] + position * LONG_FORECAST.size
        )
        _validate_wind_direction(values[23], f"long forecast {position} today")
        _validate_wind_direction(values[46], f"long forecast {position} tomorrow")
    for position in range(counts[1]):
        values = SHORT_FORECAST.unpack_from(
            raw, offsets[1] + position * SHORT_FORECAST.size
        )
        if values[26:29] != (0xFF, 0xFF, 0xFF):
            raise ValueError(
                f"short forecast {position} has invalid reserved bytes"
            )
        _validate_wind_direction(values[23], f"short forecast {position} today")
        _validate_wind_direction(values[46], f"short forecast {position} tomorrow")
    records = []
    location_keys: set[tuple[int, int, int]] = set()
    for position in range(counts[6]):
        values = LOCATION.unpack_from(raw, offsets[6] + position * LOCATION.size)
        key = values[:3]
        if key in location_keys:
            raise ValueError(f"duplicate location key {key} in location table")
        location_keys.add(key)
        latitude_raw, longitude_raw = values[6], values[7]
        latitude = latitude_raw * 45 / 8192
        longitude = longitude_raw * 45 / 8192
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"location {key} has invalid coordinates")
        records.append(
            LocationRecord(
                *key,
                _read_utf16be(raw, values[3], "city"),
                _read_utf16be(raw, values[4], "region", optional=True),
                _read_utf16be(raw, values[5], "country", optional=True),
                latitude,
                longitude,
            )
        )
    missing = (long_keys | short_keys) - location_keys
    if missing:
        raise ValueError(f"forecast tables reference {len(missing)} missing locations")

    for table_index, label in ((2, "weather condition"), (3, "UV"), (4, "laundry"), (5, "pollen")):
        item_size = sizes[table_index]
        for position in range(counts[table_index]):
            item_offset = offsets[table_index] + position * item_size
            text_offset = struct.unpack_from(">I", raw, item_offset + 4)[0]
            _read_utf16be(raw, text_offset, label)

    return ForecastSummary(size, opened, closed, country, language, temperature, *counts, tuple(records))


def validate_short(payload: bytes, *, signed: bool = True) -> ShortSummary:
    raw = unwrap_signed_payload(payload) if signed else decode_lz10(payload)
    fields = SHORT_HEADER.unpack_from(raw)
    _version, size, _crc, opened, closed = _validate_common(raw, SHORT_HEADER.size)
    country, language = fields[5], fields[6]
    count, offset = fields[8], fields[9]
    if count and offset != SHORT_HEADER.size:
        raise ValueError(f"unexpected current forecast table offset {offset}")
    if offset + count * CURRENT_FORECAST.size != len(raw):
        raise ValueError("current forecast table size does not match the payload")
    for position in range(count):
        values = CURRENT_FORECAST.unpack_from(
            raw, offset + position * CURRENT_FORECAST.size
        )
        _validate_wind_direction(values[9], f"current forecast {position}")
    return ShortSummary(size, opened, closed, country, language, count)
