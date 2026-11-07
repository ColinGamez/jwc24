"""Synthetic VPFD51 source-contract tests and optional real 05/11 replay."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from jwc24.jma_weather import JMAError, MAX_BODY_BYTES, source_path
from jwc24.jma_xml_temperatures import (
    BODY_NS, ELEMENT_NS, HEAD_NS, REPORT_NS, XMLDocumentReceipt,
    document_office, parse_daily_temperatures,
)


URL = "https://www.data.jma.go.jp/developer/xml/data/20260102013843_0_VPFD51_130000.xml"
NOW = datetime(2026, 1, 2, 5, tzinfo=timezone.utc)


def fixture():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<Report xmlns="http://xml.kishou.go.jp/jmaxml1/"
 xmlns:jmx_eb="http://xml.kishou.go.jp/jmaxml1/elementBasis1/">
 <Control><Title>府県天気予報（Ｒ１）</Title><DateTime>2026-01-02T01:38:43Z</DateTime>
 <Status>通常</Status><EditorialOffice>Synthetic editorial office</EditorialOffice>
 <PublishingOffice>Synthetic publishing office</PublishingOffice></Control>
 <Head xmlns="http://xml.kishou.go.jp/jmaxml1/informationBasis1/">
 <ReportDateTime>2026-01-02T11:00:00+09:00</ReportDateTime>
 <TargetDateTime>2026-01-02T11:00:00+09:00</TargetDateTime>
 <InfoType>発表</InfoType><InfoKind>府県天気予報</InfoKind><InfoKindVersion>1.0_1</InfoKindVersion>
 </Head><Body xmlns="http://xml.kishou.go.jp/jmaxml1/body/meteorology1/">
 <MeteorologicalInfos type="地点予報"><TimeSeriesInfo><TimeDefines>
 <TimeDefine timeId="1"><DateTime>2026-01-02T09:00:00+09:00</DateTime><Duration>PT9H</Duration><Name>今日の日中</Name></TimeDefine>
 <TimeDefine timeId="2"><DateTime>2026-01-02T00:00:00+09:00</DateTime><Duration>PT24H</Duration><Name>今日</Name></TimeDefine>
 <TimeDefine timeId="3"><DateTime>2026-01-03T00:00:00+09:00</DateTime><Duration>PT9H</Duration><Name>明日の朝</Name></TimeDefine>
 <TimeDefine timeId="4"><DateTime>2026-01-03T09:00:00+09:00</DateTime><Duration>PT9H</Duration><Name>明日の日中</Name></TimeDefine>
 </TimeDefines><Item><Kind>
 <Property><Type>日中の最高気温</Type><TemperaturePart><jmx_eb:Temperature refID="1" type="日中の最高気温" unit="度">0</jmx_eb:Temperature></TemperaturePart></Property>
 <Property><Type>最高気温</Type><TemperaturePart><jmx_eb:Temperature refID="2" type="最高気温" unit="度">1</jmx_eb:Temperature></TemperaturePart></Property>
 <Property><Type>朝の最低気温</Type><TemperaturePart><jmx_eb:Temperature refID="3" type="朝の最低気温" unit="度">-2</jmx_eb:Temperature></TemperaturePart></Property>
 <Property><Type>日中の最高気温</Type><TemperaturePart><jmx_eb:Temperature refID="4" type="日中の最高気温" unit="度">5</jmx_eb:Temperature></TemperaturePart></Property>
 </Kind><Station><Name>Synthetic forecast point</Name><Code>00001</Code></Station></Item>
 </TimeSeriesInfo></MeteorologicalInfos>
 <MeteorologicalInfos type="地点予報"><TimeSeriesInfo><TimeDefines>
 <TimeDefine timeId="1"><DateTime>2026-01-02T12:00:00+09:00</DateTime></TimeDefine>
 </TimeDefines><Item><Kind><Property><Type>３時間毎気温</Type><TemperaturePart>
 <jmx_eb:Temperature refID="1" type="気温" unit="度">99</jmx_eb:Temperature>
 </TemperaturePart></Property></Kind><Station><Name>Synthetic forecast point</Name><Code>00001</Code></Station></Item>
 </TimeSeriesInfo></MeteorologicalInfos></Body></Report>'''.encode("utf-8")


def receipt(body, *, url=URL):
    return XMLDocumentReceipt.from_body(url, body, NOW - timedelta(seconds=1), NOW)


def parse(body=None):
    body = fixture() if body is None else body
    return parse_daily_temperatures(body, receipt(body))


def edit(mutator):
    root = ET.fromstring(fixture())
    mutator(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def first_series(root):
    return root.find(".//{" + BODY_NS + "}TimeSeriesInfo")


def first_temperature(root):
    return root.find(".//{" + ELEMENT_NS + "}Temperature")


class XMLReceiptTests(unittest.TestCase):
    def test_exact_official_document_route_is_separate_from_existing_json_allowlist(self):
        self.assertEqual(document_office(URL), "130000")
        with self.assertRaises(JMAError):
            source_path(URL)
        for bad in (URL.replace("https:", "http:"), URL + "?x=1", URL + "#x",
                    URL.replace("www.data.jma.go.jp", "www.data.jma.go.jp.example"),
                    URL.replace("www.data.jma.go.jp", "user@www.data.jma.go.jp"),
                    URL.replace("www.data.jma.go.jp", "www.data.jma.go.jp:443"),
                    URL.replace("VPFD51", "VPFW50"), URL.replace("20260102", "20260230"),
                    URL.replace("130000", "13000"), URL.replace("/data/", "/data/../data/"),
                    "\n" + URL, " " + URL, URL + "\r", URL.replace("developer", "deve\tloper"),
                    URL.replace("developer", "deve\x00loper"), URL.replace("developer", "deve\x7floper")):
            with self.subTest(url=bad), self.assertRaises(JMAError):
                document_office(bad)

    def test_digest_length_status_and_interval_mismatch_reject(self):
        body = fixture()
        original = receipt(body)
        for change in ({"body_sha256": "0" * 64}, {"body_bytes": 1}, {"http_status": 302},
                       {"retrieved_start_utc": NOW + timedelta(seconds=1)}):
            with self.subTest(change=change), self.assertRaises(JMAError):
                parse_daily_temperatures(body, replace(original, **change))

    def test_empty_oversized_and_naive_receipts_reject(self):
        for body in (b"", b"x" * (MAX_BODY_BYTES + 1)):
            with self.assertRaises(JMAError):
                receipt(body)
        with self.assertRaises(JMAError):
            XMLDocumentReceipt.from_body(URL, fixture(), NOW.replace(tzinfo=None), NOW)


class XMLTemperatureTests(unittest.TestCase):
    def test_nonmonotonic_definition_order_and_each_refid_role_remain(self):
        source = parse()
        self.assertEqual(len(source.series), 1)  # 3-hour temperature series is separate.
        series = source.series[0]
        self.assertEqual([d.ref_id for d in series.time_definitions], ["1", "2", "3", "4"])
        self.assertGreater(series.time_definitions[0].valid_utc, series.time_definitions[1].valid_utc)
        values = [v for p in series.points[0].properties for v in p.values]
        self.assertEqual([v.numeric_value for v in values], [0, 1, -2, 5])
        self.assertEqual([v.semantic_role for v in values],
                         ["daytime_maximum", "maximum_temperature", "morning_minimum", "daytime_maximum"])
        self.assertEqual([v.target.duration for v in values], ["PT9H", "PT24H", "PT9H", "PT9H"])
        self.assertEqual(values[2].target.target_date_jst, date(2026, 1, 3))
        self.assertEqual(values[0].raw_unit, "度")
        self.assertFalse(hasattr(source, "native_location"))

    def test_issue_transmission_target_and_receipt_are_separate(self):
        source = parse()
        self.assertEqual(source.report_datetime, "2026-01-02T11:00:00+09:00")
        self.assertEqual(source.control_datetime, "2026-01-02T01:38:43Z")
        self.assertGreater(source.issued_utc, source.transmitted_utc)
        self.assertEqual(source.target_datetime, source.report_datetime)
        self.assertNotEqual(source.issued_utc, source.receipt.retrieved_end_utc)
        self.assertEqual(source.series[0].points[0].station_code, "00001")

    def test_unknown_and_absent_tokens_are_retained_without_becoming_numeric_zero(self):
        for token in (None, "", "unknown", "NaN", "1e999"):
            body = edit(lambda root: setattr(first_temperature(root), "text", token))
            value = parse(body).series[0].points[0].properties[0].values[0]
            self.assertIsNone(value.numeric_value)
            self.assertEqual(value.raw, None if token == "" else token)

    def test_absent_temperature_element_is_an_empty_property_not_a_synthetic_reading(self):
        def remove(root):
            part = root.find(".//{" + BODY_NS + "}TemperaturePart")
            part.remove(part[0])
        prop = parse(edit(remove)).series[0].points[0].properties[0]
        self.assertEqual(prop.values, ())

    def test_unknown_type_unit_and_qualifier_attributes_remain_unmapped(self):
        def change(root):
            value = first_temperature(root)
            value.set("type", "Future source type")
            value.set("unit", "Future unit")
            value.set("condition", "Future qualifier")
        value = parse(edit(change)).series[0].points[0].properties[0].values[0]
        self.assertIsNone(value.semantic_role)
        self.assertEqual((value.raw_type, value.raw_unit), ("Future source type", "Future unit"))
        self.assertIn(("condition", "Future qualifier"), value.attributes)

    def test_dangling_missing_duplicate_refid_and_duplicate_definitions_reject(self):
        def duplicate_ref(root):
            part = root.find(".//{" + BODY_NS + "}TemperaturePart")
            part.append(ET.fromstring(ET.tostring(part[0])))
        def duplicate_def(root):
            holder = first_series(root).find("{" + BODY_NS + "}TimeDefines")
            holder.append(ET.fromstring(ET.tostring(holder[0])))
        for mutator in (lambda r: first_temperature(r).set("refID", "99"),
                        lambda r: first_temperature(r).attrib.pop("refID"),
                        duplicate_ref, duplicate_def):
            with self.subTest(mutator=mutator), self.assertRaises(JMAError):
                parse(edit(mutator))

    def test_definition_order_not_value_order_controls_binding(self):
        def reverse(root):
            holder = first_series(root).find("{" + BODY_NS + "}TimeDefines")
            holder[:] = list(reversed(holder[:]))
        series = parse(edit(reverse)).series[0]
        value = series.points[0].properties[0].values[0]
        self.assertEqual(series.time_definitions[0].ref_id, "4")
        self.assertEqual(value.target.ref_id, "1")
        self.assertEqual(value.target.datetime, "2026-01-02T09:00:00+09:00")

    def test_duplicate_station_or_header_scalars_reject(self):
        def duplicate_station(root):
            series = first_series(root)
            series.append(ET.fromstring(ET.tostring(series.find("{" + BODY_NS + "}Item"))))
        def duplicate_date(root):
            head = root.find("{" + HEAD_NS + "}Head")
            head.append(ET.fromstring(ET.tostring(head.find("{" + HEAD_NS + "}ReportDateTime"))))
        for mutator in (duplicate_station, duplicate_date):
            with self.assertRaises(JMAError):
                parse(edit(mutator))

    def test_future_report_or_transmission_rejects_but_future_targets_remain(self):
        for namespace, name in ((HEAD_NS, "ReportDateTime"), (REPORT_NS, "DateTime")):
            body = edit(lambda root: setattr(root.find(".//{" + namespace + "}" + name),
                                             "text", "2026-01-04T05:00:00+09:00"))
            with self.assertRaises(JMAError):
                parse(body)
        self.assertGreater(parse().series[0].time_definitions[-1].valid_utc, NOW)

    def test_wrong_source_namespace_or_kind_rejects(self):
        for body in (fixture().replace(REPORT_NS.encode(), b"http://example.invalid/"),
                     fixture().replace("府県天気予報（Ｒ１）".encode(), b"Other bulletin")):
            with self.assertRaises(JMAError):
                parse(body)


class SafeXMLTests(unittest.TestCase):
    def test_dtd_external_entity_and_internal_expansion_reject_before_parsing(self):
        for declaration in (b'<!DOCTYPE Report SYSTEM "file:///C:/private.txt">',
                            b'<!DOCTYPE Report [<!ENTITY x "replacement">]>',
                            b'<!ENTITY x SYSTEM "https://example.invalid/">'):
            body = declaration + fixture()
            with self.assertRaises(JMAError):
                parse(body)

    def test_utf16_utf32_non_utf8_declaration_and_unknown_entity_reject(self):
        text = fixture().decode("utf-8")
        for body in (text.encode("utf-16"), text.encode("utf-32"),
                     fixture().replace(b'encoding="UTF-8"', b'encoding="ISO-8859-1"'),
                     fixture().replace(b"Synthetic publishing office", b"&undeclared;"),
                     fixture() + b"\0"):
            with self.subTest(body_prefix=body[:20]), self.assertRaises(JMAError):
                parse(body)

    def test_utf8_bom_is_supported_without_changing_source_digest(self):
        body = b"\xef\xbb\xbf" + fixture()
        source = parse(body)
        self.assertEqual(source.receipt.body_sha256, hashlib.sha256(body).hexdigest())

    def test_excessive_depth_text_and_truncated_document_reject(self):
        for body in (b"<a>" * 65 + b"</a>" * 65,
                     b"<a>" + b"x" * 17000 + b"</a>", fixture()[:-20]):
            with self.assertRaises(JMAError):
                parse(body)


class ActualPrivateVPFD51Replay(unittest.TestCase):
    def test_actual_official_05_and_11_documents_preserve_real_times_and_all_points(self):
        folder = Path("private/forecast/jma-shape-audit-20261107")
        if not all((folder / (name + suffix)).is_file() for name in ("tokyo-05", "tokyo-11")
                   for suffix in (".body", ".json")):
            self.skipTest("optional real private VPFD51 05/11 captures absent")
        for name, hour in (("tokyo-05", "05"), ("tokyo-11", "11")):
            body = (folder / (name + ".body")).read_bytes()
            metadata = json.loads((folder / (name + ".json")).read_bytes())
            self.assertTrue(metadata["complete"])
            self.assertIsNone(metadata["failure"])
            self.assertEqual(metadata["redirects_followed"], 0)
            self.assertFalse(metadata["authentication_supplied"])
            document_receipt = XMLDocumentReceipt(metadata["url"], metadata["body_sha256"],
                metadata["body_bytes"], datetime.fromisoformat(metadata["retrieved_start_utc"]),
                datetime.fromisoformat(metadata["retrieved_end_utc"]), metadata["status"])
            source = parse_daily_temperatures(body, document_receipt)
            self.assertEqual(source.report_datetime, f"2026-11-07T{hour}:00:00+09:00")
            self.assertLess(source.transmitted_utc, source.issued_utc)
            self.assertEqual(len(source.series), 1)
            series = source.series[0]
            self.assertEqual(series.source_series_index, 2)
            self.assertEqual([t.datetime for t in series.time_definitions], [
                "2026-11-07T09:00:00+09:00", "2026-11-07T00:00:00+09:00",
                "2026-11-08T00:00:00+09:00", "2026-11-08T09:00:00+09:00"])
            self.assertEqual([p.station_code for p in series.points], ["44132", "44172", "44263", "44301"])
            for point in series.points:
                values = [v for p in point.properties for v in p.values]
                self.assertEqual([v.ref_id for v in values], ["1", "2", "3", "4"])
                self.assertEqual([v.semantic_role for v in values],
                    ["daytime_maximum", "maximum_temperature", "morning_minimum", "daytime_maximum"])
                self.assertTrue(all(v.numeric_value is not None for v in values))
                self.assertTrue(all(v.raw_unit == "度" for v in values))


if __name__ == "__main__":
    unittest.main()
