"""Read-only publication checks joining the two native Forecast payloads.

These checks add local consistency policy to the existing binary validators.
They do not prove WC24 delivery, the installed client's trust key, or rendering.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import subprocess
import tempfile

from .forecast import (
    CURRENT_FORECAST, FORECAST_HEADER, SHORT_HEADER, SIGNATURE_ENVELOPE_SIZE,
    WEATHER_CONDITION, ForecastSummary, ShortSummary, unix_to_wii_minutes,
    unwrap_signed_payload, validate_forecast, validate_short,
)

# Local input policy; not a claim about native download capacity. An LZ10 body
# has a 24-bit decompressed length; even an all-literal encoding fits this cap.
MAX_SIGNED_PAYLOAD_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class ForecastBundleSummary:
    forecast: ForecastSummary
    short: ShortSummary
    repeated_current_keys: int
    signatures_verified: bool
    current_windows_checked: bool

    def metadata(self) -> dict[str, object]:
        return {
            'country_code': self.forecast.country_code,
            'language_code': self.forecast.language_code,
            'locations': self.forecast.locations,
            'current_forecasts': self.short.current_forecasts,
            'identical_repeated_current_keys': self.repeated_current_keys,
            'cross_file_references_checked': True,
            'signatures_verified_against_supplied_key': self.signatures_verified,
            'current_windows_checked': self.current_windows_checked,
            'observation_timestamps_checked': False,
            'installed_client_trust_checked': False,
            'native_delivery_or_rendering_checked': False,
        }


def _verify_signature(payload: bytes, public_key: Path) -> None:
    """Verify the existing RSA/SHA-1 envelope with a caller-supplied public key."""
    try:
        with tempfile.TemporaryDirectory(prefix='jwc24-forecast-verify-') as directory:
            signature = Path(directory) / 'signature.bin'
            signature.write_bytes(payload[64:SIGNATURE_ENVELOPE_SIZE])
            result = subprocess.run(
                ['openssl', 'dgst', '-sha1', '-verify', str(public_key),
                 '-signature', str(signature)],
                input=payload[SIGNATURE_ENVELOPE_SIZE:], capture_output=True,
                timeout=15, check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('Forecast signature verification could not run') from error
    if result.returncode != 0:
        # OpenSSL output may contain local paths: keep it out of public reports.
        raise ValueError('Forecast signature does not verify against the supplied key')


def validate_forecast_bundle(
    forecast_payload: bytes,
    short_payload: bytes,
    *,
    current_unix_timestamp: int | None = None,
    public_key: str | Path | None = None,
) -> ForecastBundleSummary:
    """Check both signed-envelope files before publication or a test session.

    A key is optional for historical structural inspection. Without one the
    result explicitly records that signatures were not verified. Current rows
    may cover a subset of the location catalog; missing weather is not invented.
    Conflicting current keys, missing locations/condition dictionary entries,
    mismatched locales and non-overlapping validity windows fail local policy.
    """
    for payload in (forecast_payload, short_payload):
        if not isinstance(payload, bytes):
            raise ValueError('Forecast bundle inputs must be bytes')
        if not SIGNATURE_ENVELOPE_SIZE < len(payload) <= MAX_SIGNED_PAYLOAD_BYTES:
            raise ValueError('Forecast bundle input is outside the local byte limit')
    if public_key is not None:
        key = Path(public_key).resolve()
        _verify_signature(forecast_payload, key)
        _verify_signature(short_payload, key)
    try:
        forecast = validate_forecast(forecast_payload)
        short = validate_short(short_payload)
    except struct.error as error:
        raise ValueError('Forecast bundle contains a truncated native header') from error
    if (forecast.country_code, forecast.language_code) != (short.country_code, short.language_code):
        raise ValueError('Forecast bundle locale fields differ')
    if max(forecast.open_timestamp, short.open_timestamp) >= min(forecast.close_timestamp, short.close_timestamp):
        raise ValueError('Forecast bundle validity windows do not overlap')
    if current_unix_timestamp is not None:
        if type(current_unix_timestamp) is not int:
            raise ValueError('Current timestamp must be an integer Unix timestamp')
        minute = unix_to_wii_minutes(current_unix_timestamp)
        for label, summary in (('forecast.bin', forecast), ('short.bin', short)):
            if not summary.open_timestamp <= minute < summary.close_timestamp:
                raise ValueError(f'{label} is outside its current validity window')

    full_raw = unwrap_signed_payload(forecast_payload)
    short_raw = unwrap_signed_payload(short_payload)
    full_fields = FORECAST_HEADER.unpack_from(full_raw)
    condition_count, condition_offset = full_fields[15:17]
    condition_codes = {
        WEATHER_CONDITION.unpack_from(full_raw, condition_offset + position * WEATHER_CONDITION.size)[0]
        for position in range(condition_count)
    }
    location_keys = {
        (record.country_code, record.region_code, record.location_code)
        for record in forecast.location_records
    }
    count, offset = SHORT_HEADER.unpack_from(short_raw)[8:10]
    seen = {}
    repeated = set()
    for position in range(count):
        row = CURRENT_FORECAST.unpack_from(short_raw, offset + position * CURRENT_FORECAST.size)
        key = row[:3]
        if key in seen:
            if seen[key] != row:
                raise ValueError('Current forecast table contains conflicting duplicate location rows')
            repeated.add(key)
        seen[key] = row
        if key not in location_keys:
            raise ValueError('Current forecast references a missing catalog location')
        if row[5] != 0xFFFF and row[5] not in condition_codes:
            raise ValueError('Current forecast references a missing weather condition')
    return ForecastBundleSummary(forecast, short, len(repeated), public_key is not None, current_unix_timestamp is not None)
