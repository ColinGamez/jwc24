"""Official JMA source associations and dated temperatures; no native mapping.

Metadata describes published forecast groups and temperature points, not a
license to move observations to member cities. Receipts establish consistency
with supplied bytes, not independent authenticity or present-day freshness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re

from .jma_weather import (
    JST, ForecastArea, ForecastSource, ForecastValue, SourceReceipt,
    _json, _list, _object, _raw, _require, _text,
)


def _code(value: object, length: int) -> str:
    _require(type(value) is str and bool(re.fullmatch(r"[0-9]{%d}" % length, value)),
             "invalid source association identity")
    return value


@dataclass(frozen=True)
class ShortAssociation:
    office: str
    class10: str
    class20: str
    temperature_points: tuple[str, ...]
    raw_metadata_json: str


@dataclass(frozen=True)
class WeeklyAssociation:
    office: str
    srf: str
    week: str
    temperature_point: str
    name_jp: str
    name_en: str
    raw_metadata_json: str


@dataclass(frozen=True)
class WeeklyCandidates:
    class10: str
    week_groups: tuple[str, ...]


@dataclass(frozen=True)
class AssociationCatalog:
    short: tuple[ShortAssociation, ...]
    weekly: tuple[WeeklyAssociation, ...]
    candidates: tuple[WeeklyCandidates, ...]
    receipts: tuple[SourceReceipt, ...]


@dataclass(frozen=True)
class ObservationCatalog:
    station_codes: tuple[str, ...]
    receipt: SourceReceipt


def parse_observation_catalog(body: bytes, receipt: SourceReceipt) -> ObservationCatalog:
    """Exact ID membership only; selected station details use parse_station."""
    data = _object(_json(body, receipt, "stations"))
    _require(0 < len(data) <= 10000, "station catalog outside bounds")
    for code, metadata in data.items():
        _code(code, 5)
        _object(metadata)
    return ObservationCatalog(tuple(data), receipt)


def parse_associations(short_body: bytes, short_receipt: SourceReceipt,
                       weekly_body: bytes, weekly_receipt: SourceReceipt,
                       candidates_body: bytes, candidates_receipt: SourceReceipt,
                       names_body: bytes, names_receipt: SourceReceipt) -> AssociationCatalog:
    short_data = _object(_json(short_body, short_receipt, "short_associations"))
    week_data = _object(_json(weekly_body, weekly_receipt, "weekly_associations"))
    candidate_data = _object(_json(candidates_body, candidates_receipt, "weekly_candidates"))
    names = _object(_json(names_body, names_receipt, "weekly_names"))
    for data in (short_data, week_data, candidate_data, names):
        _require(0 < len(data) <= 1000, "association catalog outside bounds")
    for code, name in names.items():
        _code(code, 6)
        name = _object(name)
        _text(name.get("jp"))
        _text(name.get("en"))
    short, weekly, candidates = [], [], []
    for office, rows in short_data.items():
        _code(office, 6)
        seen = set()
        for row in _list(rows, 256):
            row = _object(row)
            region = _code(row.get("class10"), 6)
            _require(region not in seen, "duplicate short association")
            seen.add(region)
            points = tuple(_code(p, 5) for p in _list(row.get("amedas"), 64))
            _require(len(set(points)) == len(points), "duplicate temperature point")
            short.append(ShortAssociation(office, region, _code(row.get("class20"), 7),
                                          points, _raw(row)))
    for office, rows in week_data.items():
        _code(office, 6)
        seen = set()
        for row in _list(rows, 256):
            row = _object(row)
            srf, week, point = (_code(row.get(k), n)
                                for k, n in (("srf", 6), ("week", 6), ("amedas", 5)))
            _require((srf, week, point) not in seen, "duplicate weekly association")
            seen.add((srf, week, point))
            _require(week in names, "weekly group has no published name")
            _require(any(a.office == office and a.class10 == srf for a in short),
                     "weekly representative short area absent from office")
            weekly.append(WeeklyAssociation(office, srf, week, point,
                                            names[week]["jp"], names[week]["en"], _raw(row)))
    week_codes = {a.week for a in weekly}
    short_codes = {a.class10 for a in short}
    for region, groups in candidate_data.items():
        _code(region, 6)
        groups = tuple(_code(g, 6) for g in _list(groups, 64))
        _require(region in short_codes and all(g in week_codes for g in groups),
                 "candidate references an absent association")
        offices = {a.office for a in short if a.class10 == region}
        _require(all(any(a.office in offices and a.week == group for a in weekly) for group in groups),
                 "candidate group is outside its published office")
        _require(len(set(groups)) == len(groups), "duplicate candidate group")
        candidates.append(WeeklyCandidates(region, groups))
    return AssociationCatalog(tuple(short), tuple(weekly), tuple(candidates),
                              (short_receipt, weekly_receipt, candidates_receipt, names_receipt))


def _area(source: ForecastSource, report_index: int, series_index: int,
          code: str) -> ForecastArea | None:
    _require(type(report_index) is int and 0 <= report_index < len(source.reports),
             "explicit report index outside source")
    series = source.reports[report_index].time_series
    _require(series_index < len(series), "expected source series absent")
    return next((a for a in series[series_index].areas if a.code == code), None)


def _has(area: ForecastArea | None, field: str) -> bool:
    return area is not None and any(f.name == field for f in area.fields)


@dataclass(frozen=True)
class AssociationAvailability:
    association: ShortAssociation | WeeklyAssociation
    temperature_point: str
    weather_area_present: bool
    temperature_area_present: bool
    temperature_field_present: bool
    observation_station_present: bool

    @property
    def forecast_present(self) -> bool:
        return self.weather_area_present and self.temperature_field_present


def short_candidates(source: ForecastSource, catalog: AssociationCatalog,
                     observations: ObservationCatalog, class10: str, *,
                     report_index: int) -> tuple[AssociationAvailability, ...]:
    _code(class10, 6)
    out = []
    for association in catalog.short:
        if association.office != source.office_code or association.class10 != class10:
            continue
        for point in association.temperature_points:
            area = _area(source, report_index, 2, point)
            out.append(AssociationAvailability(association, point,
                _has(_area(source, report_index, 0, class10), "weatherCodes"),
                area is not None, _has(area, "temps"), point in observations.station_codes))
    return tuple(out)


def weekly_candidates(source: ForecastSource, catalog: AssociationCatalog,
                      observations: ObservationCatalog, class10: str, *,
                      report_index: int) -> tuple[AssociationAvailability, ...]:
    """Return every published alternative with presence flags; select none."""
    _code(class10, 6)
    groups = next((c.week_groups for c in catalog.candidates if c.class10 == class10), ())
    out = []
    for group in groups:
        for association in catalog.weekly:
            if association.office != source.office_code or association.week != group:
                continue
            point = association.temperature_point
            area = _area(source, report_index, 1, point)
            out.append(AssociationAvailability(association, point,
                _has(_area(source, report_index, 0, group), "weatherCodes"),
                area is not None, _has(area, "tempsMin") and _has(area, "tempsMax"),
                point in observations.station_codes))
    return tuple(out)


@dataclass(frozen=True)
class TemperatureSlot:
    field: str
    index: int
    source_time_define: str
    valid_utc: datetime
    target_date_jst: date
    value: ForecastValue
    unit: str
    role: str | None


@dataclass(frozen=True)
class DatedTemperatures:
    office: str
    report_index: int
    report_datetime: str
    issued_utc: datetime
    temperature_point: str
    temperature_point_name: str
    association: ShortAssociation | WeeklyAssociation
    issue_bucket: str | None
    slots: tuple[TemperatureSlot, ...]
    source_receipt: SourceReceipt
    association_receipts: tuple[SourceReceipt, ...]
    observation_station_present: bool
    observation_catalog_receipt: SourceReceipt


def issue_bucket(issued_utc: datetime) -> str:
    _require(issued_utc.tzinfo is not None and issued_utc.utcoffset() is not None,
             "issue time requires a timezone")
    hour = issued_utc.astimezone(JST).hour
    return "17" if hour < 5 or hour >= 17 else "05" if hour < 11 else "11"


def project_temperatures(source: ForecastSource, catalog: AssociationCatalog,
                         observations: ObservationCatalog,
                         association: ShortAssociation | WeeklyAssociation,
                         temperature_point: str, *, report_index: int) -> DatedTemperatures:
    """Project explicit source roles only, retaining unused and missing tokens.

    The 05/11 selector is proven against captured client functions with synthetic
    values; their actual provider response shapes have not been captured. Count
    and selected calendar-date guards here are local acceptance restrictions.
    """
    _code(temperature_point, 5)
    _require(association.office == source.office_code, "association office differs from source")
    short = isinstance(association, ShortAssociation)
    _require(association in (catalog.short if short else catalog.weekly),
             "association is not from the supplied catalog")
    _require(temperature_point in association.temperature_points if short
             else temperature_point == association.temperature_point,
             "explicit temperature point is not in association")
    area = _area(source, report_index, 2 if short else 1, temperature_point)
    _require(area is not None, "forecast temperature point absent; no fallback selected")
    series = source.reports[report_index].time_series[2 if short else 1]
    report = source.reports[report_index]
    fields = {f.name: f for f in area.fields}
    today = report.issued_utc.astimezone(JST).date()
    bucket = issue_bucket(report.issued_utc) if short else None
    count = len(series.time_defines)
    if short:
        _require("temps" in fields and count == (2 if bucket == "17" else 4),
                 "short temperature shape is outside the reviewed selector")
        roles = {0: "morning_minimum", 1: "daytime_maximum"} if bucket == "17" else {
            0: "daytime_maximum", 2: "morning_minimum", 3: "daytime_maximum"}
        wanted = {i: today + timedelta(days=1 if bucket == "17" or i >= 2 else 0)
                  for i in roles}
        selected = [fields["temps"]]
    else:
        _require("tempsMin" in fields and "tempsMax" in fields,
                 "weekly min/max forecast fields absent")
        selected = [f for f in area.fields if f.name.startswith(("tempsMin", "tempsMax"))]
        roles, wanted = {}, {}
        dates = tuple(t.astimezone(JST).date() for t in series.valid_times_utc)
        _require(dates[0] in (today, today + timedelta(days=1))
                 and len(set(dates)) == len(dates)
                 and all(b == a + timedelta(days=1) for a, b in zip(dates, dates[1:])),
                 "weekly target calendar dates are not consecutive and unique")
    slots = []
    for field in selected:
        _require(field.unit == "degC" and len(field.values) == count,
                 "temperature unit or target/value count mismatch")
        for i, value in enumerate(field.values):
            target = series.valid_times_utc[i].astimezone(JST).date()
            if short and i in wanted:
                _require(target == wanted[i], "selected short role target date disagrees with issue date")
            role = roles.get(i) if short else "provider_" + field.name
            slots.append(TemperatureSlot(field.name, i, series.time_defines[i],
                                         series.valid_times_utc[i], target, value, "degC", role))
    return DatedTemperatures(source.office_code, report_index, report.report_datetime,
        report.issued_utc, temperature_point, area.name, association, bucket, tuple(slots),
        source.receipt, catalog.receipts, temperature_point in observations.station_codes,
        observations.receipt)
