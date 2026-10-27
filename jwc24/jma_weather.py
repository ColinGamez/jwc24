"""Dated JMA source records, without native Forecast conversion or publication.

Source: https://www.jma.go.jp/bosai/forecast/ and
https://www.jma.go.jp/bosai/amedas/ (JMA public data, PDL 1.0).
JWC24 parses and annotates the source; it does not create JMA forecasts.
See channels/forecast/jma_source.md for the captured consumer contract.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Any
from urllib.parse import urlsplit


MAX_BODY_BYTES = 2 * 1024 * 1024
JST = timezone(timedelta(hours=9))
UTC = timezone.utc
BASE = "https://www.jma.go.jp"
TERMS_URL = BASE + "/jma/kishou/info/coment.html"
FORECAST_PAGE = BASE + "/bosai/forecast/"
AMEDAS_PAGE = BASE + "/bosai/amedas/"


class JMAError(ValueError):
    """A source or its supplied provenance does not meet this parser's contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise JMAError(message)


def utc_datetime(value: datetime) -> datetime:
    _require(isinstance(value, datetime) and value.tzinfo is not None,
             "a timezone-qualified datetime is required")
    _require(value.utcoffset() is not None, "a timezone-qualified datetime is required")
    return value.astimezone(UTC)


def _iso(value: Any) -> datetime:
    _require(isinstance(value, str) and bool(re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})", value)),
        "source time must include its complete date, seconds and timezone")
    try:
        return utc_datetime(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as exc:
        raise JMAError("invalid source datetime") from exc


def source_path(url: str) -> tuple[str, tuple[str, ...]]:
    """Restrict evidence and acquisition to the exact reviewed official routes."""
    _require(isinstance(url, str) and len(url) <= 256, "invalid source URL")
    try:
        p = urlsplit(url)
    except ValueError as exc:
        raise JMAError("invalid source URL") from exc
    _require(p.scheme == "https" and p.netloc == "www.jma.go.jp"
             and not p.query and not p.fragment, "source must use the official HTTPS origin")
    routes = (
        ("forecast", r"/bosai/forecast/data/forecast/([0-9]{6})\.json"),
        ("latest", r"/bosai/amedas/data/latest_time\.txt"),
        ("stations", r"/bosai/amedas/const/amedastable\.json"),
        ("point", r"/bosai/amedas/data/point/([0-9]{5})/([0-9]{8})_([0-9]{2})\.json"),
    )
    for kind, pattern in routes:
        m = re.fullmatch(pattern, p.path)
        if m:
            return kind, m.groups()
    raise JMAError("source route is outside the reviewed contract")


@dataclasses.dataclass(frozen=True)
class SourceReceipt:
    url: str
    body_sha256: str
    body_bytes: int
    retrieved_start_utc: datetime
    retrieved_end_utc: datetime
    http_status: int = 200

    @classmethod
    def from_body(cls, url: str, body: bytes, started: datetime,
                  ended: datetime, *, status: int = 200) -> SourceReceipt:
        source_path(url)
        _require(type(body) is bytes and 0 < len(body) <= MAX_BODY_BYTES,
                 "source body is empty or exceeds the capture bound")
        start, end = utc_datetime(started), utc_datetime(ended)
        _require(start <= end, "retrieval bounds are reversed")
        _require(type(status) is int and status == 200, "source HTTP status is not 200")
        return cls(url, hashlib.sha256(body).hexdigest(), len(body), start, end, status)

    def verify(self, body: bytes, expected_kind: str) -> tuple[str, ...]:
        actual = SourceReceipt.from_body(self.url, body, self.retrieved_start_utc,
                                        self.retrieved_end_utc, status=self.http_status)
        _require(actual == self, "source digest, length or retrieval metadata mismatch")
        kind, args = source_path(self.url)
        _require(kind == expected_kind, "source route does not match the parser")
        return args


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in out, "duplicate JSON member")
        out[key] = value
    return out


def _json(body: bytes, receipt: SourceReceipt, kind: str) -> Any:
    receipt.verify(body, kind)
    try:
        data = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_float=lambda token: _number(float(token)),
                          parse_constant=lambda _: (_ for _ in ()).throw(JMAError("nonfinite JSON number")))
        pending = [data]
        while pending:
            value = pending.pop()
            if isinstance(value, str):
                value.encode("utf-8")  # Reject escaped lone surrogates, including unknown metadata.
            elif type(value) is dict:
                pending.extend(value.keys())
                pending.extend(value.values())
            elif type(value) is list:
                pending.extend(value)
        return data
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise JMAError("invalid source JSON") from exc


def _object(value: Any) -> dict[str, Any]:
    _require(type(value) is dict, "expected a source object")
    return value


