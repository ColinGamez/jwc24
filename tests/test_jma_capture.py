"""Bounded immutable acquisition tests; all transports are offline substitutes."""

from dataclasses import replace
from datetime import timedelta
from email.message import Message
import http.client
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24.jma_capture import CapturedResource, capture_bundle, fetch_resource, _NoRedirect
from jwc24.jma_weather import JMAError, MAX_BODY_BYTES, point_url
from tests.test_jma_weather import (
    FORECAST_URL, LATEST_URL, STATIONS_URL, NOW, encoded, forecast_fixture,
    latest_fixture, station_fixture, station_record_fixture,
)


class FakeResponse:
    def __init__(self, url=FORECAST_URL, body=b"{}", status=200, headers=None):
        self.url, self.body, self.code = url, body, status
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self.offset, self.closed, self.timeouts = 0, False, []
        self.fp = self
        self.raw = self
        self._sock = self

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def read1(self, count):
        data = self.body[self.offset:self.offset + count]
        self.offset += len(data)
        if not data:
            self.fp = None
        return data

    def geturl(self):
        return self.url

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, response):
        self.response, self.requests = response, []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.response


class TransportTests(unittest.TestCase):
    def fetch(self, response):
        opener = FakeOpener(response)
        with patch("jwc24.jma_capture.urllib.request.build_opener", return_value=opener):
            capture = fetch_resource(FORECAST_URL)
        return capture, opener

    def test_single_get_no_credentials_cookie_or_redirect(self):
        response = FakeResponse(body=b"{}", headers={"Content-Length": "2"})
        capture, opener = self.fetch(response)
        self.assertTrue(capture.complete)
        self.assertIsNone(capture.failure)
        self.assertEqual(capture.body, b"{}")
        self.assertEqual(capture.receipt().body_bytes, 2)
        self.assertEqual(len(opener.requests), 1)
        req, timeout = opener.requests[0]
        self.assertEqual(timeout, 30)
        self.assertEqual(req.get_method(), "GET")
        self.assertFalse(any(k.lower() in {"cookie", "authorization"} for k in req.headers))
        self.assertTrue(all(0 < t <= 30 for t in response.timeouts))
        self.assertTrue(response.closed)
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, None, None, "https://example.org"))

    def test_exact_body_limit_accepts_and_one_extra_byte_rejects(self):
        capture, _ = self.fetch(FakeResponse(body=b"x" * MAX_BODY_BYTES))
        self.assertTrue(capture.complete)
        capture, _ = self.fetch(FakeResponse(body=b"x" * (MAX_BODY_BYTES + 100)))
        self.assertFalse(capture.complete)
        self.assertEqual(len(capture.body), MAX_BODY_BYTES + 1)
        with self.assertRaises(JMAError):
            capture.receipt()

    def test_redirect_non200_compression_length_and_header_bounds_reject(self):
        cases = [FakeResponse(status=302, headers={"Location": "https://example.org"}),
                 FakeResponse(status=500), FakeResponse(url="https://example.org"),
                 FakeResponse(headers={"Content-Encoding": "gzip"}),
                 FakeResponse(headers={"Content-Length": "999"}),
                 FakeResponse(headers={"X-Large": "x" * 65537})]
        for response in cases:
            capture, _ = self.fetch(response)
            with self.subTest(status=response.code), self.assertRaises(JMAError):
                capture.receipt()
            self.assertTrue(response.closed)

    def test_wall_deadline_rejects_even_with_small_body(self):
        opener = FakeOpener(FakeResponse())
        with patch("jwc24.jma_capture.urllib.request.build_opener", return_value=opener), \
                patch("jwc24.jma_capture.time.monotonic", side_effect=[100, 131]):
            capture = fetch_resource(FORECAST_URL)
        self.assertFalse(capture.complete)
        self.assertEqual(capture.failure, "deadline_exceeded")

    def test_bad_origin_rejects_before_transport(self):
        with patch("jwc24.jma_capture.urllib.request.build_opener") as transport:
            with self.assertRaises(JMAError):
                fetch_resource(FORECAST_URL.replace("www.jma.go.jp", "example.org"))
            transport.assert_not_called()

    def test_malformed_http_response_is_a_failed_capture(self):
        with patch("jwc24.jma_capture.urllib.request.build_opener") as factory:
            factory.return_value.open.side_effect = http.client.BadStatusLine("malformed")
            result = fetch_resource(FORECAST_URL)
        self.assertFalse(result.complete)
        self.assertEqual(result.failure, "transport_failed")

    def test_response_closing_fp_after_content_length_is_complete(self):
        class AutoClosingResponse(FakeResponse):
            def read1(self, count):
                chunk = super().read1(count)
                if self.offset == len(self.body):
                    self.fp = None
                return chunk
        capture, _ = self.fetch(AutoClosingResponse(headers={"Content-Length": "2"}))
        self.assertTrue(capture.complete)


