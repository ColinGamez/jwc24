"""Explicit single-slot conversion of VPFD51 daily extrema to native integers.

This replacement policy supplies no city, native clock, complete forecast day,
source-age acceptance, provider activation or publication. The whole supplied
parsed source and its original dates remain attached to the result.
"""
from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction
import re

from .jma_measurements import MISSING_TEMPERATURE, ROUNDING, _rounded
from .jma_weather import JMAError, JST, _iso, _number, utc_datetime
from .jma_xml_temperatures import (
    XMLDailyTemperatureSource, XMLDocumentReceipt, XMLTemperaturePoint,
    XMLTemperatureValue,
)


POLICY_ID = 'jwc24-jma-xml-daily-extrema-v1'
_ROLES = {
    'daytime_maximum': ('\u65e5\u4e2d\u306e\u6700\u9ad8\u6c17\u6e29', 9, 'PT9H'),
    'morning_minimum': ('\u671d\u306e\u6700\u4f4e\u6c17\u6e29', 0, 'PT9H'),
    'maximum_temperature': ('\u6700\u9ad8\u6c17\u6e29', 0, 'PT24H'),
}


@dataclass(frozen=True)
class NativeXMLTemperature:
    policy_id: str
    rounding: str
    source: XMLDailyTemperatureSource
    office_code: str
    series_index: int
    source_series_index: int
    report_datetime: str
    issued_utc: datetime
    control_datetime: str
    transmitted_utc: datetime
    target_datetime: str
    station: XMLTemperaturePoint
    source_value: XMLTemperatureValue
    source_receipt: XMLDocumentReceipt
    native_daily_role: str | None
    temperature_celsius: int
    temperature_fahrenheit: int
    unavailable_reasons: tuple[str, ...]


def project_xml_temperature(source: XMLDailyTemperatureSource, *, series_index: int,
                            station_code: str, ref_id: str, expected_role: str,
                            expected_date: date, rounding: str) -> NativeXMLTemperature:
    """Convert one explicit source slot under reviewed period/unit restrictions.

    ``maximum_temperature`` remains a retained general maximum, never a native
    daily low/high substitute. Unknown units/qualifiers and absent values return
    native missing sentinels with explicit reasons. Incorrect caller selection
    or an unfamiliar period rejects instead of sorting or guessing a target.
    """
    if (type(source) is not XMLDailyTemperatureSource or type(series_index) is not int
            or not 0 <= series_index < len(source.series) or type(station_code) is not str
            or re.fullmatch(r'[0-9]{5}', station_code) is None or type(ref_id) is not str
            or type(expected_role) is not str or expected_role not in _ROLES
            or type(expected_date) is not date or type(rounding) is not str or rounding != ROUNDING):
        raise JMAError('explicit typed XML temperature selection and rounding required')
    series = source.series[series_index]
    points = [p for p in series.points if p.station_code == station_code]
    if len(points) != 1 or type(points[0]) is not XMLTemperaturePoint:
        raise JMAError('selected XML temperature point is absent or ambiguous')
    point = points[0]
    raw_type, hour, duration = _ROLES[expected_role]
    properties = [p for p in point.properties if p.raw_type == raw_type]
    values = [v for p in properties for v in p.values if v.ref_id == ref_id]
    if len(values) != 1 or type(values[0]) is not XMLTemperatureValue:
        raise JMAError('selected XML temperature role/reference is absent or ambiguous')
    value = values[0]
    targets = [t for t in series.time_definitions if t.ref_id == ref_id]
    if len(targets) != 1 or targets[0] != value.target:
        raise JMAError('XML temperature reference differs from its series definition')
    target = value.target
    if _iso(target.datetime) != utc_datetime(target.valid_utc):
        raise JMAError('XML temperature target token and parsed instant differ')
    local = target.valid_utc.astimezone(JST)
    if (target.target_date_jst != expected_date or local.hour != hour or local.minute != 0
            or local.second != 0 or target.duration != duration):
        raise JMAError('selected XML temperature period differs from its reviewed role')
    reasons = []
    daily_role = expected_role if expected_role != 'maximum_temperature' else None
    if daily_role is None:
        reasons.append('general_maximum_is_not_a_native_daily_extremum')
    if value.raw_type != raw_type or value.semantic_role != expected_role:
        reasons.append('unreviewed_temperature_type')
    if value.raw_unit != '\u5ea6':
        reasons.append('unreviewed_temperature_unit')
    attrs = dict(value.attributes)
    if (len(attrs) != len(value.attributes)
            or not {'refID', 'type', 'unit'} <= set(attrs)
            or not set(attrs) <= {'refID', 'type', 'unit', 'description'}
            or attrs.get('refID') != value.ref_id or attrs.get('type') != value.raw_type
            or attrs.get('unit') != value.raw_unit):
        reasons.append('qualified_or_inconsistent_temperature_attributes')
    if value.raw is None or value.raw == '':
        reasons.append('temperature_missing')
    elif value.numeric_value is None:
        reasons.append('temperature_token_unavailable')
    celsius = fahrenheit = MISSING_TEMPERATURE
    if not reasons:
        if (type(value.raw) is not str or len(value.raw) > 512
                or re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', value.raw) is None):
            raise JMAError('XML temperature numeric token differs from its parsed value')
        exact = Fraction(value.raw)
        parsed_number = float(value.raw) if '.' in value.raw else int(value.raw)
        if _number(value.numeric_value) != _number(parsed_number):
            raise JMAError('XML temperature token and parsed numeric value differ')
        if not -1_000_000 <= exact <= 1_000_000:
            raise JMAError('XML temperature token exceeds local conversion bounds')
        # Convert from the original decimal token; never round C before F.
        celsius = _rounded(exact, -127, 127)
        fahrenheit = _rounded(exact * Fraction(9, 5) + 32, -127, 127)
    return NativeXMLTemperature(POLICY_ID, ROUNDING, source, source.office_code, series_index,
        series.source_series_index, source.report_datetime,
        source.issued_utc, source.control_datetime, source.transmitted_utc, source.target_datetime,
        point, value, source.receipt, daily_role, celsius, fahrenheit, tuple(reasons))
