"""Check explicit experimental catalog pins and published JMA area hierarchy.

Neither a label match, a coordinate, a receipt nor a native-format file proves
Nintendo provenance or city-to-station identity. This module assigns no city,
selects no point and creates no native weather. An assessment retains those
unresolved identity requirements alongside the memberships it actually checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math

from .jma_associations import AssociationCatalog, ObservationCatalog, ShortAssociation, _code
from .jma_weather import (
    JMAError, MAX_BODY_BYTES, SourceReceipt, Station, _json, _list, _object, _pairs, _raw,
    _require, _text,
)


AREA_KINDS = ("centers", "offices", "class10s", "class15s", "class20s")
CATALOG_CLASSIFICATIONS = frozenset({"third_party_catalog", "historical_native_download",
                                   "recovered_original_unverified", "synthetic"})


@dataclass(frozen=True)
class AreaNode:
    kind: str
    code: str
    name: str
    english_name: str
    parent: str | None
    children: tuple[str, ...]
    raw_metadata_json: str


@dataclass(frozen=True)
class AreaCatalog:
    nodes: tuple[AreaNode, ...]
    receipt: SourceReceipt

    def node(self, kind: str, code: str) -> AreaNode:
        _require(kind in AREA_KINDS, "unknown source area class")
        matches = [n for n in self.nodes if n.kind == kind and n.code == code]
        _require(len(matches) == 1, "explicit area identity is absent or ambiguous")
        return matches[0]


def parse_area_catalog(body: bytes, receipt: SourceReceipt) -> AreaCatalog:
    data = _object(_json(body, receipt, "common_areas"))
    _require(set(data) == set(AREA_KINDS), "common area classes differ from reviewed contract")
    nodes, by_class = [], {}
    for i, kind in enumerate(AREA_KINDS):
        rows = _object(data[kind])
        _require(0 < len(rows) <= 10000, "area class count outside bounds")
        parsed = {}
        for code, raw in rows.items():
            _code(code, 7 if kind == "class20s" else 6)
            raw = _object(raw)
            parent = _code(raw.get("parent"), 6) if i else None
            children = (tuple(_code(c, 7 if kind == "class15s" else 6)
                              for c in _list(raw.get("children"), 10000))
                        if kind != "class20s" else ())
            _require(len(set(children)) == len(children), "duplicate source area child")
            node = AreaNode(kind, code, _text(raw.get("name")), _text(raw.get("enName")),
                            parent, children, _raw(raw))
            nodes.append(node)
            parsed[code] = node
        by_class[kind] = parsed
    for i, kind in enumerate(AREA_KINDS[1:], 1):
        parents, children = by_class[AREA_KINDS[i - 1]], by_class[kind]
        for code, child in children.items():
            _require(child.parent in parents and code in parents[child.parent].children,
                     "source parent/child membership disagrees")
        for code, parent in parents.items():
            _require(all(c in children and children[c].parent == code for c in parent.children),
                     "source child/parent membership disagrees")
    return AreaCatalog(tuple(nodes), receipt)


@dataclass(frozen=True)
class PublishedAreaChain:
    municipality: AreaNode
    class15: AreaNode
    class10: AreaNode
    office: AreaNode
    center: AreaNode
    receipt: SourceReceipt


def published_area_chain(catalog: AreaCatalog, class20: str) -> PublishedAreaChain:
    """Follow supplied provider IDs, never infer a city from its name/point."""
    _code(class20, 7)
    result = []
    code = class20
    for kind in reversed(AREA_KINDS):
        node = catalog.node(kind, code)
        result.append(node)
        code = node.parent
    return PublishedAreaChain(*result, catalog.receipt)


@dataclass(frozen=True)
class CatalogReceipt:
    body_sha256: str
    body_bytes: int
    classification: str
    origin_reference: str
    evidence_reference: str

    @classmethod
    def from_body(cls, body: bytes, *, classification: str,
                  origin_reference: str, evidence_reference: str) -> CatalogReceipt:
        _require(type(body) is bytes and 0 < len(body) <= MAX_BODY_BYTES,
                 "experimental catalog outside byte bound")
        _require(type(classification) is str and classification in CATALOG_CLASSIFICATIONS,
                 "catalog classification must not assert verified Nintendo provenance")
        return cls(hashlib.sha256(body).hexdigest(), len(body), classification,
                   _text(origin_reference), _text(evidence_reference))


@dataclass(frozen=True)
class ExperimentalLocation:
    key: tuple[int, int, int]
    city: str
    region: str
    country: str
    latitude: int | float
    longitude: int | float
    zoom_near: int
    zoom_far: int
    raw_row_json: str


@dataclass(frozen=True)
class ExperimentalLocationCatalog:
    rows: tuple[ExperimentalLocation, ...]
    receipt: CatalogReceipt


def _integer(value: object, maximum: int) -> int:
    _require(type(value) is int and 0 <= value <= maximum, "catalog integer outside native range")
    return value


def _coordinate(value: object, maximum: int) -> int | float:
    _require(type(value) in (int, float) and -maximum <= value <= maximum
             and math.isfinite(value), "invalid experimental location coordinate")
    return value


def _optional_label(value: object) -> str:
    # Some retained globe rows intentionally have no region/country label.
    if value == "":
        return ""
    return _text(value)


def parse_experimental_catalog(body: bytes, receipt: CatalogReceipt) -> ExperimentalLocationCatalog:
    actual = CatalogReceipt.from_body(body, classification=receipt.classification,
        origin_reference=receipt.origin_reference, evidence_reference=receipt.evidence_reference)
    _require(actual == receipt, "catalog digest or metadata mismatch")
    try:
        data = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise JMAError("invalid experimental catalog JSON") from exc
    rows, seen = [], set()
    for raw in _list(data, 10000):
        raw = _object(raw)
        key = tuple(_integer(raw.get(k), n) for k, n in (
            ("country_code", 255), ("region_code", 255), ("location_code", 65535)))
        _require(key not in seen, "duplicate experimental location key")
        seen.add(key)
        try:
            canonical = _raw(raw)
            canonical.encode("utf-8")
        except UnicodeError as exc:
            raise JMAError("invalid catalog Unicode") from exc
        rows.append(ExperimentalLocation(key, _text(raw.get("city")), _optional_label(raw.get("region")),
            _optional_label(raw.get("country")), _coordinate(raw.get("latitude"), 90),
            _coordinate(raw.get("longitude"), 180), _integer(raw.get("zoom_near"), 255),
            _integer(raw.get("zoom_far"), 255), canonical))
    return ExperimentalLocationCatalog(tuple(rows), receipt)


@dataclass(frozen=True)
class CatalogRowPin:
    catalog_sha256: str
    row_index: int
    key: tuple[int, int, int]
    row_sha256: str


def pin_catalog_row(catalog: ExperimentalLocationCatalog,
                    key: tuple[int, int, int]) -> CatalogRowPin:
    _require(type(key) is tuple and len(key) == 3 and all(type(k) is int for k in key),
             "explicit exact catalog key required")
    matches = [(i, r) for i, r in enumerate(catalog.rows) if r.key == key]
    _require(len(matches) == 1, "explicit catalog key absent or ambiguous")
    index, row = matches[0]
    return CatalogRowPin(catalog.receipt.body_sha256, index, key,
                         hashlib.sha256(row.raw_row_json.encode("utf-8")).hexdigest())


def verify_catalog_pin(catalog: ExperimentalLocationCatalog, pin: CatalogRowPin) -> ExperimentalLocation:
    _require(pin.catalog_sha256 == catalog.receipt.body_sha256
             and type(pin.row_index) is int and 0 <= pin.row_index < len(catalog.rows),
             "catalog pin digest or row index differs")
    row = catalog.rows[pin.row_index]
    _require(pin.key == row.key and pin.row_sha256 == hashlib.sha256(
        row.raw_row_json.encode("utf-8")).hexdigest(), "catalog pin row identity differs")
    return row


@dataclass(frozen=True)
class ExperimentalBindingAssessment:
    catalog_receipt: CatalogReceipt
    catalog_pin: CatalogRowPin
    location: ExperimentalLocation
    published_area: PublishedAreaChain
    source_association: ShortAssociation
    association_receipts: tuple[SourceReceipt, ...]
    forecast_temperature_point: str
    observation_catalog_receipt: SourceReceipt
    observation_station_in_catalog: bool
    station_metadata: Station | None
    catalog_pin_status: str = field(default="validated_exact_catalog_row", init=False)
    provider_hierarchy_status: str = field(default="validated_reciprocal_provider_membership", init=False)
    native_city_municipality_status: str = field(default="unresolved_external_identity_evidence", init=False)
    native_city_measurement_status: str = field(default="unresolved_station_to_native_city_identity", init=False)
    original_catalog_provenance_status: str = field(default="unverified_by_this_validator", init=False)
    ready_for_native_publication: bool = field(default=False, init=False)


def assess_experimental_binding(catalog: ExperimentalLocationCatalog, pin: CatalogRowPin,
        areas: AreaCatalog, class20: str, associations: AssociationCatalog,
        observations: ObservationCatalog, temperature_point: str, *,
        station_metadata: Station | None) -> ExperimentalBindingAssessment:
    """Check supplied identities without claiming the city represents a station.

    The class20 choice is caller-supplied, not proved by a matching name or by
    its numeric coordinate. It remains unresolved even after the independent
    catalog pin and JMA hierarchy pass. A representative temperature forecast
    and a station measurement keep their original separate identities.
    """
    row = verify_catalog_pin(catalog, pin)
    chain = published_area_chain(areas, class20)
    _code(temperature_point, 5)
    matches = [a for a in associations.short if a.office == chain.office.code
               and a.class10 == chain.class10.code and temperature_point in a.temperature_points]
    _require(len(matches) == 1, "explicit point does not belong to published office/area association")
    present = temperature_point in observations.station_codes
    if station_metadata is not None:
        _require(type(station_metadata) is Station and station_metadata.code == temperature_point
                 and present and station_metadata.receipt == observations.receipt,
                 "station identity or catalog receipt differs from explicit source point")
    return ExperimentalBindingAssessment(catalog.receipt, pin, row, chain, matches[0],
        associations.receipts, temperature_point, observations.receipt, present, station_metadata)
