"""Normal-report and issue-age gates, including retained real morning reports."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from jwc24.jma_weather import JMAError
from jwc24.jma_xml_eligibility import check_xml_eligibility
from jwc24.jma_xml_temperatures import XMLDocumentReceipt
from tests.test_jma_xml_temperatures import NOW, fixture, receipt


def check(body=None, **overrides):
    body = fixture() if body is None else body
    args = dict(expected_office="130000", now=NOW, maximum_issue_age_seconds=14400)
    args.update(overrides)
    return check_xml_eligibility(body, receipt(body), **args)


class XMLEligibilityTests(unittest.TestCase):
    def test_issue_expiry_is_independent_of_earlier_transmission_and_target(self):
        result = check()
        self.assertEqual(result.source.issued_utc.hour, 2)
        self.assertLess(result.source.transmitted_utc, result.source.issued_utc)
        self.assertEqual(result.issue_age_seconds, 10800)
        self.assertEqual(result.expires_utc, NOW + timedelta(hours=1))
        metadata = result.metadata()
        self.assertTrue(metadata["normal_announcement_age_check_passed"])
        self.assertFalse(metadata["latest_report_or_correction_history_verified"])
        self.assertFalse(metadata["native_payload_generated_or_published"])

    def test_training_test_correction_cancel_unknown_and_version_drift_reject(self):
        for old, value in (("通常", "訓練"), ("通常", "試験"), ("通常", "CCA"),
                           ("通常", ""), ("発表", "訂正"), ("発表", "取消"),
                           ("発表", "future"), ("1.0_1", "1.0_2")):
            body = fixture().replace(old.encode(), value.encode())
            with self.subTest(value=value), self.assertRaises(JMAError):
                check(body)

    def test_expiry_boundary_and_old_issue_with_new_receipt(self):
        expiry = NOW + timedelta(hours=1)
        self.assertEqual(check(now=expiry - timedelta(microseconds=1)).expires_utc, expiry)
        for now in (expiry, expiry + timedelta(days=10)):
            with self.subTest(now=now), self.assertRaises(JMAError):
                check(now=now)
        body = fixture()
        fetched = NOW + timedelta(days=10)
        new_receipt = XMLDocumentReceipt.from_body(receipt(body).url, body, fetched, fetched)
        with self.assertRaises(JMAError):
            check_xml_eligibility(body, new_receipt, expected_office="130000",
                                  now=fetched, maximum_issue_age_seconds=14400)

    def test_office_clock_and_explicit_policy_errors_reject(self):
        for changes in ({"expected_office": "100000"}, {"expected_office": "１３0000"},
                        {"now": NOW - timedelta(microseconds=1)},
                        {"now": NOW.replace(tzinfo=None)}, {"maximum_issue_age_seconds": True},
                        {"maximum_issue_age_seconds": 0}, {"maximum_issue_age_seconds": 604801}):
            with self.subTest(changes=changes), self.assertRaises(JMAError):
                check(**changes)

    def test_byte_receipt_binding_prevents_status_and_timestamp_substitution(self):
        body = fixture()
        for changed in (body.replace("通常".encode(), "訓練".encode()),
                        body.replace(b"11:00:00", b"12:00:00")):
            with self.assertRaises(JMAError):
                check_xml_eligibility(changed, receipt(body), expected_office="130000",
                                      now=NOW, maximum_issue_age_seconds=14400)
        with self.assertRaises(JMAError):
            check_xml_eligibility(body, replace(receipt(body), http_status=302),
                                  expected_office="130000", now=NOW,
                                  maximum_issue_age_seconds=14400)

    def test_target_is_retained_and_never_substituted_for_issue(self):
        body = fixture().replace(b"<TargetDateTime>2026-01-02T11:00:00+09:00",
                                  b"<TargetDateTime>2026-01-03T00:00:00+09:00")
        result = check(body)
        self.assertGreater(result.source.target_utc, result.checked_utc)
        self.assertEqual(result.issue_age_seconds, 10800)

    def test_actual_private_morning_captures_pass_historical_clock_but_not_later_clock(self):
        folder = Path("private/forecast/jma-shape-audit-20261107")
        if not all((folder / (name + suffix)).is_file() for name in ("tokyo-05", "tokyo-11")
                   for suffix in (".body", ".json")):
            self.skipTest("optional real private VPFD51 05/11 captures absent")
        for name in ("tokyo-05", "tokyo-11"):
            body = (folder / (name + ".body")).read_bytes()
            item = json.loads((folder / (name + ".json")).read_bytes())
            self.assertTrue(item["complete"])
            self.assertIsNone(item["failure"])
            r = XMLDocumentReceipt(item["url"], item["body_sha256"], item["body_bytes"],
                datetime.fromisoformat(item["retrieved_start_utc"]),
                datetime.fromisoformat(item["retrieved_end_utc"]), item["status"])
            args = dict(expected_office="130000", maximum_issue_age_seconds=86400)
            result = check_xml_eligibility(body, r, now=r.retrieved_end_utc, **args)
            self.assertEqual(result.source.receipt, r)
            self.assertEqual(len(result.source.series[0].points), 4)
            self.assertLess(result.source.transmitted_utc, result.source.issued_utc)
            with self.assertRaises(JMAError):
                check_xml_eligibility(body, r,
                    now=datetime(2026, 11, 10, tzinfo=timezone.utc), **args)


if __name__ == "__main__":
    unittest.main()
