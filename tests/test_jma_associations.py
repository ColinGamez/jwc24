"""Synthetic contract tests and optional immutable October source replay."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from jwc24.jma_associations import (
    issue_bucket, parse_associations, parse_observation_catalog,
    project_temperatures, short_candidates, weekly_candidates,
)
from jwc24.jma_weather import BASE, JMAError, SourceReceipt, parse_forecast


NOW = datetime(2026, 1, 3, tzinfo=timezone.utc)


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def source(kind, value):
    routes = {"short": "/bosai/forecast/const/forecast_area.json",
              "week": "/bosai/forecast/const/week_area.json",
              "candidates": "/bosai/forecast/const/week_area05.json",
              "names": "/bosai/forecast/const/week_area_name.json",
              "stations": "/bosai/amedas/const/amedastable.json",
              "forecast": "/bosai/forecast/data/forecast/130000.json"}
    body = encoded(value)
    return body, SourceReceipt.from_body(BASE + routes[kind], body, NOW - timedelta(seconds=1), NOW)


def catalog_values():
    return [{"130000": [{"class10": "130030", "class20": "1340100",
                          "amedas": ["44263", "99999"]}]},
            {"130000": [{"srf": "130030", "week": "130100", "amedas": "44263"},
                        {"srf": "130030", "week": "130030", "amedas": "99999"}]},
            {"130030": ["130100", "130030"]},
            {"130100": {"jp": "Synthetic published island group", "en": "Synthetic group"},
             "130030": {"jp": "Synthetic alternate group", "en": "Synthetic alternate"}}]


def catalog(values=None):
    pairs = [source(k, v) for k, v in zip(("short", "week", "candidates", "names"),
                                        catalog_values() if values is None else values)]
    return parse_associations(*(x for pair in pairs for x in pair))


def observations():
    return parse_observation_catalog(*source("stations", {"44263": {"name": "Synthetic station"}}))


def forecast_values(hour=17):
    issue = f"2026-01-02T{hour:02d}:00:00+09:00"
    times = (["2026-01-03T00:00:00+09:00", "2026-01-03T09:00:00+09:00"] if hour >= 17 else
             ["2026-01-02T09:00:00+09:00", "2026-01-02T18:00:00+09:00",
              "2026-01-03T00:00:00+09:00", "2026-01-03T09:00:00+09:00"])
    values = ["", "12"] if len(times) == 2 else ["12", "-99", "", "13"]
    return [{"publishingOffice": "Synthetic office", "reportDatetime": issue, "timeSeries": [
        {"timeDefines": ["2026-01-02T17:00:00+09:00"], "areas": [
            {"area": {"code": "130030", "name": "Synthetic short area"}, "weatherCodes": ["100"]}]},
        {"timeDefines": ["2026-01-02T18:00:00+09:00"], "areas": [
            {"area": {"code": "130030", "name": "Synthetic short area"}, "pops": ["0"]}]},
        {"timeDefines": times, "areas": [
            {"area": {"code": "44263", "name": "Synthetic point"}, "temps": values}]}]},
        {"publishingOffice": "Synthetic weekly office", "reportDatetime": "2026-01-02T11:00:00+09:00",
         "timeSeries": [
            {"timeDefines": ["2026-01-03T00:00:00+09:00", "2026-01-04T00:00:00+09:00"],
             "areas": [{"area": {"code": "130100", "name": "Synthetic published island group"},
                        "weatherCodes": ["100", "200"]}]},
            {"timeDefines": ["2026-01-03T00:00:00+09:00", "2026-01-04T00:00:00+09:00"],
             "areas": [{"area": {"code": "44263", "name": "Synthetic representative point"},
                        "tempsMin": ["0", ""], "tempsMax": ["12", "13"],
                        "tempsMinLower": ["-2", None]}]}]}]


def forecast(value=None, hour=17):
    return parse_forecast(*source("forecast", forecast_values(hour) if value is None else value))


class AssociationTests(unittest.TestCase):
    def test_all_short_points_and_raw_metadata_remain(self):
        result = catalog()
        self.assertEqual(result.short[0].temperature_points, ("44263", "99999"))
        self.assertEqual(json.loads(result.short[0].raw_metadata_json), catalog_values()[0]["130000"][0])
        self.assertEqual(len(result.receipts), 4)

    def test_published_week_group_and_representative_not_member_city(self):
        row = catalog().weekly[0]
        self.assertEqual((row.week, row.srf, row.temperature_point), ("130100", "130030", "44263"))
        self.assertEqual(row.name_en, "Synthetic group")

    def test_all_alternatives_survive_with_forecast_and_station_states_separate(self):
        rows = weekly_candidates(forecast(), catalog(), observations(), "130030", report_index=1)
        self.assertEqual([r.association.week for r in rows], ["130100", "130030"])
        self.assertTrue(rows[0].forecast_present)
        self.assertFalse(rows[1].weather_area_present)
        self.assertFalse(rows[1].temperature_area_present)
        self.assertFalse(rows[1].observation_station_present)

    def test_forecast_missing_but_observation_present_and_reverse(self):
        values = forecast_values()
        values[0]["timeSeries"][2]["areas"].append(
            {"area": {"code": "99999", "name": "Synthetic forecast-only point"}, "temps": ["1", "2"]})
        rows = short_candidates(forecast(values), catalog(), observations(), "130030", report_index=0)
        self.assertTrue(rows[1].forecast_present)
        self.assertFalse(rows[1].observation_station_present)
        values[0]["timeSeries"][2]["areas"][0] = {
            "area": {"code": "44263", "name": "Synthetic station with other forecast field"}, "pops": ["0", "0"]}
        row = short_candidates(forecast(values), catalog(), observations(), "130030", report_index=0)[0]
        self.assertTrue(row.temperature_area_present)
        self.assertFalse(row.temperature_field_present)
        self.assertTrue(row.observation_station_present)

    def test_unknown_region_does_not_choose_another(self):
        self.assertEqual(short_candidates(forecast(), catalog(), observations(), "999999", report_index=0), ())
        self.assertEqual(weekly_candidates(forecast(), catalog(), observations(), "999999", report_index=1), ())

    def test_missing_group_name_duplicate_points_and_dangling_candidate_reject(self):
        for change in ("name", "point", "candidate", "short", "weekly"):
            values = catalog_values()
            if change == "name":
                del values[3]["130100"]
            elif change == "point":
                values[0]["130000"][0]["amedas"].append("44263")
            elif change == "candidate":
                values[2]["130030"].append("999999")
            elif change == "short":
                values[0]["130000"].append(values[0]["130000"][0])
            else:
                values[1]["130000"].append(values[1]["130000"][0])
            with self.subTest(change=change), self.assertRaises(JMAError):
                catalog(values)

    def test_metadata_receipt_route_digest_and_origin_are_checked(self):
        pairs = [source(k, v) for k, v in zip(("short", "week", "candidates", "names"), catalog_values())]
        for bad in (replace(pairs[0][1], body_sha256="0" * 64), pairs[1][1]):
            with self.subTest(bad=bad), self.assertRaises(JMAError):
                parse_associations(pairs[0][0], bad, *(x for pair in pairs[1:] for x in pair))
        with self.assertRaises(JMAError):
            SourceReceipt.from_body(BASE + "/bosai/forecast/const/other.json", b"{}", NOW, NOW)


class TemperatureTests(unittest.TestCase):
    def project(self, data=None, *, hour=17, weekly=False, point="44263"):
        cat = catalog()
        return project_temperatures(forecast(data, hour), cat, observations(),
                                    cat.weekly[0] if weekly else cat.short[0], point,
                                    report_index=1 if weekly else 0)

    def test_17_roles_dates_missing_and_receipts_preserved(self):
        result = self.project()
        self.assertEqual(result.report_datetime, "2026-01-02T17:00:00+09:00")
        self.assertEqual(result.issued_utc, datetime(2026, 1, 2, 8, tzinfo=timezone.utc))
        self.assertEqual([s.role for s in result.slots], ["morning_minimum", "daytime_maximum"])
        self.assertEqual([s.target_date_jst for s in result.slots], [date(2026, 1, 3)] * 2)
        self.assertEqual(result.slots[0].value.raw, "")
        self.assertIsNone(result.slots[0].value.value)
        self.assertEqual(len(result.association_receipts), 4)

    def test_synthetic_05_11_roles_retain_unused_slot_and_actual_target_tokens(self):
        for hour in (5, 11):
            result = self.project(hour=hour)
            self.assertEqual([s.role for s in result.slots],
                             ["daytime_maximum", None, "morning_minimum", "daytime_maximum"])
            self.assertEqual(result.slots[1].value.raw, "-99")
            self.assertEqual(result.slots[1].source_time_define, "2026-01-02T18:00:00+09:00")
            self.assertEqual([s.target_date_jst for s in result.slots],
                             [date(2026, 1, 2)] * 2 + [date(2026, 1, 3)] * 2)

    def test_bucket_uses_jst_including_early_morning(self):
        for hour, expected in ((0, "17"), (4, "17"), (5, "05"), (10, "05"),
                               (11, "11"), (16, "11"), (17, "17"), (23, "17")):
            instant = datetime.fromisoformat(f"2026-01-02T{hour:02d}:00:00+09:00")
            self.assertEqual(issue_bucket(instant.astimezone(timezone.utc)), expected)

    def test_early_morning_17_bucket_keeps_local_date_guard_explicit(self):
        # This is synthetic. No actual before-05 report/target shape was captured.
        values = forecast_values()
        values[0]["reportDatetime"] = "2026-01-03T04:00:00+09:00"
        with self.assertRaisesRegex(JMAError, "target date"):
            self.project(values)
        values[0]["timeSeries"][2]["timeDefines"] = [
            "2026-01-04T00:00:00+09:00", "2026-01-04T09:00:00+09:00"]
        result = self.project(values)
        self.assertEqual(result.issue_bucket, "17")
        self.assertEqual(result.slots[0].target_date_jst, date(2026, 1, 4))

    def test_short_wrong_date_and_count_reject_instead_of_retime(self):
        for kind in ("date", "count"):
            values = forecast_values()
            series = values[0]["timeSeries"][2]
            if kind == "date":
                series["timeDefines"] = ["2026-01-04T00:00:00+09:00", "2026-01-04T09:00:00+09:00"]
            else:
                series["timeDefines"].append("2026-01-04T09:00:00+09:00")
                series["areas"][0]["temps"].append("1")
            with self.subTest(kind=kind), self.assertRaises(JMAError):
                self.project(values)

    def test_weekly_group_and_each_raw_field_has_own_dated_slots(self):
        result = self.project(weekly=True)
        self.assertEqual(result.association.week, "130100")
        self.assertEqual(result.temperature_point, "44263")
        self.assertEqual(result.report_datetime, "2026-01-02T11:00:00+09:00")
        self.assertIsNone(result.issue_bucket)
        self.assertEqual(len(result.slots), 6)
        self.assertEqual(result.slots[0].value.value, 0)
        self.assertEqual(result.slots[-1].role, "provider_tempsMinLower")
        self.assertIsNone(result.slots[-1].value.raw)

    def test_weekly_date_gaps_reject_without_invented_day(self):
        values = forecast_values()
        values[1]["timeSeries"][1]["timeDefines"][1] = "2026-01-05T00:00:00+09:00"
        with self.assertRaises(JMAError):
            self.project(values, weekly=True)

    def test_weekly_old_targets_reject_without_using_retrieval_clock(self):
        values = forecast_values()
        values[1]["timeSeries"][1]["timeDefines"] = [
            "2025-12-31T00:00:00+09:00", "2026-01-01T00:00:00+09:00"]
        with self.assertRaises(JMAError):
            self.project(values, weekly=True)

    def test_absent_explicit_point_never_chooses_first(self):
        with self.assertRaises(JMAError):
            self.project(point="99999")
        with self.assertRaises(JMAError):
            self.project(point="11111")

    def test_forecast_only_point_projects_with_observation_catalog_absence_retained(self):
        values = forecast_values()
        values[0]["timeSeries"][2]["areas"].append(
            {"area": {"code": "99999", "name": "Synthetic forecast-only point"}, "temps": ["1", "2"]})
        result = self.project(values, point="99999")
        self.assertEqual(result.temperature_point, "99999")
        self.assertFalse(result.observation_station_present)

    def test_association_office_catalog_and_report_are_explicit(self):
        cat, src, obs = catalog(), forecast(), observations()
        for assoc, index in ((replace(cat.short[0], office="100000"), 0),
                             (replace(cat.short[0], class20="9999999"), 0),
                             (cat.short[0], True), (cat.short[0], 20)):
            with self.subTest(assoc=assoc, index=index), self.assertRaises(JMAError):
                project_temperatures(src, cat, obs, assoc, "44263", report_index=index)


class HistoricalPrivateReplayTests(unittest.TestCase):
    def test_october_28_associations_and_actual_17_temperature_sample(self):
        initial = Path("private/forecast/jma-source-audit-20261028")
        added = Path("private/forecast/jma-association-audit-20261028")
        required = [(initial, "forecast-area-metadata"), (added, "week_area"),
                    (added, "week_area05"), (added, "week_area_name"),
                    (initial, "amedas-stations"), (initial, "forecast-tokyo")]
        if not all((p / (n + ".body")).is_file() and (p / (n + ".json")).is_file()
                   for p, n in required):
            self.skipTest("optional historical private JMA capture absent")
        inputs = []
        def capture_time(value):
            return (datetime.fromtimestamp(value, timezone.utc) if type(value) in (int, float)
                    else datetime.fromisoformat(value))
        for folder, name in required:
            body = (folder / (name + ".body")).read_bytes()
            meta = json.loads((folder / (name + ".json")).read_bytes())
            receipt = SourceReceipt(meta["url"], meta["body_sha256"], meta.get("body_bytes", meta.get("bytes")),
                capture_time(meta["retrieved_start_utc"]),
                capture_time(meta["retrieved_end_utc"]), meta["status"])
            inputs.append((body, receipt))
        cat = parse_associations(*(x for pair in inputs[:4] for x in pair))
        obs = parse_observation_catalog(*inputs[4])
        src = parse_forecast(*inputs[5])
        self.assertEqual((len(cat.short), len(cat.weekly), len(cat.candidates)), (142, 92, 142))
        self.assertEqual(len({a.office for a in cat.short}), 58)
        self.assertEqual(len({a.week for a in cat.weekly}), 91)
        self.assertEqual(sum(len(c.week_groups) > 1 for c in cat.candidates), 37)
        missing = sorted(p for a in cat.short for p in a.temperature_points if p not in obs.station_codes)
        self.assertEqual(missing, ["63576", "73136"])
        self.assertTrue(all(a.temperature_point in obs.station_codes for a in cat.weekly))
        candidates = weekly_candidates(src, cat, obs, "130030", report_index=1)
        self.assertEqual([a.association.week for a in candidates], ["130100", "130030"])
        self.assertEqual([a.forecast_present for a in candidates], [True, False])
        row = next(a for a in cat.short if a.office == "130000" and a.class10 == "130030")
        result = project_temperatures(src, cat, obs, row, "44263", report_index=0)
        self.assertEqual(result.report_datetime, "2026-10-27T17:00:00+09:00")
        self.assertEqual([s.target_date_jst for s in result.slots], [date(2026, 10, 28)] * 2)
        self.assertEqual([s.source_time_define[11:19] for s in result.slots], ["00:00:00", "09:00:00"])
        weekly = project_temperatures(src, cat, obs, candidates[0].association, "44263", report_index=1)
        self.assertEqual(weekly.association.name_en, "Izu Islands")
        self.assertEqual(len(weekly.slots), 42)
        self.assertEqual(weekly.slots[0].target_date_jst, date(2026, 10, 28))


if __name__ == "__main__":
    unittest.main()
