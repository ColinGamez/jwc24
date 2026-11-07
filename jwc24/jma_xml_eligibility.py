"""Byte-bound, narrow VPFD51 report eligibility, separate from publication.

This local policy accepts only the normal announcement/version tuple actually
reviewed in the retained reports. It cannot establish that no later correction
or cancellation exists, select a latest report or authenticate its origin.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .jma_weather import JMAError, utc_datetime
from .jma_xml_temperatures import (
    XMLDailyTemperatureSource, XMLDocumentReceipt, parse_daily_temperatures,
)


POLICY_ID = "jwc24-vpfd51-normal-announcement-age-v1"


@dataclass(frozen=True)
class XMLEligibilityCheck:
    source: XMLDailyTemperatureSource
    checked_utc: datetime
    maximum_issue_age_seconds: int
    issue_age_seconds: float
    expires_utc: datetime

    def metadata(self) -> dict:
        return {
            "policy_id": POLICY_ID,
            "office_code": self.source.office_code,
            "source_sha256": self.source.receipt.body_sha256,
            "provider_issue_utc": self.source.issued_utc.isoformat(),
            "provider_transmission_utc": self.source.transmitted_utc.isoformat(),
            "provider_target_utc": self.source.target_utc.isoformat(),
            "retrieved_end_utc": self.source.receipt.retrieved_end_utc.isoformat(),
            "checked_utc": self.checked_utc.isoformat(),
            "maximum_issue_age_seconds": self.maximum_issue_age_seconds,
            "issue_age_seconds": self.issue_age_seconds,
            "expires_utc": self.expires_utc.isoformat(),
            "normal_announcement_age_check_passed": True,
            "latest_report_or_correction_history_verified": False,
            "source_independently_authenticated": False,
            "all_payload_dependencies_verified": False,
            "native_payload_generated_or_published": False,
        }


def check_xml_eligibility(body: bytes, receipt: XMLDocumentReceipt, *,
                          expected_office: str, now: datetime,
                          maximum_issue_age_seconds: int) -> XMLEligibilityCheck:
    """Reparse exact supplied bytes and check one report under explicit limits.

    No cached typed object can substitute changed dates or status. A successful
    result is only a prerequisite: the caller must still handle supersession,
    cancellation history, every other source and native validity independently.
    """
    if (type(expected_office) is not str or len(expected_office) != 6
            or any(c not in "0123456789" for c in expected_office)
            or type(maximum_issue_age_seconds) is not int
            or not 1 <= maximum_issue_age_seconds <= 7 * 86400):
        raise JMAError("explicit office and bounded XML issue-age policy required")
    now = utc_datetime(now)
    source = parse_daily_temperatures(body, receipt)
    if source.office_code != expected_office:
        raise JMAError("XML report office differs from explicit selection")
    if (source.status, source.info_type, source.info_kind_version) != (
            "通常", "発表", "1.0_1"):
        raise JMAError("XML report status/type/version outside reviewed announcement policy")
    # Actual transmissions can precede the displayed announcement; neither the
    # transmission, target nor retrieval becomes a substitute issue timestamp.
    if not receipt.retrieved_start_utc <= receipt.retrieved_end_utc <= now:
        raise JMAError("XML retrieval is after the eligibility clock")
    try:
        expiry = source.issued_utc + timedelta(seconds=maximum_issue_age_seconds)
    except OverflowError:
        raise JMAError("XML issue expiry is outside datetime bounds") from None
    if now >= expiry:
        raise JMAError("XML report is stale under its explicit issue-age policy")
    return XMLEligibilityCheck(source, now, maximum_issue_age_seconds,
                               (now - source.issued_utc).total_seconds(), expiry)