def _list(value: Any, maximum: int, *, empty: bool = False) -> list[Any]:
    _require(type(value) is list and (0 if empty else 1) <= len(value) <= maximum,
             "source array outside bounds")
    return value


def _text(value: Any, maximum: int = 512) -> str:
    _require(isinstance(value, str) and 0 < len(value) <= maximum
             and not any(ord(c) < 32 for c in value), "invalid source text")
    return value


def _raw(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise JMAError("invalid source metadata") from exc


def _number(value: Any) -> int | float:
    _require(type(value) in (int, float), "expected a finite source number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    _require(finite, "expected a finite source number")
    return value


@dataclasses.dataclass(frozen=True)
class ForecastValue:
    raw: str | None
    value: str | int | float | None


@dataclasses.dataclass(frozen=True)
class ForecastField:
    name: str
    unit: str | None
    semantic: str
    values: tuple[ForecastValue, ...]


@dataclasses.dataclass(frozen=True)
class ForecastArea:
    code: str
    name: str
    fields: tuple[ForecastField, ...]


@dataclasses.dataclass(frozen=True)
class ForecastSeries:
    time_defines: tuple[str, ...]
    valid_times_utc: tuple[datetime, ...]
    areas: tuple[ForecastArea, ...]


@dataclasses.dataclass(frozen=True)
class ForecastReport:
    publishing_office: str
    report_datetime: str
    issued_utc: datetime
    time_series: tuple[ForecastSeries, ...]
    # Climatological averages are preserved, never substituted for forecasts.
    extra_metadata_json: str


@dataclasses.dataclass(frozen=True)
class ForecastSource:
    office_code: str
    reports: tuple[ForecastReport, ...]
    receipt: SourceReceipt


_NUMERIC_FORECAST = frozenset({"temps", "tempsMin", "tempsMinUpper", "tempsMinLower",
                             "tempsMax", "tempsMaxUpper", "tempsMaxLower", "pops"})
_TEXT_FORECAST = frozenset({"weathers", "winds", "waves", "reliabilities"})


def _forecast_field(name: str, values: Any, count: int) -> ForecastField:
    _text(name, 80)
    array = _list(values, 128)
    _require(len(array) == count, "forecast values and target times differ in length")
    parsed = []
    for raw in array:
        _require(raw is None or isinstance(raw, str) and len(raw) <= 512,
                 "forecast values must preserve their source string or null")
        if raw in (None, ""):
            parsed.append(ForecastValue(raw, None))
        elif name in _NUMERIC_FORECAST:
            _require(bool(re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw)),
                     "invalid forecast numeric token")
            value = float(raw) if "." in raw else int(raw)
            _number(value)
            if name == "pops":
                _require(0 <= value <= 100, "precipitation probability outside percent range")
            parsed.append(ForecastValue(raw, value))
        else:
            _text(raw)
            if name == "weatherCodes":
                _require(bool(re.fullmatch(r"[0-9]{3}", raw)), "invalid JMA weather code")
            parsed.append(ForecastValue(raw, raw))
    if name in _NUMERIC_FORECAST:
        unit = "percent" if name == "pops" else "degC"
        # The paired short-range `temps` roles are intentionally not inferred.
        semantic = "provider_temperature_sequence" if name == "temps" else "provider_" + name
    elif name == "weatherCodes":
        unit, semantic = None, "JMA_weather_code"
    else:
        unit = None
        semantic = "provider_" + name if name in _TEXT_FORECAST else "unmapped_provider_field"
    return ForecastField(name, unit, semantic, tuple(parsed))


def parse_forecast(body: bytes, receipt: SourceReceipt) -> ForecastSource:
    data = _list(_json(body, receipt, "forecast"), 16)
    reports = []
    for item in data:
        report = _object(item)
        issued_raw = report.get("reportDatetime")
        issued = _iso(issued_raw)
        # Explicit local acceptance policy, not an HTTP Date/mtime inference.
        _require(issued <= receipt.retrieved_end_utc, "forecast issue time is after retrieval")
        series_out = []
        for s in _list(report.get("timeSeries"), 32):
            s = _object(s)
            times = tuple(_list(s.get("timeDefines"), 128))
            utc_times = tuple(_iso(t) for t in times)
            _require(all(a < b for a, b in zip(utc_times, utc_times[1:])),
                     "forecast target times must be increasing and unique")
            areas, seen = [], set()
            for a in _list(s.get("areas"), 256):
                a = _object(a)
                identity = _object(a.get("area"))
                code = _text(identity.get("code"), 6)
                _require(bool(re.fullmatch(r"[0-9]{5,6}", code)) and code not in seen,
                         "invalid or duplicate forecast area")
                seen.add(code)
                fields = tuple(_forecast_field(k, v, len(times)) for k, v in a.items() if k != "area")
                _require(0 < len(fields) <= 64, "forecast area has no fields or too many fields")
                areas.append(ForecastArea(code, _text(identity.get("name")), fields))
            series_out.append(ForecastSeries(times, utc_times, tuple(areas)))
        extras = {k: v for k, v in report.items()
                  if k not in {"publishingOffice", "reportDatetime", "timeSeries"}}
        reports.append(ForecastReport(_text(report.get("publishingOffice")), issued_raw,
                                      issued, tuple(series_out), _raw(extras)))
    return ForecastSource(source_path(receipt.url)[1][0], tuple(reports), receipt)


@dataclasses.dataclass(frozen=True)
class Station:
    code: str
    name: str
    kana: str | None
    english_name: str | None
    station_type: str
    elements: str
    latitude_degrees_minutes: tuple[int, int | float]
    longitude_degrees_minutes: tuple[int, int | float]
    altitude_m: int | float
    raw_metadata_json: str
    receipt: SourceReceipt


def parse_station(body: bytes, receipt: SourceReceipt, station_code: str) -> Station:
    _require(isinstance(station_code, str) and bool(re.fullmatch(r"[0-9]{5}", station_code)),
             "station must be an explicit five-digit provider ID")
    catalog = _object(_json(body, receipt, "stations"))
    _require(station_code in catalog, "selected station absent from provider metadata")
    s = _object(catalog[station_code])
    coordinates = []
    for key, maximum in (("lat", 90), ("lon", 180)):
        pair = _list(s.get(key), 2)
        _require(len(pair) == 2 and type(pair[0]) is int and -maximum <= pair[0] <= maximum,
                 "invalid station coordinate degrees")
        minute = _number(pair[1])
        _require(0 <= minute < 60 and (abs(pair[0]) < maximum or minute == 0),
                 "invalid station coordinate minutes")
        coordinates.append((pair[0], minute))
    return Station(station_code, _text(s.get("kjName")),
                   _text(s["knName"]) if s.get("knName") else None,
                   _text(s["enName"]) if s.get("enName") else None,
                   _text(s.get("type"), 16), _text(s.get("elems"), 64),
                   coordinates[0], coordinates[1], _number(s.get("alt")), _raw(s), receipt)


@dataclasses.dataclass(frozen=True)
class LatestObservationTime:
    reported_datetime: str
    time_utc: datetime
    receipt: SourceReceipt


def parse_latest_time(body: bytes, receipt: SourceReceipt) -> LatestObservationTime:
    receipt.verify(body, "latest")
    try:
        raw = body.decode("ascii").strip()
    except UnicodeError as exc:
        raise JMAError("latest time is not ASCII") from exc
    time = _iso(raw)
    _require(time <= receipt.retrieved_end_utc, "national observation time is after retrieval")
    return LatestObservationTime(raw, time, receipt)


def point_url(station_code: str, latest: LatestObservationTime) -> str:
    _require(isinstance(station_code, str) and bool(re.fullmatch(r"[0-9]{5}", station_code)),
             "station must be an explicit five-digit provider ID")
    local = latest.time_utc.astimezone(JST)
    # Actual JMA client floors the JST hour to its eight three-hour file windows.
    return (BASE + "/bosai/amedas/data/point/" + station_code + "/"
            + local.strftime("%Y%m%d") + f"_{local.hour // 3 * 3:02d}.json")


@dataclasses.dataclass(frozen=True)
class ObservationValue:
    name: str
    raw_value: int | float | None
    qc: int
    qualifier: str
    unit: str | None
    period_seconds: int | None
    supported_unit: bool

    @property
    def normal_in_jma_client(self) -> bool:
        return self.raw_value is not None and self.qc in (0, 1)

    @property
    def unqualified(self) -> bool:
        """Conservative local eligibility only; this does not emit native data."""
        return self.raw_value is not None and self.qc == 0


# Units from the captured official client element table; no scale conversion.
_OBS_UNITS: dict[str, tuple[str, int | None]] = {
    "temp": ("degC", None), "maxTemp": ("degC", None), "minTemp": ("degC", None),
    "wind": ("m/s", 600), "gust": ("m/s", None),
    "windDirection": ("JMA_16_direction_0_calm", 600),
    "gustDirection": ("JMA_16_direction_0_calm", None),
    "pressure": ("hPa", None), "normalPressure": ("hPa", None),
    "humidity": ("percent", None), "snow": ("cm", None),
    "snow1h": ("cm", 3600), "snow6h": ("cm", 21600),
    "snow12h": ("cm", 43200), "snow24h": ("cm", 86400),
    "sun10m": ("minute", 600), "sun1h": ("hour", 3600),
    "precipitation10m": ("mm", 600), "precipitation1h": ("mm", 3600),
    "precipitation3h": ("mm", 10800), "precipitation24h": ("mm", 86400),
}
_QC = ("", ")", "#", "#", "]", "\u4f11\u6b62\u4e2d", "\u00d7", " ")


@dataclasses.dataclass(frozen=True)
class ObservationRecord:
    source_time_key_jst: str
    observed_utc: datetime
    values: tuple[ObservationValue, ...]
    # Hour/minute extrema metadata is not silently promoted to a full date.
    metadata_json: str

    def value(self, name: str) -> ObservationValue | None:
        return next((v for v in self.values if v.name == name), None)


@dataclasses.dataclass(frozen=True)
class ObservationSource:
    station: Station
    records: tuple[ObservationRecord, ...]
    national_latest: LatestObservationTime
    receipt: SourceReceipt


def parse_observations(body: bytes, receipt: SourceReceipt, station: Station,
                       latest: LatestObservationTime) -> ObservationSource:
    data = _object(_json(body, receipt, "point"))
    code, day, hour = source_path(receipt.url)[1]
    _require(code == station.code, "point file and selected station differ")
    _require(receipt.url == point_url(code, latest), "point file does not match latest-time window")
    try:
        window = datetime.strptime(day + hour, "%Y%m%d%H").replace(tzinfo=JST)
    except ValueError as exc:
        raise JMAError("invalid point file date") from exc
    _require(int(hour) % 3 == 0, "point file is not a three-hour JST window")
    _require(0 < len(data) <= 180, "empty or overlong station observations")
    records = []
    for key, item in sorted(data.items()):
        _require(isinstance(key, str) and bool(re.fullmatch(r"[0-9]{14}", key)),
                 "observation key must include the full JST date and time")
        try:
            local = datetime.strptime(key, "%Y%m%d%H%M%S").replace(tzinfo=JST)
        except ValueError as exc:
            raise JMAError("invalid observation date") from exc
        observed = local.astimezone(UTC)
        _require(window <= local < window + timedelta(hours=3), "observation outside point file window")
        _require(observed <= latest.time_utc and observed <= receipt.retrieved_end_utc,
                 "observation is after national latest time or retrieval")
        item = _object(item)
        pref, number = item.get("prefNumber"), item.get("observationNumber")
        _require(type(pref) is int and type(number) is int
                 and 0 <= pref <= 99 and 0 <= number <= 999
                 and f"{pref:02d}{number:03d}" == code,
                 "record identity does not match its station")
        values, metadata = [], {}
        for name, pair in item.items():
            _text(name, 80)
            _require(name not in _OBS_UNITS or type(pair) is list,
                     "known observation field requires its value/QC array")
            if name in {"prefNumber", "observationNumber"} or type(pair) is not list:
                metadata[name] = pair
                continue
            _require(len(pair) == 2 and type(pair[1]) is int and 0 <= pair[1] <= 7,
                     "observation requires an explicit supported QC code")
            raw = pair[0] if pair[0] is None else _number(pair[0])
            if name in {"windDirection", "gustDirection"} and raw is not None:
                _require(type(raw) is int and 0 <= raw <= 16, "invalid JMA wind direction")
            unit, period = _OBS_UNITS.get(name, (None, None))
            values.append(ObservationValue(name, raw, pair[1], _QC[pair[1]], unit,
                                           period, name in _OBS_UNITS))
        _require(bool(values), "observation has no measurement arrays")
        records.append(ObservationRecord(key, observed, tuple(values), _raw(metadata)))
    return ObservationSource(station, tuple(records), latest, receipt)


def source_records_document(forecast: ForecastSource, observations: ObservationSource) -> dict[str, Any]:
    """Export usable dated source records; never native normalized weather or receipts."""
    def convert(value: Any) -> Any:
        if dataclasses.is_dataclass(value):
            return {f.name: convert(getattr(value, f.name)) for f in dataclasses.fields(value)}
        if isinstance(value, datetime):
            return utc_datetime(value).isoformat()
        if isinstance(value, tuple):
            return [convert(v) for v in value]
        return value

    return {
        "schema_version": 1,
        "record_type": "JMA_source_records_not_native_forecast",
        "source_credit": [{"name": "Japan Meteorological Agency", "url": FORECAST_PAGE},
                          {"name": "Japan Meteorological Agency", "url": AMEDAS_PAGE}],
        "processing_notice": "JWC24 parsed and annotated JMA source records; no native mapping or publication.",
        "terms_url": TERMS_URL,
        "native_location_mapping": None,
        "current_weather_inferred": False,
        "forecast": convert(forecast),
        "observations": convert(observations),
    }
