"""Check explicit private source receipts without treating parse time as weather time.

This is an acquisition-boundary gate, not independent verification of provider
facts or permissions. It never fetches, retimes, fills missing weather or signs.
"""
from __future__ import annotations

import hashlib
import json
import re

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
DATASETS = ('current', 'long', 'compact')


class ForecastSourceError(ValueError):
    pass


def _json(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_DOCUMENT_BYTES:
        raise ForecastSourceError('Normalized document exceeds local byte bounds')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise ForecastSourceError('Normalized source JSON is invalid') from None


def _key(value):
    if (type(value) not in (tuple, list) or len(value) != 3
            or any(type(item) is not int for item in value)
            or not 0 <= value[0] <= 255 or not 0 <= value[1] <= 255
            or not 0 <= value[2] <= 65535):
        raise ForecastSourceError('Source receipt location key is invalid')
    return tuple(value)


def _ref(value):
    if (type(value) is not str or not value.strip() or len(value) > 2048
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ForecastSourceError('Bounded private source/rights reference required')


def check_forecast_sources(documents, receipts, *, now, max_source_age_seconds):
    """Bind normalized rows to explicit observation/issue-time attestations.

    A digest/reference identifies the source bytes; it cannot prove an adapter
    actually extracted that time from them. Public code has no private provider
    parser. Provider-origin timestamps and their attestations must come from a
    separately reviewed acquisition adapter, not a caller's build clock. Native
    local-clock fields are independent and are never used as source times here.
    """
    if (type(now) is not int or not 946684800 <= now < 0xFFFFFFFF
            or type(max_source_age_seconds) is not int
            or not 1 <= max_source_age_seconds <= 7 * 86400
            or type(documents) is not dict or set(documents) != set(DATASETS)
            or type(receipts) is not dict or set(receipts) != {
                'schema_version', 'rights_ref', 'provider_times_retimed',
                'reference_weather_substituted', 'datasets'}
            or type(receipts['schema_version']) is not int or receipts['schema_version'] != 1
            or receipts['provider_times_retimed'] is not False
            or receipts['reference_weather_substituted'] is not False
            or type(receipts['datasets']) is not dict or set(receipts['datasets']) != set(DATASETS)):
        raise ForecastSourceError('Explicit source-time policy and unaltered provider-time receipts required')
    _ref(receipts['rights_ref'])
    counts, source_times, expiry_times, repeats = {}, [], [], 0
    for name in DATASETS:
        rows = _json(documents[name])
        receipt = receipts['datasets'][name]
        if (type(rows) is not list or len(rows) > 4096
                or type(receipt) is not dict or set(receipt) != {'normalized_sha256', 'entries'}
                or receipt['normalized_sha256'] != hashlib.sha256(documents[name]).hexdigest()
                or type(receipt['entries']) is not list or len(receipt['entries']) > 4096):
            raise ForecastSourceError('Source receipt is not bound to the normalized document')
        indexed = {}
        for row in rows:
            try:
                key = _key([row[field] for field in ('country_code', 'region_code', 'location_code')])
                if type(row['local_unix_timestamp']) is not int:
                    raise ValueError()
                if key in indexed:
                    if indexed[key] != row:
                        raise ForecastSourceError('Normalized source has conflicting duplicate rows')
                    repeats += 1
                indexed[key] = row
            except (KeyError, TypeError, ValueError):
                raise ForecastSourceError('Normalized source row is invalid') from None
        seen = set()
        for entry in receipt['entries']:
            if type(entry) is not dict or set(entry) != {
                    'key', 'source_sha256', 'source_ref', 'time_basis',
                    'source_time_utc', 'retrieved_utc', 'valid_until_utc'}:
                raise ForecastSourceError('Source-time receipt fields are incomplete')
            key = _key(entry['key'])
            if key in seen or key not in indexed:
                raise ForecastSourceError('Source receipt keys are duplicated or unrelated')
            seen.add(key)
            _ref(entry['source_ref'])
            if (type(entry['source_sha256']) is not str
                    or re.fullmatch('[0-9a-f]{64}', entry['source_sha256']) is None
                    or entry['time_basis'] not in ('provider_observation', 'provider_issue')
                    or any(type(entry[field]) is not int for field in (
                        'source_time_utc', 'retrieved_utc', 'valid_until_utc'))):
                raise ForecastSourceError('Provider-origin source-time receipt is invalid')
            issued, retrieved, expiry = (entry[field] for field in (
                'source_time_utc', 'retrieved_utc', 'valid_until_utc'))
            if not (946684800 <= issued <= retrieved <= now < expiry < 0xFFFFFFFF
                    and now - issued < max_source_age_seconds):
                raise ForecastSourceError('Weather source time is stale, future-dated or expired')
            source_times.append(issued)
            expiry_times.append(expiry)
        if seen != set(indexed):
            raise ForecastSourceError('Normalized weather lacks complete source-time receipts')
        counts[name] = len(rows)
    if counts['current'] == 0 or counts['long'] + counts['compact'] == 0:
        raise ForecastSourceError('No explicit current/forecast weather supplied')
    return {'rows': counts, 'identical_duplicate_rows': repeats,
            'oldest_source_age_seconds': now - min(source_times),
            'earliest_supplied_expiry_utc': min(expiry_times),
            'source_ages_checked_against_supplied_receipts': True,
            'native_clock_fields_used_as_source_times': False,
            'provider_timestamp_extraction_independently_verified': False,
            'source_rights_independently_verified': False,
            'all_catalog_locations_have_weather': False,
            'native_payload_generated_or_published': False}
