"""Synthetic source-contract tests; optional private captures make no live calls."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import unittest

from jwc24.jma_weather import (
    BASE, JMAError, MAX_BODY_BYTES, SourceReceipt, parse_forecast, parse_latest_time,
    parse_observations, parse_station, point_url, source_path, source_records_document,
)


NOW = datetime(2026, 1, 2, 5, tzinfo=timezone.utc)
FORECAST_URL = BASE + "/bosai/forecast/data/forecast/130000.json"
LATEST_URL = BASE + "/bosai/amedas/data/latest_time.txt"
STATIONS_URL = BASE + "/bosai/amedas/const/amedastable.json"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def receipt(url, body, ended=NOW):
    return SourceReceipt.from_body(url, body, ended - timedelta(seconds=1), ended)


def forecast_fixture():
    def report(issue):
        return {"publishingOffice": "Synthetic office", "reportDatetime": issue,
                "timeSeries": [{"timeDefines": ["2026-01-02T15:00:00+09:00", "2026-01-03T15:00:00+09:00"],
                    "areas": [{"area": {"code": "130010", "name": "Synthetic published area"},
                               "weatherCodes": ["100", "200"], "pops": ["0", ""],
                               "temps": ["-2", "12"], "winds": ["Source wind text", "Source wind text"]}]}]}
    return [report("2026-01-02T11:00:00+09:00"), report("2026-01-02T12:00:00+09:00")]


def station_fixture():
    return {"44132": {"type": "A", "elems": "11111111", "lat": [35, 30], "lon": [139, 30],
                       "alt": 20, "kjName": "Synthetic station", "knName": "Synthetic kana",
                       "enName": "Synthetic station"}}


def latest_fixture():
    body = b"2026-01-02T13:40:00+09:00\n"
    return parse_latest_time(body, receipt(LATEST_URL, body))


def station_record_fixture():
    return {"20260102133000": {"prefNumber": 44, "observationNumber": 132,
        "temp": [5.2, 0], "wind": [None, 6], "windDirection": [0, 0],
        "snow": [0, 6], "humidity": [None, 5], "precipitation10m": [0, 1],
        "maxTempTime": {"hour": 12, "minute": 10}}}


def station_object():
    body = encoded(station_fixture())
    return parse_station(body, receipt(STATIONS_URL, body), "44132")


def observations(data=None):
    latest = latest_fixture()
    body = encoded(station_record_fixture() if data is None else data)
    return parse_observations(body, receipt(point_url("44132", latest), body), station_object(), latest)


class SourceReceiptTests(unittest.TestCase):
    def test_exact_official_origin_and_reviewed_routes_only(self):
        for url in [FORECAST_URL, LATEST_URL, STATIONS_URL, point_url("44132", latest_fixture())]:
            self.assertTrue(source_path(url))
        for url in [FORECAST_URL.replace("https:", "http:"), FORECAST_URL + "?x=1", FORECAST_URL + "#x",
                    FORECAST_URL.replace("www.jma.go.jp", "www.jma.go.jp.example"),
                    FORECAST_URL.replace("www.jma.go.jp", "user@www.jma.go.jp"),
                    FORECAST_URL.replace("www.jma.go.jp", "www.jma.go.jp:443"),
                    FORECAST_URL.replace("130000", "../130000"), BASE + "/unreviewed"]:
            with self.subTest(url=url), self.assertRaises(JMAError):
                source_path(url)

    def test_hash_length_status_and_dates_are_validated(self):
        body = encoded(forecast_fixture())
        good = receipt(FORECAST_URL, body)
        for bad in [replace(good, body_sha256="0" * 64), replace(good, body_bytes=1),
                    replace(good, http_status=302), replace(good, retrieved_start_utc=NOW + timedelta(seconds=1))]:
            with self.subTest(bad=bad), self.assertRaises(JMAError):
                parse_forecast(body, bad)
        with self.assertRaises(JMAError):
            SourceReceipt.from_body(FORECAST_URL, b"x" * (MAX_BODY_BYTES + 1), NOW, NOW)
        with self.assertRaises(JMAError):
            SourceReceipt.from_body(FORECAST_URL, b"x", NOW.replace(tzinfo=None), NOW)

    def test_strict_json(self):
        for body in [b'[{"reportDatetime":1,"reportDatetime":2}]', b'[NaN]', b'[Infinity]', b'\xff']:
            with self.subTest(body=body), self.assertRaises(JMAError):
                parse_forecast(body, receipt(FORECAST_URL, body))

    def test_unknown_metadata_nonfinite_or_invalid_unicode_rejects_consistently(self):
        good = encoded(forecast_fixture())
        for token in [b'NaN', b'1e9999', b'"\\ud800"']:
            body = b'[{"unknownMetadata":' + token + b',' + good[2:]
            with self.subTest(token=token), self.assertRaises(JMAError):
                parse_forecast(body, receipt(FORECAST_URL, body))


class ForecastTests(unittest.TestCase):
    def parse(self, data):
        body = encoded(data)
        return parse_forecast(body, receipt(FORECAST_URL, body))

    def test_reports_keep_separate_issue_dates_and_future_targets(self):
        result = self.parse(forecast_fixture())
        self.assertNotEqual(result.reports[0].issued_utc, result.reports[1].issued_utc)
        self.assertGreater(result.reports[0].time_series[0].valid_times_utc[-1], NOW)
        self.assertEqual(result.office_code, "130000")
        area = result.reports[0].time_series[0].areas[0]
        self.assertEqual(area.code, "130010")
        self.assertEqual(area.fields[0].semantic, "JMA_weather_code")
        self.assertEqual(area.fields[0].values[0].value, "100")

    def test_empty_probability_is_missing_and_not_zero(self):
        result = self.parse(forecast_fixture())
        pops = result.reports[0].time_series[0].areas[0].fields[1]
        self.assertEqual(pops.values[0].value, 0)
        self.assertEqual(pops.values[1].raw, "")
        self.assertIsNone(pops.values[1].value)

    def test_provider_issue_required_and_no_later_than_retrieval(self):
        for bad in [None, "", "2026-01-02T12:00:00", "2026-01-03T12:00:00+09:00"]:
            data = forecast_fixture()
            data[0]["reportDatetime"] = bad
            with self.subTest(bad=bad), self.assertRaises(JMAError):
                self.parse(data)

    def test_old_reports_remain_dated_not_retimed(self):
        data = forecast_fixture()
        data[0]["reportDatetime"] = "2001-01-02T12:00:00+09:00"
        result = self.parse(data)
        self.assertEqual(result.reports[0].issued_utc.year, 2001)

    def test_target_shape_order_and_probabilities(self):
        mutations = [
            lambda s: s["timeDefines"].reverse(),
            lambda s: s["timeDefines"].__setitem__(1, s["timeDefines"][0]),
            lambda s: s["areas"][0]["pops"].append("10"),
            lambda s: s["areas"][0]["pops"].__setitem__(0, "101"),
            lambda s: s["areas"].append(s["areas"][0]),
            lambda s: s["areas"][0]["weatherCodes"].__setitem__(0, "native197"),
        ]
        for mutation in mutations:
            data = forecast_fixture()
            mutation(data[0]["timeSeries"][0])
            with self.subTest(mutation=mutation), self.assertRaises(JMAError):
                self.parse(data)

    def test_unmapped_fields_and_climatology_preserved(self):
        data = forecast_fixture()
        data[0]["tempAverage"] = {"areas": [{"min": "9.5", "max": "15.4"}]}
        data[0]["timeSeries"][0]["areas"][0]["newSourceField"] = ["opaque", ""]
        report = self.parse(data).reports[0]
        self.assertIn("tempAverage", json.loads(report.extra_metadata_json))
        field = report.time_series[0].areas[0].fields[-1]
        self.assertEqual(field.semantic, "unmapped_provider_field")
        self.assertIsNone(field.unit)


class ObservationTests(unittest.TestCase):
    def test_full_dates_station_identity_qc_and_units(self):
        data = observations()
        record = data.records[0]
        self.assertEqual(record.observed_utc, datetime(2026, 1, 2, 4, 30, tzinfo=timezone.utc))
        self.assertEqual(data.station.code, "44132")
        self.assertEqual(record.value("temp").unit, "degC")
        self.assertEqual(record.value("wind").unit, "m/s")
        self.assertIsNone(record.value("wind").raw_value)
        self.assertEqual(record.value("windDirection").raw_value, 0)
        self.assertEqual(record.value("snow").raw_value, 0)
        self.assertFalse(record.value("snow").normal_in_jma_client)
        self.assertEqual(record.value("precipitation10m").qualifier, ")")
        self.assertTrue(record.value("precipitation10m").normal_in_jma_client)
        self.assertFalse(record.value("precipitation10m").unqualified)
        self.assertIsNone(record.value("weather"))
        self.assertIsNone(record.value("uv"))
        self.assertEqual(json.loads(record.metadata_json)["maxTempTime"], {"hour": 12, "minute": 10})

    def test_qc_is_mandatory_and_supported(self):
        for value in [3, None, [3], [3, None], [3, 8], [3, True], [3, -1], [False, 0]]:
            data = station_record_fixture()
            data[next(iter(data))]["temp"] = value
            with self.subTest(value=value), self.assertRaises(JMAError):
                observations(data)

    def test_qc_qualifiers_not_erased(self):
        for qc in range(8):
            data = station_record_fixture()
            data[next(iter(data))]["temp"] = [2, qc]
            value = observations(data).records[0].value("temp")
            self.assertEqual(value.qc, qc)
            self.assertEqual(value.raw_value, 2)
            self.assertEqual(value.normal_in_jma_client, qc in (0, 1))

    def test_unknown_measurement_is_retained_without_invented_unit(self):
        data = station_record_fixture()
        data[next(iter(data))]["newSourceField"] = [12, 0]
        value = observations(data).records[0].value("newSourceField")
        self.assertEqual(value.raw_value, 12)
        self.assertFalse(value.supported_unit)
        self.assertIsNone(value.unit)

    def test_missing_station_or_coordinate_rejected(self):
        for data in [{}, {"44132": {**station_fixture()["44132"], "lat": [35, 60]}}]:
            body = encoded(data)
            with self.subTest(data=data), self.assertRaises(JMAError):
                parse_station(body, receipt(STATIONS_URL, body), "44132")

    def test_timeofday_future_or_wrong_station_rejected(self):
        for key in ["133000", "20260102135000", "20260102115900", "20260230133000"]:
            data = {key: next(iter(station_record_fixture().values()))}
            with self.subTest(key=key), self.assertRaises(JMAError):
                observations(data)
        data = station_record_fixture()
        data[next(iter(data))]["observationNumber"] = 133
        with self.assertRaises(JMAError):
            observations(data)

    def test_national_latest_not_an_issue_time_or_fetch_clock(self):
        latest = latest_fixture()
        self.assertEqual(latest.reported_datetime, "2026-01-02T13:40:00+09:00")
        self.assertNotEqual(latest.time_utc, NOW)
        body = b"2026-01-03T13:40:00+09:00"
        with self.assertRaises(JMAError):
            parse_latest_time(body, receipt(LATEST_URL, body))

    def test_derived_jst_window_and_explicit_station_only(self):
        self.assertTrue(point_url("44132", latest_fixture()).endswith("/44132/20260102_12.json"))
        with self.assertRaises(JMAError):
            point_url("nearest", latest_fixture())
        body = encoded(station_record_fixture())
        with self.assertRaises(JMAError):
            parse_observations(body, receipt(point_url("44133", latest_fixture()), body),
                               station_object(), latest_fixture())

    def test_jst_midnight_keeps_its_own_date_not_utc_date(self):
        body = b"2026-01-02T00:40:00+09:00"
        latest = parse_latest_time(body, receipt(LATEST_URL, body))
        self.assertEqual(latest.time_utc.day, 1)
        self.assertTrue(point_url("44132", latest).endswith("/20260102_00.json"))

    def test_export_is_source_records_not_native_weather(self):
        body = encoded(forecast_fixture())
        document = source_records_document(parse_forecast(body, receipt(FORECAST_URL, body)), observations())
        self.assertIsNone(document["native_location_mapping"])
        self.assertFalse(document["current_weather_inferred"])
        self.assertIn("not_native_forecast", document["record_type"])
        self.assertIn("processing_notice", document)
        self.assertEqual(document["observations"]["records"][0]["values"][0]["qc"], 0)
        json.dumps(document, allow_nan=False)


class PrivateActualCaptureTests(unittest.TestCase):
    def test_actual_jma_captures_if_available(self):
        folder = Path(__file__).resolve().parents[1] / "private/forecast/jma-source-audit-20261028"
        if not folder.exists():
            self.skipTest("private bounded JMA source captures are absent")
        names = ["forecast-page", "amedas-page", "forecast-tokyo", "amedas-latest", "amedas-stations",
                 "area-metadata", "amedas-explanation", "forecast-area-metadata", "amedas-point"]
        blobs = {}
        for name in names:
            body = (folder / (name + ".body")).read_bytes()
            meta = json.loads((folder / (name + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(meta["status"], 200)
            self.assertTrue(meta["complete_within_2mib"])
            self.assertEqual(len(body), meta["bytes"])
            self.assertLessEqual(len(body), MAX_BODY_BYTES)
            self.assertEqual(hashlib.sha256(body).hexdigest(), meta["body_sha256"])
            self.assertLessEqual(meta["retrieved_end_utc"] - meta["retrieved_start_utc"], 30)
            blobs[name] = (body, meta)

        def parsed_input(name):
            body, meta = blobs[name]
            return body, SourceReceipt.from_body(meta["url"], body,
                datetime.fromtimestamp(meta["retrieved_start_utc"], timezone.utc),
                datetime.fromtimestamp(meta["retrieved_end_utc"], timezone.utc))

        forecast = parse_forecast(*parsed_input("forecast-tokyo"))
        latest = parse_latest_time(*parsed_input("amedas-latest"))
        station_id = source_path(blobs["amedas-point"][1]["url"])[1][0]
        station = parse_station(*parsed_input("amedas-stations"), station_id)
        records = parse_observations(*parsed_input("amedas-point"), station, latest)
        self.assertGreater(len(forecast.reports), 0)
        self.assertGreater(len(records.records), 0)
        self.assertTrue(any(v.unit == "m/s" for r in records.records for v in r.values))
        self.assertTrue(any(not v.normal_in_jma_client for r in records.records for v in r.values))
        exported = source_records_document(forecast, records)
        self.assertIsNone(exported["native_location_mapping"])


if __name__ == "__main__":
    unittest.main()
