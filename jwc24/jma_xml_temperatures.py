"""Dated daily-temperature source records from official VPFD51 documents.

This independent XML contract does not broaden the JSON capture allowlist,
infer its array layout, assign native cities or create/publish native weather.
Receipts bind supplied bytes and metadata, not independent source authenticity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from .jma_weather import (
    JST, MAX_BODY_BYTES, JMAError, _iso, _number, _raw, _require, _text, utc_datetime,
)


REPORT_NS = "http://xml.kishou.go.jp/jmaxml1/"
HEAD_NS = REPORT_NS + "informationBasis1/"
BODY_NS = REPORT_NS + "body/meteorology1/"
ELEMENT_NS = REPORT_NS + "elementBasis1/"
_ROLES = {"日中の最高気温": "daytime_maximum", "最高気温": "maximum_temperature",
          "朝の最低気温": "morning_minimum"}


def document_office(url: str) -> str:
    _require(type(url) is str and len(url) <= 256
             and all(33 <= ord(c) <= 126 for c in url),
             "invalid VPFD51 source URL")
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise JMAError("invalid VPFD51 source URL") from exc
    match = re.fullmatch(r"/developer/xml/data/([0-9]{14})_([0-9]{1,8})_VPFD51_([0-9]{6})\.xml",
                         parsed.path)
    _require(parsed.scheme == "https" and parsed.netloc == "www.data.jma.go.jp"
             and not parsed.query and not parsed.fragment and match is not None,
             "source is not an exact official VPFD51 document route")
    try:
        datetime.strptime(match[1], "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise JMAError("invalid VPFD51 filename date") from exc
    # The filename is not substituted for any provider time field.
    return match[3]


@dataclass(frozen=True)
class XMLDocumentReceipt:
    url: str
    body_sha256: str
    body_bytes: int
    retrieved_start_utc: datetime
    retrieved_end_utc: datetime
    http_status: int = 200

    @classmethod
    def from_body(cls, url: str, body: bytes, started: datetime, ended: datetime,
                  *, status: int = 200) -> XMLDocumentReceipt:
        document_office(url)
        _require(type(body) is bytes and 0 < len(body) <= MAX_BODY_BYTES,
                 "VPFD51 body outside source byte bound")
        start, end = utc_datetime(started), utc_datetime(ended)
        _require(start <= end and type(status) is int and status == 200,
                 "invalid VPFD51 retrieval bounds or HTTP status")
        return cls(url, hashlib.sha256(body).hexdigest(), len(body), start, end, status)

    def verify(self, body: bytes) -> str:
        actual = type(self).from_body(self.url, body, self.retrieved_start_utc,
                                      self.retrieved_end_utc, status=self.http_status)
        _require(actual == self, "VPFD51 digest, length or retrieval metadata mismatch")
        return document_office(self.url)


def _safe_xml(body: bytes) -> ET.Element:
    try:
        text = body.decode("utf-8-sig")
        _require("\0" not in text, "NUL/UTF-16/UTF-32 outside UTF-8 XML contract")
        _require(not re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I),
                 "DTD and entity declarations are outside the source contract")
        declaration = re.match(r"<\?xml\b[^?]*\?>", text)
        if declaration:
            encoding = re.search(r"\bencoding\s*=\s*(['\"])(.*?)\1", declaration[0], re.I)
            _require(encoding is None or encoding[2].lower() == "utf-8",
                     "XML declaration must describe UTF-8")
        parser = ET.XMLPullParser(events=("start", "end"))
        depth, count, root = 0, 0, None
        for offset in range(0, len(text), 4096):
            parser.feed(text[offset:offset + 4096])
            for event, element in parser.read_events():
                if event == "start":
                    depth += 1
                    count += 1
                    if root is None:
                        root = element
                    _require(depth <= 64 and count <= 50000 and len(element.attrib) <= 32,
                             "XML structure exceeds local bounds")
                else:
                    _require(len(element.text or "") <= 16384 and len(element.tail or "") <= 16384,
                             "XML text exceeds local bounds")
                    depth -= 1
        parser.close()
        _require(root is not None and depth == 0, "incomplete XML document")
        _require(all(len(e.text or "") <= 16384 and len(e.tail or "") <= 16384 for e in root.iter()),
                 "XML final text exceeds local bounds")
        return root
    except (UnicodeError, ET.ParseError, RecursionError) as exc:
        raise JMAError("invalid bounded UTF-8 source XML") from exc


def _one(parent: ET.Element, tag: str, *, required: bool = True) -> ET.Element | None:
    found = parent.findall(tag)
    _require(len(found) == 1 if required else len(found) <= 1,
             "required XML element absent or duplicate element")
    return found[0] if found else None


def _value(parent: ET.Element, tag: str, *, required: bool = True) -> str | None:
    item = _one(parent, tag, required=required)
    if item is None:
        return None
    _require(len(item) == 0, "source scalar contains nested elements")
    return _text(item.text, 4096) if required else item.text


def _tree(element: ET.Element) -> dict:
    return {"tag": element.tag, "attributes": dict(element.attrib), "text": element.text,
            "children": [_tree(child) for child in element]}


@dataclass(frozen=True)
class XMLTimeDefinition:
    ref_id: str
    datetime: str
    valid_utc: datetime
    duration: str | None
    name: str | None
    raw_metadata_json: str

    @property
    def target_date_jst(self) -> date:
        return self.valid_utc.astimezone(JST).date()


@dataclass(frozen=True)
class XMLTemperatureValue:
    ref_id: str
    target: XMLTimeDefinition
    raw: str | None
    numeric_value: int | float | None
    raw_type: str | None
    raw_unit: str | None
    semantic_role: str | None
    attributes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class XMLTemperatureProperty:
    raw_type: str
    values: tuple[XMLTemperatureValue, ...]
    raw_metadata_json: str


@dataclass(frozen=True)
class XMLTemperaturePoint:
    station_code: str
    station_name: str
    properties: tuple[XMLTemperatureProperty, ...]
    station_metadata_json: str


@dataclass(frozen=True)
class XMLTemperatureSeries:
    source_series_index: int
    source_group_type: str | None
    time_definitions: tuple[XMLTimeDefinition, ...]
    points: tuple[XMLTemperaturePoint, ...]


@dataclass(frozen=True)
class XMLDailyTemperatureSource:
    office_code: str
    report_datetime: str
    issued_utc: datetime
    control_datetime: str
    transmitted_utc: datetime
    target_datetime: str
    target_utc: datetime
    publishing_office: str
    editorial_office: str
    status: str
    info_type: str
    info_kind_version: str
    series: tuple[XMLTemperatureSeries, ...]
    header_metadata_json: str
    receipt: XMLDocumentReceipt


def _time_definitions(series: ET.Element) -> tuple[XMLTimeDefinition, ...]:
    holder = _one(series, "{" + BODY_NS + "}TimeDefines")
    definitions, seen = [], set()
    for item in holder.findall("{" + BODY_NS + "}TimeDefine"):
        ref = item.get("timeId")
        _require(type(ref) is str and bool(re.fullmatch(r"[0-9]{1,6}", ref)) and ref not in seen,
                 "invalid or duplicate XML time definition ID")
        seen.add(ref)
        raw_time = _value(item, "{" + BODY_NS + "}DateTime")
        definitions.append(XMLTimeDefinition(ref, raw_time, _iso(raw_time),
            _value(item, "{" + BODY_NS + "}Duration", required=False),
            _value(item, "{" + BODY_NS + "}Name", required=False), _raw(_tree(item))))
    _require(0 < len(definitions) <= 128, "XML time-definition count outside bounds")
    # IDs bind values. Sorting by time would corrupt the actual 05/11 source order.
    return tuple(definitions)


def parse_daily_temperatures(body: bytes, receipt: XMLDocumentReceipt) -> XMLDailyTemperatureSource:
    _require(type(receipt) is XMLDocumentReceipt, "typed VPFD51 document receipt required")
    office = receipt.verify(body)
    root = _safe_xml(body)
    _require(root.tag == "{" + REPORT_NS + "}Report", "unexpected source report namespace")
    control = _one(root, "{" + REPORT_NS + "}Control")
    head = _one(root, "{" + HEAD_NS + "}Head")
    source_body = _one(root, "{" + BODY_NS + "}Body")
    _require(_value(control, "{" + REPORT_NS + "}Title") == "府県天気予報（Ｒ１）"
             and _value(head, "{" + HEAD_NS + "}InfoKind") == "府県天気予報",
             "XML source kind differs from VPFD51 daily forecast")
    report_raw = _value(head, "{" + HEAD_NS + "}ReportDateTime")
    control_raw = _value(control, "{" + REPORT_NS + "}DateTime")
    target_raw = _value(head, "{" + HEAD_NS + "}TargetDateTime")
    issued, transmitted, target = _iso(report_raw), _iso(control_raw), _iso(target_raw)
    _require(issued <= receipt.retrieved_end_utc and transmitted <= receipt.retrieved_end_utc,
             "XML report or transmission time is after retrieval under local acceptance policy")
    found, source_index = [], 0
    for group in source_body.findall("{" + BODY_NS + "}MeteorologicalInfos"):
        for series in group.findall("{" + BODY_NS + "}TimeSeriesInfo"):
            index = source_index
            source_index += 1
            items = series.findall("{" + BODY_NS + "}Item")
            properties = [p for item in items for p in item.findall("{" + BODY_NS + "}Kind/{" + BODY_NS + "}Property")]
            if not any(_value(p, "{" + BODY_NS + "}Type", required=False) in _ROLES for p in properties):
                continue
            definitions = _time_definitions(series)
            by_id = {t.ref_id: t for t in definitions}
            points, station_ids = [], set()
            for item in items:
                station = _one(item, "{" + BODY_NS + "}Station")
                code = _value(station, "{" + BODY_NS + "}Code")
                _require(bool(re.fullmatch(r"[0-9]{5}", code)) and code not in station_ids,
                         "invalid or duplicate forecast temperature station")
                station_ids.add(code)
                parsed_properties = []
                for prop in item.findall("{" + BODY_NS + "}Kind/{" + BODY_NS + "}Property"):
                    raw_type = _value(prop, "{" + BODY_NS + "}Type")
                    values, refs = [], set()
                    for value in prop.findall(".//{" + ELEMENT_NS + "}Temperature"):
                        _require(len(value) == 0, "temperature scalar contains nested elements")
                        ref = value.get("refID")
                        _require(ref in by_id and ref not in refs,
                                 "temperature has missing, dangling or duplicate refID")
                        refs.add(ref)
                        raw = value.text
                        _require(raw is None or len(raw) <= 512, "temperature token outside bounds")
                        number = None
                        if raw is not None and re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw):
                            number = _number(float(raw) if "." in raw else int(raw))
                        mapped_role = _ROLES.get(raw_type) if value.get("type") == raw_type else None
                        values.append(XMLTemperatureValue(ref, by_id[ref], raw, number,
                            value.get("type"), value.get("unit"), mapped_role, tuple(value.attrib.items())))
                    parsed_properties.append(XMLTemperatureProperty(raw_type, tuple(values), _raw(_tree(prop))))
                points.append(XMLTemperaturePoint(code, _value(station, "{" + BODY_NS + "}Name"),
                                                   tuple(parsed_properties), _raw(_tree(station))))
            _require(0 < len(points) <= 256, "daily temperature station count outside bounds")
            found.append(XMLTemperatureSeries(index, group.get("type"), definitions, tuple(points)))
    _require(0 < len(found) <= 32, "no reviewed daily temperature series or too many series")
    return XMLDailyTemperatureSource(office, report_raw, issued, control_raw, transmitted,
        target_raw, target, _value(control, "{" + REPORT_NS + "}PublishingOffice"),
        _value(control, "{" + REPORT_NS + "}EditorialOffice"),
        _value(control, "{" + REPORT_NS + "}Status"), _value(head, "{" + HEAD_NS + "}InfoType"),
        _value(head, "{" + HEAD_NS + "}InfoKindVersion"), tuple(found),
        _raw({"control": _tree(control), "head": _tree(head)}), receipt)
