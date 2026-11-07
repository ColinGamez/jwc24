"""Explicit source-kind age checks for selected parsed JMA inputs.

Provider times, metadata cache ages and native location clocks are separate.
This pure gate neither acquires data nor establishes complete mapping/rights,
authenticates supplied receipts, constructs normalized rows, signs or publishes.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from .jma_associations import AssociationCatalog
from .jma_weather import (
    MAX_BODY_BYTES, JST, ForecastSource, JMAError, ObservationSource, SourceReceipt,
    _iso, point_url, source_path, utc_datetime,
)


@dataclass(frozen=True)
class JMAAgePolicy:
    observation_seconds: int
    forecast_issue_seconds: int
    national_latest_seconds: int
    metadata_cache_seconds: int
    station_lag_seconds: int

    def __post_init__(self):
        for name, maximum in (("observation_seconds", 7 * 86400),
                              ("forecast_issue_seconds", 7 * 86400),
                              ("national_latest_seconds", 7 * 86400),
                              ("metadata_cache_seconds", 366 * 86400),
                              ("station_lag_seconds", 86400)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise JMAError("explicit bounded JMA source-age policy required")


@dataclass(frozen=True)
class SourceAge:
    role: str
    time_basis: str
    basis_utc: datetime
    receipt: SourceReceipt
    age_seconds: float
    maximum_age_seconds: int
    expires_utc: datetime


@dataclass(frozen=True)
class JMAAgeCheck:
    checked_utc: datetime
    policy: JMAAgePolicy
    forecast_report_indices: tuple[int, ...]
    station_code: str
    observation_key_jst: str
    station_lag_seconds: float
    checks: tuple[SourceAge, ...]
    earliest_expiry_utc: datetime

    def metadata(self):
        return {
            "checked_utc": self.checked_utc.isoformat(),
            "forecast_report_indices": list(self.forecast_report_indices),
            "station_code": self.station_code,
            "observation_key_jst": self.observation_key_jst,
            "station_lag_seconds": self.station_lag_seconds,
            "earliest_expiry_utc": self.earliest_expiry_utc.isoformat(),
            "checks": [{"role": c.role, "time_basis": c.time_basis,
                        "basis_utc": c.basis_utc.isoformat(), "age_seconds": c.age_seconds,
                        "maximum_age_seconds": c.maximum_age_seconds,
                        "expires_utc": c.expires_utc.isoformat(),
                        "source_url": c.receipt.url, "source_sha256": c.receipt.body_sha256}
                       for c in self.checks],
            "native_clock_used_as_source_time": False,
            "source_receipts_independently_authenticated": False,
            "native_location_mapping_verified": False,
            "all_payload_source_dependencies_verified": False,
            "native_payload_generated_or_published": False,
        }


def _receipt(receipt, kind, now):
    if (type(receipt) is not SourceReceipt or type(receipt.http_status) is not int
            or receipt.http_status != 200 or type(receipt.body_bytes) is not int
            or not 0 < receipt.body_bytes <= MAX_BODY_BYTES
            or type(receipt.body_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", receipt.body_sha256) is None):
        raise JMAError("invalid supplied JMA source receipt")
    actual, arguments = source_path(receipt.url)
    if actual != kind:
        raise JMAError("source receipt route differs from its age role")
    start, end = utc_datetime(receipt.retrieved_start_utc), utc_datetime(receipt.retrieved_end_utc)
    if not start <= end <= now:
        raise JMAError("source retrieval is reversed or after the check clock")
    return end, arguments


def _age(role, basis_kind, basis, receipt, maximum, retrieved, now):
    basis = utc_datetime(basis)
    if basis > retrieved:
        raise JMAError("provider time is after its source retrieval")
    try:
        expiry = basis + timedelta(seconds=maximum)
    except OverflowError:
        raise JMAError("source expiry is outside datetime bounds") from None
    if now >= expiry:
        raise JMAError(role + " is stale under its explicit source-age policy")
    return SourceAge(role, basis_kind, basis, receipt, (now - basis).total_seconds(), maximum, expiry)


def check_jma_age(forecast: ForecastSource, observations: ObservationSource,
                  associations: AssociationCatalog, *, report_indices: tuple[int, ...],
                  observation_key_jst: str, now: datetime, policy: JMAAgePolicy,
                  additional_metadata_receipts: tuple[SourceReceipt, ...] = ()) -> JMAAgeCheck:
    """Check exactly the selected reports, observation and supplied dependencies.

    No latest-record or policy default is chosen. Metadata's retrieval age is
    legitimate cache age; it is never used as a weather issue/observation time.
    A later publisher must check all its actual source dependencies and cap
    publication at this expiry and its own native validity limits.
    """
    if (type(forecast) is not ForecastSource or type(observations) is not ObservationSource
            or type(associations) is not AssociationCatalog or type(policy) is not JMAAgePolicy
            or type(report_indices) is not tuple or not 1 <= len(report_indices) <= 16
            or any(type(i) is not int or not 0 <= i < len(forecast.reports) for i in report_indices)
            or len(set(report_indices)) != len(report_indices)
            or type(observation_key_jst) is not str
            or re.fullmatch(r"[0-9]{14}", observation_key_jst) is None
            or type(additional_metadata_receipts) is not tuple or len(additional_metadata_receipts) > 8):
        raise JMAError("explicit typed JMA inputs, policy and selection required")
    now = utc_datetime(now)
    retrieved, args = _receipt(forecast.receipt, "forecast", now)
    if forecast.office_code != args[0]:
        raise JMAError("forecast office differs from its source receipt")
    checks = []
    for index in report_indices:
        report = forecast.reports[index]
        if _iso(report.report_datetime) != report.issued_utc:
            raise JMAError("forecast raw issue date and parsed provider time disagree")
        checks.append(_age("forecast_report:" + str(index), "provider_issue", report.issued_utc,
                           forecast.receipt, policy.forecast_issue_seconds, retrieved, now))
    latest = observations.national_latest
    if _iso(latest.reported_datetime) != latest.time_utc:
        raise JMAError("national raw date and parsed provider time disagree")
    latest_retrieved, _ = _receipt(latest.receipt, "latest", now)
    checks.append(_age("national_latest", "provider_national_observation_time", latest.time_utc,
                       latest.receipt, policy.national_latest_seconds, latest_retrieved, now))
    obs_retrieved, args = _receipt(observations.receipt, "point", now)
    if (observations.station.code != args[0]
            or observations.receipt.url != point_url(observations.station.code, latest)):
        raise JMAError("station observation does not match its source window")
    selected = [r for r in observations.records if r.source_time_key_jst == observation_key_jst]
    if len(selected) != 1:
        raise JMAError("selected station observation is absent or ambiguous")
    record = selected[0]
    try:
        key_time = datetime.strptime(observation_key_jst, "%Y%m%d%H%M%S").replace(tzinfo=JST)
    except ValueError:
        raise JMAError("selected observation date is invalid") from None
    if key_time != record.observed_utc:
        raise JMAError("observation key and provider time disagree")
    lag = (utc_datetime(latest.time_utc) - utc_datetime(record.observed_utc)).total_seconds()
    if not 0 <= lag < policy.station_lag_seconds:
        raise JMAError("station observation exceeds the explicit national-time lag policy")
    checks.append(_age("station_observation", "provider_observation", record.observed_utc,
                       observations.receipt, policy.observation_seconds, obs_retrieved, now))
    expected = {"short_associations", "weekly_associations", "weekly_candidates", "weekly_names"}
    if (type(associations.receipts) is not tuple or len(associations.receipts) != 4
            or any(type(r) is not SourceReceipt for r in associations.receipts)
            or {source_path(r.url)[0] for r in associations.receipts} != expected):
        raise JMAError("association metadata dependencies are incomplete")
    metadata = [("stations", observations.station.receipt)]
    metadata.extend((source_path(r.url)[0], r) for r in associations.receipts)
    for receipt in additional_metadata_receipts:
        if type(receipt) is not SourceReceipt:
            raise JMAError("typed additional metadata receipt required")
        kind = source_path(receipt.url)[0]
        if kind not in {"common_areas", "forecast_client"}:
            raise JMAError("additional metadata route is not a reviewed dependency")
        metadata.append((kind, receipt))
    seen = set()
    for kind, receipt in metadata:
        end, _ = _receipt(receipt, kind, now)
        if receipt.url in seen:
            raise JMAError("metadata source snapshots are duplicated or conflicting")
        seen.add(receipt.url)
        checks.append(_age("metadata:" + kind, "metadata_retrieval", end, receipt,
                           policy.metadata_cache_seconds, end, now))
    return JMAAgeCheck(now, policy, report_indices, observations.station.code, observation_key_jst,
                       lag, tuple(checks), min(c.expires_utc for c in checks))
