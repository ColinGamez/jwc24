"""Explicit identity/provenance checks; no network or profile access."""

from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import unittest

from jwc24.jma_associations import parse_associations, parse_observation_catalog
from jwc24.jma_identity import (
    CatalogReceipt, assess_experimental_binding, parse_area_catalog,
    parse_experimental_catalog, pin_catalog_row, published_area_chain, verify_catalog_pin,
)
from jwc24.jma_weather import BASE, JMAError, SourceReceipt, parse_station
from tests.test_jma_associations import catalog, observations, source


NOW = datetime(2026, 1, 3, tzinfo=timezone.utc)


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def area_values():
    return {
        "centers": {"010300": {"name": "Synthetic center", "enName": "Synthetic center",
                                "children": ["130000"]}},
        "offices": {"130000": {"name": "Synthetic office", "enName": "Synthetic office",
                                "parent": "010300", "children": ["130030"]}},
        "class10s": {"130030": {"name": "Synthetic southern region", "enName": "Synthetic southern region",
                                 "parent": "130000", "children": ["130031"]}},
        "class15s": {"130031": {"name": "Synthetic islands", "enName": "Synthetic islands",
                                 "parent": "130030", "children": ["1340100"]}},
        "class20s": {"1340100": {"name": "Synthetic town", "enName": "Synthetic town",
                                  "parent": "130031"}}}


def areas(value=None):
    body = encoded(area_values() if value is None else value)
    receipt = SourceReceipt.from_body(BASE + "/bosai/common/const/area.json", body,
                                      NOW - timedelta(seconds=1), NOW)
    return parse_area_catalog(body, receipt)


def location_values():
    return [{"country_code": 1, "region_code": 1, "location_code": 1,
             "city": "Synthetic experimental city", "region": "Synthetic region",
             "country": "Synthetic country", "latitude": 33.125, "longitude": 139.75,
             "zoom_near": 0, "zoom_far": 3}]


def experimental(value=None, classification="third_party_catalog"):
    body = encoded(location_values() if value is None else value)
    receipt = CatalogReceipt.from_body(body, classification=classification,
        origin_reference="Synthetic supplied origin", evidence_reference="Synthetic supplied evidence")
    return parse_experimental_catalog(body, receipt)


def station():
    body, receipt = source("stations", {"44263": {"type": "A", "elems": "11111111",
        "lat": [33, 7.5], "lon": [139, 45], "alt": 10, "kjName": "Synthetic station",
        "knName": "Synthetic kana", "enName": "Synthetic station"}})
    return parse_station(body, receipt, "44263"), parse_observation_catalog(body, receipt)


class PublishedHierarchyTests(unittest.TestCase):
    def test_complete_reciprocal_chain_keeps_provider_ids_labels_and_receipt(self):
        table = areas()
        chain = published_area_chain(table, "1340100")
        self.assertEqual((chain.municipality.code, chain.class15.code, chain.class10.code,
                          chain.office.code, chain.center.code),
                         ("1340100", "130031", "130030", "130000", "010300"))
        self.assertEqual(chain.class10.name, "Synthetic southern region")
        self.assertEqual(chain.receipt, table.receipt)

    def test_both_parent_and_children_directions_are_checked(self):
        for change in ("missing_parent", "wrong_child", "duplicate_child", "dangling_child"):
            data = area_values()
            if change == "missing_parent":
                data["class20s"]["1340100"]["parent"] = "999999"
            elif change == "wrong_child":
                data["class15s"]["130031"]["children"] = ["9999999"]
            elif change == "duplicate_child":
                data["class15s"]["130031"]["children"] *= 2
            else:
                data["class15s"]["130031"]["children"].append("9999999")
            with self.subTest(change=change), self.assertRaises(JMAError):
                areas(data)

    def test_namespace_is_part_of_identity_even_if_codes_repeat_between_levels(self):
        data = area_values()
        data["class15s"]["130030"] = data["class15s"].pop("130031")
        data["class10s"]["130030"]["children"] = ["130030"]
        data["class20s"]["1340100"]["parent"] = "130030"
        chain = published_area_chain(areas(data), "1340100")
        self.assertEqual(chain.class15.code, chain.class10.code)
        self.assertNotEqual(chain.class15.kind, chain.class10.kind)

    def test_missing_class20_has_no_name_or_first_row_fallback(self):
        with self.assertRaises(JMAError):
            published_area_chain(areas(), "9999999")

    def test_receipt_digest_and_parser_route_remain_bound(self):
        table = areas()
        body = encoded(area_values())
        with self.assertRaises(JMAError):
            parse_area_catalog(body + b" ", table.receipt)
        with self.assertRaises(JMAError):
            parse_area_catalog(body, replace(table.receipt,
                url=BASE + "/bosai/forecast/const/forecast_area.json"))