class BundleTests(unittest.TestCase):
    def fixtures(self):
        return {
            FORECAST_URL: encoded(forecast_fixture()),
            LATEST_URL: b"2026-01-02T13:40:00+09:00",
            STATIONS_URL: encoded(station_fixture()),
            point_url("44132", latest_fixture()): encoded(station_record_fixture()),
        }

    def transport(self, fixtures, requested, alter=None):
        def run(url):
            requested.append(url)
            result = CapturedResource(url, fixtures[url], (("Date", "not a provider issue date"),),
                                      200, NOW - timedelta(seconds=1), NOW, True)
            return alter(result) if alter else result
        return run

    def test_four_explicit_resources_originals_and_typed_export(self):
        fixtures, requested = self.fixtures(), []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            result = capture_bundle(output, office_code="130000", station_code="44132",
                transport=self.transport(fixtures, requested))
            self.assertTrue(result["complete"])
            self.assertEqual(requested, list(fixtures))
            self.assertFalse(result["native_payload_written"])
            for resource in result["resources"]:
                meta = json.loads((output / resource["metadata"]).read_text(encoding="utf-8"))
                self.assertEqual((output / resource["body"]).read_bytes(), fixtures[meta["url"]])
            records = json.loads((output / "source-records.json").read_text(encoding="utf-8"))
            self.assertIsNone(records["native_location_mapping"])
            self.assertEqual(records["forecast"]["reports"][0]["report_datetime"],
                             forecast_fixture()[0]["reportDatetime"])
            self.assertFalse(records["current_weather_inferred"])
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with self.assertRaises(FileExistsError):
                capture_bundle(output, office_code="130000", station_code="44132", transport=lambda _: self.fail())
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_parse_failure_preserves_original_and_stops_no_records(self):
        fixtures, requested = self.fixtures(), []
        fixtures[FORECAST_URL] = b"not JSON"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            result = capture_bundle(output, office_code="130000", station_code="44132",
                                    transport=self.transport(fixtures, requested))
            self.assertFalse(result["complete"])
            self.assertEqual(len(requested), 1)
            self.assertEqual((output / "forecast.body").read_bytes(), b"not JSON")
            self.assertFalse((output / "source-records.json").exists())
            self.assertFalse(json.loads((output / "manifest.json").read_text())["complete"])

    def test_transport_failure_keeps_partial_evidence(self):
        requested = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            result = capture_bundle(output, office_code="130000", station_code="44132",
                transport=self.transport(self.fixtures(), requested,
                    lambda r: replace(r, complete=False, failure="deadline_exceeded")))
            self.assertFalse(result["complete"])
            self.assertEqual(len(requested), 1)
            self.assertTrue((output / "forecast.body").exists())

    def test_mid_export_failure_leaves_no_accepted_or_pending_record_file(self):
        original_dump = json.dump

        def fail_mid_export(data, stream, **kwargs):
            if data.get("record_type") == "JMA_source_records_not_native_forecast":
                stream.write('{"partial":')
                raise OSError("simulated disk write failure")
            return original_dump(data, stream, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            with patch("jwc24.jma_capture.json.dump", side_effect=fail_mid_export):
                result = capture_bundle(output, office_code="130000", station_code="44132",
                                        transport=self.transport(self.fixtures(), []))
            self.assertFalse(result["complete"])
            self.assertEqual(len(result["resources"]), 4)
            self.assertFalse((output / "source-records.json").exists())
            self.assertFalse((output / "source-records.pending").exists())
            self.assertTrue((output / "point.body").exists())
            self.assertFalse(json.loads((output / "manifest.json").read_text())["complete"])

    def test_supplied_transport_cannot_bypass_elapsed_acceptance_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            result = capture_bundle(Path(directory) / "failed", office_code="130000", station_code="44132",
                transport=self.transport(self.fixtures(), [],
                    lambda r: replace(r, started_utc=NOW - timedelta(seconds=31))))
            self.assertFalse(result["complete"])
            self.assertEqual(len(result["resources"]), 1)

    def test_station_absent_does_not_guess_nearest_or_fetch_point(self):
        fixtures, requested = self.fixtures(), []
        fixtures[STATIONS_URL] = b"{}"
        with tempfile.TemporaryDirectory() as directory:
            result = capture_bundle(Path(directory) / "failed", office_code="130000", station_code="44132",
                                    transport=self.transport(fixtures, requested))
            self.assertFalse(result["complete"])
            self.assertEqual(len(requested), 3)

    def test_invalid_ids_make_no_directory_and_no_request(self):
        with tempfile.TemporaryDirectory() as directory:
            for office, station in [("nearest", "44132"), ("130000", "city"), ("../130", "44132")]:
                output = Path(directory) / "invalid"
                with self.assertRaises(JMAError):
                    capture_bundle(output, office_code=office, station_code=station, transport=lambda _: self.fail())
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
