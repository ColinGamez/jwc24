"""Explicit replacement mapping for four reviewed JMA daily condition meanings.

Source: https://www.jma.go.jp/bosai/forecast/ (JMA public data, PDL 1.0).
JWC24 maps the official source meanings to inspected original channel pictures.
This is not a recovered Weathernews/Nintendo dictionary or a publication path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from types import MappingProxyType

from jwc24.forecast import WeatherConditionText
from jwc24.jma_weather import (FORECAST_PAGE, ForecastSource, JMAError,
                              SourceReceipt)

CLIENT_BYTES = 199327
CLIENT_SHA256 = '2219c9b3f581d0e69857eeb4c98e1ebb8059269b73d7886f9ecc9a676b124a50'
POLICY_ID = 'jwc24-jma-pure-daily-conditions-v1'
SUPPORTED = MappingProxyType({'100': (1, '\u6674'), '200': (10, '\u66c7'),
                              '300': (19, '\u96e8'), '400': (26, '\u96ea')})


class JMAUnknownCondition(JMAError):
    """The reviewed source catalog does not contain this code."""


class JMAUnsupportedCondition(JMAError):
    """A real catalog code has no verified native mapping in this policy."""


class JMAConditionUnavailable(JMAError):
    """The selected source explicitly lacks a daily condition code."""


@dataclass(frozen=True)
class ConditionCatalogEntry:
    code: str
    source_day_image: str
    source_night_image: str
    source_group: str
    japanese_label: str
    english_label: str


@dataclass(frozen=True)
class ConditionCatalog:
    entries: tuple[ConditionCatalogEntry, ...]
    receipt: SourceReceipt


@dataclass(frozen=True)
class NativeDailyCondition:
    policy_id: str
    office_code: str
    area_code: str
    area_name: str
    report_index: int
    series_index: int
    target_index: int
    report_datetime: str
    issued_utc: datetime
    target_datetime: str
    valid_utc: datetime
    raw_weather_code: str
    description_field_present: bool
    raw_weather_description: str | None
    dictionary_row: WeatherConditionText
    forecast_receipt: SourceReceipt
    catalog_receipt: SourceReceipt


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise JMAError('duplicate condition catalog code')
        result[key] = value
    return result


def _literal_entries(body):
    """Parse a bounded data-only literal; never evaluate downloaded JavaScript."""
    if type(body) is not bytes or not 1 <= len(body) <= 512 * 1024:
        raise JMAError('condition client body outside bounds')
    try:
        source = body.decode('utf-8')
        marker = 'R.TELOPS='
        if source.count(marker) != 1:
            raise JMAError('condition catalog marker is absent or ambiguous')
        start = source.index(marker) + len(marker)
        stop = source.index('}', start) + 1
        literal = re.sub(r'([,{])([0-9]{3}):', r'\1"\2":', source[start:stop])
        values = json.loads(literal, object_pairs_hook=_pairs)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise JMAError('condition client has no accepted data-only literal') from exc
    if type(values) is not dict or not 1 <= len(values) <= 256:
        raise JMAError('condition catalog is outside bounds')
    entries = []
    for code, row in values.items():
        if (not re.fullmatch(r'[0-9]{3}', code) or type(row) is not list or len(row) != 5
                or any(type(value) is not str or not 1 <= len(value) <= 512
                       or any(ord(c) < 32 for c in value) for value in row)):
            raise JMAError('condition catalog entry shape differs')
        try:
            for value in row:
                value.encode('utf-8')
        except UnicodeError as exc:
            raise JMAError('condition catalog text is not valid Unicode') from exc
        entries.append(ConditionCatalogEntry(code, *row))
    return tuple(entries)


def parse_condition_catalog(body: bytes, receipt: SourceReceipt) -> ConditionCatalog:
    receipt.verify(body, 'forecast_client')
    if len(body) != CLIENT_BYTES or hashlib.sha256(body).hexdigest() != CLIENT_SHA256:
        raise JMAError('condition client is not the reviewed source snapshot')
    entries = _literal_entries(body)
    if len(entries) != 118:
        raise JMAError('reviewed condition catalog count differs')
    found = {entry.code: entry for entry in entries}
    if any(found.get(code) is None or found[code].japanese_label != label
           for code, (_, label) in SUPPORTED.items()):
        raise JMAError('reviewed pure condition meaning differs')
    return ConditionCatalog(entries, receipt)


def project_daily_condition(source: ForecastSource, *, report_index: int,
                            series_index: int, area_code: str, target_index: int,
                            catalog: ConditionCatalog) -> NativeDailyCondition:
    """Select one actual daily code, preserving source dates, identity and text.

    No default report/area/date, FF fallback, night-bit choice or composite
    approximation is supplied. The caller still must establish native location
    identity, source freshness, attribution and complete payload consistency.
    """
    if type(source) is not ForecastSource or type(catalog) is not ConditionCatalog:
        raise JMAError('typed forecast and condition catalog required')
    if (type(catalog.entries) is not tuple
            or any(type(entry) is not ConditionCatalogEntry for entry in catalog.entries)
            or any(type(entry.code) is not str or not re.fullmatch(r'[0-9]{3}', entry.code)
                   for entry in catalog.entries)
            or len({entry.code for entry in catalog.entries}) != len(catalog.entries)):
        raise JMAError('condition catalog entries must be typed and unambiguous')
    if any(type(value) is not int or value < 0 for value in (report_index, series_index, target_index)):
        raise JMAError('explicit nonnegative source indices required')
    if type(area_code) is not str:
        raise JMAError('explicit published area required')
    try:
        report = source.reports[report_index]
        series = report.time_series[series_index]
        target = series.time_defines[target_index]
        valid = series.valid_times_utc[target_index]
    except IndexError as exc:
        raise JMAError('selected source index is absent') from exc
    areas = [area for area in series.areas if area.code == area_code]
    if len(areas) != 1:
        raise JMAError('selected published area is absent or ambiguous')
    area = areas[0]
    codes = [field for field in area.fields if field.name == 'weatherCodes']
    descriptions = [field for field in area.fields if field.name == 'weathers']
    if len(codes) != 1 or len(descriptions) > 1:
        raise JMAError('daily condition field is absent or ambiguous')
    if (len(codes[0].values) != len(series.time_defines)
            or descriptions and len(descriptions[0].values) != len(series.time_defines)):
        raise JMAError('daily condition field and target counts differ')
    code = codes[0].values[target_index].raw
    if code in (None, ''):
        raise JMAConditionUnavailable('selected source condition is unavailable')
    if type(code) is not str or not re.fullmatch(r'[0-9]{3}', code):
        raise JMAError('selected source condition token differs')
    entries = [entry for entry in catalog.entries if entry.code == code]
    if not entries:
        raise JMAUnknownCondition('selected code is absent from the reviewed source catalog')
    if len(entries) != 1 or type(entries[0]) is not ConditionCatalogEntry:
        raise JMAError('condition catalog entry is ambiguous or untyped')
    if code not in SUPPORTED:
        raise JMAUnsupportedCondition('selected source condition has no verified native mapping')
    selector, expected_label = SUPPORTED[code]
    if entries[0].japanese_label != expected_label:
        raise JMAError('pure condition label differs from the reviewed source meaning')
    raw_description = descriptions[0].values[target_index].raw if descriptions else None
    return NativeDailyCondition(
        POLICY_ID, source.office_code, area.code, area.name, report_index, series_index,
        target_index, report.report_datetime, report.issued_utc, target, valid, code,
        bool(descriptions), raw_description, WeatherConditionText(int(code), selector,
        entries[0].japanese_label), source.receipt, catalog.receipt,
    )