class ExperimentalCatalogTests(unittest.TestCase):
    def test_exact_row_pin_preserves_labels_coordinates_and_order(self):
        cat = experimental()
        pin = pin_catalog_row(cat, (1, 1, 1))
        row = verify_catalog_pin(cat, pin)
        self.assertEqual(row.city, "Synthetic experimental city")
        self.assertEqual((row.latitude, row.longitude, row.zoom_near), (33.125, 139.75, 0))
        self.assertEqual(pin.catalog_sha256, cat.receipt.body_sha256)
        self.assertEqual(pin.row_index, 0)

    def test_shifted_region_keys_from_another_catalog_are_rejected(self):
        first = experimental()
        values = location_values()
        values[0]["region_code"] = 2
        second = experimental(values)
        with self.assertRaises(JMAError):
            verify_catalog_pin(second, pin_catalog_row(first, (1, 1, 1)))
        with self.assertRaises(JMAError):
            pin_catalog_row(second, (1, 1, 1))

    def test_same_key_with_changed_label_coordinate_or_unknown_metadata_rejects_old_pin(self):
        first = experimental()
        pin = pin_catalog_row(first, (1, 1, 1))
        for change in ({"city": "Changed label"}, {"latitude": 33.5}, {"new_metadata": "Changed"}):
            data = location_values()
            data[0].update(change)
            with self.subTest(change=change), self.assertRaises(JMAError):
                verify_catalog_pin(experimental(data), pin)

    def test_pin_requires_matching_index_key_and_canonical_row_digest(self):
        cat = experimental()
        pin = pin_catalog_row(cat, (1, 1, 1))
        for change in ({"row_index": True}, {"row_index": 20}, {"key": (1, 2, 1)},
                       {"row_sha256": "0" * 64}):
            with self.subTest(change=change), self.assertRaises(JMAError):
                verify_catalog_pin(cat, replace(pin, **change))

    def test_catalog_classification_is_a_retained_claim_not_nintendo_authentication(self):
        for classification in ("third_party_catalog", "historical_native_download",
                               "recovered_original_unverified", "synthetic"):
            cat = experimental(classification=classification)
            self.assertEqual(cat.receipt.classification, classification)
        for classification in ("verified_Nintendo_original", "", "original", []):
            with self.assertRaises(JMAError):
                experimental(classification=classification)

    def test_existing_blank_region_and_country_are_retained(self):
        values = location_values()
        values[0].update(region="", country="")
        row = experimental(values).rows[0]
        self.assertEqual((row.region, row.country), ("", ""))

    def test_changed_receipt_or_duplicate_keys_reject(self):
        body = encoded(location_values())
        cat = experimental()
        with self.assertRaises(JMAError):
            parse_experimental_catalog(body, replace(cat.receipt, body_sha256="0" * 64))
        with self.assertRaises(JMAError):
            experimental(location_values() * 2)

    def test_bad_json_unicode_nonfinite_and_native_field_ranges_reject(self):
        for body in (b'[{"city":"\\ud800"}]', b'[NaN]', b'[{}]', b'\xff'):
            receipt = CatalogReceipt.from_body(body, classification="synthetic",
                origin_reference="Synthetic", evidence_reference="Synthetic")
            with self.subTest(body=body), self.assertRaises(JMAError):
                parse_experimental_catalog(body, receipt)
        for change in ({"country_code": True}, {"location_code": 65536}, {"latitude": 91},
                       {"longitude": float("inf")}, {"zoom_near": -1}):
            values = location_values()
            values[0].update(change)
            with self.subTest(change=change), self.assertRaises(JMAError):
                experimental(values)


