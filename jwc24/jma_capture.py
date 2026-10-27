"""Explicit, bounded acquisition of one JMA office and one selected station.

No provider activation, native location assignment, signing, task or profile writes.
Raw evidence is created exclusively in a new directory, including on failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import re
import time
from typing import Callable
import urllib.error
import urllib.request

from jwc24.jma_weather import (
    BASE, MAX_BODY_BYTES, JMAError, SourceReceipt, parse_forecast, parse_latest_time,
    parse_observations, parse_station, point_url, source_path, source_records_document,
    utc_datetime,
)


TIMEOUT_SECONDS = 30
MAX_HEADER_BYTES = 65536


@dataclass(frozen=True)
class CapturedResource:
    url: str
    body: bytes
    headers: tuple[tuple[str, str], ...]
    status: int
    started_utc: datetime
    ended_utc: datetime
    complete: bool
    failure: str | None = None

    def receipt(self) -> SourceReceipt:
        if not self.complete or self.failure:
            raise JMAError("capture did not finish within its bounds")
        if not 0 <= (utc_datetime(self.ended_utc) - utc_datetime(self.started_utc)).total_seconds() <= TIMEOUT_SECONDS:
            raise JMAError("capture retrieval interval exceeds its acceptance deadline")
        if sum(len(k.encode("utf-8")) + len(v.encode("utf-8")) for k, v in self.headers) > MAX_HEADER_BYTES:
            raise JMAError("capture headers exceed the evidence bound")
        return SourceReceipt.from_body(self.url, self.body, self.started_utc,
                                       self.ended_utc, status=self.status)

    def metadata(self) -> dict:
        return {
            "url": self.url, "status": self.status, "headers": [list(h) for h in self.headers],
            "retrieved_start_utc": self.started_utc.isoformat(),
            "retrieved_end_utc": self.ended_utc.isoformat(),
            "body_sha256": hashlib.sha256(self.body).hexdigest(), "body_bytes": len(self.body),
            "complete": self.complete, "failure": self.failure,
            "maximum_body_bytes": MAX_BODY_BYTES, "timeout_seconds": TIMEOUT_SECONDS,
            "redirects_followed": 0, "authentication_supplied": False,
            "http_dates_used_as_provider_times": False,
        }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_resource(url: str) -> CapturedResource:
    """One official HTTPS request, no retries, cookies, auth or redirects.

    The acceptance deadline covers connection plus body reads. Socket timeouts
    are reduced before every read; an elapsed deadline rejects. OS DNS resolution
    may return after the deadline, but such a response cannot become accepted.
    No compressed response is decoded behind the raw-byte size bound.
    """
    source_path(url)
    start = datetime.now(timezone.utc)
    deadline = time.monotonic() + TIMEOUT_SECONDS
    body, headers, status = bytearray(), (), 0
    failure = None
    complete = False
    response = None
    try:
        request = urllib.request.Request(url, headers={
            "User-Agent": "JWC24-JMA-source-audit/1", "Accept-Encoding": "identity",
            "Accept": "application/json,text/plain;q=0.9",
        })
        # This opener has no CookieProcessor, HTTP auth handler or redirect following.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            response = opener.open(request, timeout=TIMEOUT_SECONDS)
        except urllib.error.HTTPError as exc:
            response = exc
        status = response.code
        headers = tuple((str(k), str(v)) for k, v in response.headers.items())
        if sum(len(k.encode("utf-8")) + len(v.encode("utf-8")) for k, v in headers) > MAX_HEADER_BYTES:
            raise JMAError("response headers exceed bound")
        if response.geturl() != url:
            raise JMAError("response URL changed")
        if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
            raise JMAError("compressed response outside raw capture contract")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            # HTTPResponse.read1 performs at most one underlying buffered read.
            if response.fp is None:
                chunk = b""
            else:
                response.fp.raw._sock.settimeout(remaining)
                chunk = response.read1(min(65536, MAX_BODY_BYTES + 1 - len(body)))
            if time.monotonic() > deadline:
                raise TimeoutError
            body.extend(chunk)
            if len(body) > MAX_BODY_BYTES:
                raise JMAError("response body exceeds bound")
            if not chunk:
                break
        length = response.headers.get("Content-Length")
        if length is not None and (not re.fullmatch(r"[0-9]+", length) or int(length) != len(body)):
            raise JMAError("response body length differs from Content-Length")
        complete = True
        if status != 200:
            failure = "non_200_status"
    except TimeoutError:
        failure = "deadline_exceeded"
    except JMAError:
        failure = "capture_bounds_or_transport_contract"
    except (OSError, urllib.error.URLError, http.client.HTTPException, AttributeError, ValueError):
        failure = "transport_failed"
    finally:
        if response is not None:
            try:
                response.close()
            except OSError:
                pass
    return CapturedResource(url, bytes(body), headers, status, start,
                            datetime.now(timezone.utc), complete, failure)


def _write_json(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def _publish_records(output: Path, records: dict) -> None:
    """An interrupted export can never have the accepted record filename."""
    pending = output / "source-records.pending"
    destination = output / "source-records.json"
    owned_pending = False
    try:
        with pending.open("x", encoding="utf-8", newline="\n") as stream:
            owned_pending = True
            json.dump(records, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
        if destination.exists():
            raise FileExistsError(destination)
        pending.rename(destination)
        owned_pending = False
    finally:
        if owned_pending:
            pending.unlink(missing_ok=True)


def capture_bundle(output_directory: Path, *, office_code: str, station_code: str,
                   transport: Callable[[str], CapturedResource] = fetch_resource) -> dict:
    """Create a new four-resource bundle and typed source-record export.

    Codes are explicit JMA identities, never nearest-city choices. The injectable
    transport supports offline verification; it does not authenticate evidence.
    Existing paths reject. Failed bundles retain captured originals and a failure
    manifest; they have no source-record output and are never active weather.
    """
    if not isinstance(office_code, str) or not re.fullmatch(r"[0-9]{6}", office_code):
        raise JMAError("an explicit six-digit office code is required")
    if not isinstance(station_code, str) or not re.fullmatch(r"[0-9]{5}", station_code):
        raise JMAError("an explicit five-digit station code is required")
    output = Path(output_directory)
    output.mkdir(parents=False, exist_ok=False)
    resources = []
    manifest = {
        "schema_version": 1, "record_type": "JMA_capture_bundle_not_native_forecast",
        "office_code": office_code, "station_code": station_code, "resources": resources,
        "complete": False, "failure": None, "native_payload_written": False,
        "native_location_mapping": None, "provider_activated": False,
        "acquisition_mode": "official_get" if transport is fetch_resource else "supplied_transport",
        "evidence_independently_authenticated": False,
    }

    def acquire(name: str, url: str) -> tuple[bytes, SourceReceipt]:
        source_path(url)
        captured = transport(url)
        if not isinstance(captured, CapturedResource) or captured.url != url:
            raise JMAError("transport returned a different source")
        # Do not let a custom transport bypass the bounds of the real one.
        if type(captured.body) is not bytes or len(captured.body) > MAX_BODY_BYTES + 1:
            raise JMAError("transport body exceeds evidence storage bound")
        with (output / (name + ".body")).open("xb") as stream:
            stream.write(captured.body)
        _write_json(output / (name + ".json"), captured.metadata())
        resources.append({"name": name, "metadata": name + ".json", "body": name + ".body"})
        return captured.body, captured.receipt()

    try:
        body, receipt = acquire("forecast", BASE + "/bosai/forecast/data/forecast/" + office_code + ".json")
        forecast = parse_forecast(body, receipt)
        body, receipt = acquire("latest", BASE + "/bosai/amedas/data/latest_time.txt")
        latest = parse_latest_time(body, receipt)
        body, receipt = acquire("stations", BASE + "/bosai/amedas/const/amedastable.json")
        station = parse_station(body, receipt, station_code)
        body, receipt = acquire("point", point_url(station_code, latest))
        observations = parse_observations(body, receipt, station, latest)
        records = source_records_document(forecast, observations)
        _publish_records(output, records)
        manifest["complete"] = True
    except (JMAError, OSError, ValueError, TypeError, OverflowError):
        manifest["failure"] = "source_acquisition_or_parse_failed"
    finally:
        _write_json(output / "manifest.json", manifest)
    return manifest