class BindingAssessmentTests(unittest.TestCase):
    def assess(self, **kwargs):
        cat = experimental()
        values = dict(catalog=cat, pin=pin_catalog_row(cat, (1, 1, 1)), areas=areas(),
                      class20="1340100", associations=catalog(), observations=observations(),
                      temperature_point="44263", station_metadata=None)
        values.update(kwargs)
        return assess_experimental_binding(**values)

    def test_checked_provider_and_catalog_facts_do_not_prove_city_municipality_identity(self):
        result = self.assess()
        self.assertEqual(result.catalog_pin_status, "validated_exact_catalog_row")
        self.assertEqual(result.provider_hierarchy_status, "validated_reciprocal_provider_membership")
        self.assertEqual(result.native_city_municipality_status, "unresolved_external_identity_evidence")
        self.assertEqual(result.native_city_measurement_status, "unresolved_station_to_native_city_identity")
        self.assertFalse(result.ready_for_native_publication)
        self.assertEqual(result.location.city, "Synthetic experimental city")
        self.assertEqual(result.published_area.municipality.name, "Synthetic town")
        self.assertEqual(result.forecast_temperature_point, "44263")

    def test_public_constructor_and_replace_do_not_accept_self_asserted_ready_or_statuses(self):
        result = self.assess()
        constructor_values = {f.name: getattr(result, f.name) for f in fields(result) if f.init}
        for name, value in (("ready_for_native_publication", True),
                            ("native_city_municipality_status", "verified"),
                            ("native_city_measurement_status", "verified"),
                            ("original_catalog_provenance_status", "Nintendo_verified"),
                            ("catalog_pin_status", "self_asserted"),
                            ("provider_hierarchy_status", "self_asserted")):
            with self.subTest(name=name):
                with self.assertRaises((TypeError, ValueError)):
                    replace(result, **{name: value})
                with self.assertRaises(TypeError):
                    type(result)(**constructor_values, **{name: value})

    def test_exact_station_metadata_is_preserved_separately_from_native_city(self):
        selected, obs = station()
        result = self.assess(observations=obs, station_metadata=selected)
        self.assertIs(result.station_metadata, selected)
        self.assertEqual(result.station_metadata.name, "Synthetic station")
        self.assertFalse(result.ready_for_native_publication)
        self.assertEqual(result.original_catalog_provenance_status, "unverified_by_this_validator")

    def test_matching_names_and_coordinates_do_not_upgrade_identity(self):
        selected, obs = station()
        data = location_values()
        data[0].update(city=selected.name, latitude=33.125, longitude=139.75)
        cat = experimental(data)
        result = self.assess(catalog=cat, pin=pin_catalog_row(cat, (1, 1, 1)),
                             observations=obs, station_metadata=selected)
        self.assertEqual(result.location.city, result.station_metadata.name)
        self.assertFalse(result.ready_for_native_publication)
        self.assertTrue(result.native_city_measurement_status.startswith("unresolved"))

    def test_explicit_point_must_be_published_for_exact_office_and_class10(self):
        with self.assertRaises(JMAError):
            self.assess(temperature_point="44132")
        changed = replace(catalog(), short=(replace(catalog().short[0], office="100000"),))
        with self.assertRaises(JMAError):
            self.assess(associations=changed)

    def test_forecast_point_catalog_absence_does_not_invent_station_metadata(self):
        result = self.assess(temperature_point="99999")
        self.assertFalse(result.observation_station_in_catalog)
        self.assertIsNone(result.station_metadata)
        self.assertFalse(result.ready_for_native_publication)

    def test_station_id_or_distinct_source_receipt_rejects(self):
        selected, obs = station()
        with self.assertRaises(JMAError):
            self.assess(observations=obs, station_metadata=replace(selected, code="99999"))
        with self.assertRaises(JMAError):
            self.assess(station_metadata=selected)


class PrivateHistoricalIdentityAudit(unittest.TestCase):
    def test_actual_takasaki_chain_pending_maebashi_representative_and_catalog_key_drift(self):
        initial = Path("private/forecast/jma-source-audit-20261028")
        added = Path("private/forecast/jma-association-audit-20261028")
        locations = Path("private/forecast/generated/japan-locations.json")
        archived = Path("private/forecast/reference/wiilink-live/forecast.bin")
        required = [(initial, "area-metadata"), (initial, "forecast-area-metadata"),
                    (added, "week_area"), (added, "week_area05"), (added, "week_area_name"),
                    (initial, "amedas-stations")]
        if not locations.is_file() or not archived.is_file() or not all(
                (p / (n + ".body")).is_file() and (p / (n + ".json")).is_file() for p, n in required):
            self.skipTest("optional historical JMA/catalog audit inputs absent")
        def read_pair(folder, name):
            body = (folder / (name + ".body")).read_bytes()
            meta = json.loads((folder / (name + ".json")).read_bytes())
            def dt(v):
                return datetime.fromtimestamp(v, timezone.utc) if type(v) in (int, float) else datetime.fromisoformat(v)
            receipt = SourceReceipt(meta["url"], meta["body_sha256"], meta.get("body_bytes", meta.get("bytes")),
                dt(meta["retrieved_start_utc"]), dt(meta["retrieved_end_utc"]), meta["status"])
            return body, receipt
        inputs = [read_pair(*pair) for pair in required]
        areas_table = parse_area_catalog(*inputs[0])
        self.assertEqual(len(areas_table.nodes), 2391)
        associations = parse_associations(*(x for pair in inputs[1:5] for x in pair))
        obs = parse_observation_catalog(*inputs[5])
        selected = parse_station(*inputs[5], "42251")
        body = locations.read_bytes()
        receipt = CatalogReceipt.from_body(body, classification="third_party_catalog",
            origin_reference="WiiLink24/ForecastChannel weather.xml-derived catalog",
            evidence_reference="Private retained third-party checkout and import tool")
        native = parse_experimental_catalog(body, receipt)
        result = assess_experimental_binding(native, pin_catalog_row(native, (1, 11, 2)),
            areas_table, "1020200", associations, obs, "42251", station_metadata=selected)
        self.assertEqual(result.location.city, "\u9ad8\u5d0e\u5e02")
        self.assertEqual(result.published_area.municipality.code, "1020200")
        self.assertEqual((result.published_area.class15.code, result.published_area.class10.code,
                          result.published_area.office.code), ("100013", "100010", "100000"))
        self.assertEqual(result.station_metadata.name, "\u524d\u6a4b")
        self.assertFalse(result.ready_for_native_publication)
        # This is a retained third-party native-format response, not Nintendo provenance.
        from jwc24.forecast import FORECAST_HEADER, LOCATION, unwrap_signed_payload
        from tools.extract_forecast_catalog import coordinate, text_at
        archived_body = archived.read_bytes()
        self.assertEqual(hashlib.sha256(archived_body).hexdigest(),
                         "29f5526385602be30a6640552d63a4b971d321b53f20f9d138fcfab957fa30ca")
        raw = unwrap_signed_payload(archived_body)
        header = FORECAST_HEADER.unpack_from(raw)
        extracted = []
        for i in range(header[23]):
            row = LOCATION.unpack_from(raw, header[24] + i * LOCATION.size)
            extracted.append(dict(zip(("country_code", "region_code", "location_code", "city", "region",
                "country", "latitude", "longitude", "zoom_near", "zoom_far"),
                (*row[:3], *(text_at(raw, row[j]) for j in (3, 4, 5)),
                 coordinate(row[6]), coordinate(row[7]), row[8], row[9]))))
        other_body = encoded(extracted)
        other = parse_experimental_catalog(other_body, CatalogReceipt.from_body(other_body,
            classification="historical_native_download", origin_reference="Private WiiLink native-format response",
            evidence_reference="Source download SHA256=" + hashlib.sha256(archived_body).hexdigest()))
        self.assertEqual(len(other.rows), 653)
        other_tokyo = verify_catalog_pin(other, pin_catalog_row(other, (1, 2, 1)))
        this_tokyo = verify_catalog_pin(native, pin_catalog_row(native, (1, 1, 1)))
        self.assertEqual(other_tokyo.city, this_tokyo.city)
        with self.assertRaises(JMAError):
            verify_catalog_pin(other, pin_catalog_row(native, (1, 1, 1)))


if __name__ == "__main__":
    unittest.main()
