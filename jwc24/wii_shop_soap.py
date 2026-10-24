"""Offline CAS ListTitles codec derived from fingerprinted client-library evidence.

This module has no service handler, authentication, catalog adapter or network I/O.
Parsing is structural validation, never proof of an account or authorization.
Response evidence references are caller assertions, not independent verification.
See channels/wii_shop/soap_contract.md before integration.
"""

from dataclasses import dataclass, field
from io import StringIO
import re
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
CAS_NS = "urn:cas.wsapi.broadon.com"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
LIST_TITLES_ACTION = CAS_NS + "/ListTitles"
# Local defensive limits; these are not recovered native limits.
MAX_XML_BYTES = 128 * 1024
MAX_ELEMENTS = 2048
MAX_REPEATS = 256
MAX_TEXT = 4096
_COMMON = ("Version", "MessageId", "DeviceId", "DeviceToken", "AccountId",
           "ApplicationId", "TIN", "Region", "Country", "Language", "Age")
_REQUIRED_COMMON = ("Version", "MessageId", "Region", "Country", "Language")
_REPEATED = ("Attributes", "AttributeFilters", "TitleId")
_UINT32 = (1 << 32) - 1


class SoapContractError(ValueError):
    """Unsupported or malformed offline contract input (never echoes values)."""


def _text(value):
    if (not isinstance(value, str) or len(value) > MAX_TEXT
            or any(not (c in "\t\n\r" or "\x20" <= c <= "\ud7ff"
                        or "\ue000" <= c <= "\ufffd" or "\U00010000" <= c <= "\U0010ffff")
                   for c in value)):
        raise SoapContractError("Invalid or oversized XML text")
    return value


def _source(value):
    if not _text(value).strip():
        raise SoapContractError("An explicit evidence reference is required")


def _uint32(value):
    if type(value) is not int or not 0 <= value <= _UINT32:
        raise SoapContractError("Expected unsigned 32-bit integer")
    return value


def _title_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{16}", value):
        raise SoapContractError("Expected 16-digit hexadecimal title ID")
    return value.lower()


@dataclass(frozen=True)
class AttributeFilter:
    name: str
    value: str


@dataclass(frozen=True)
class ListTitlesRequest:
    offset: int
    limit: int
    attributes: tuple[str, ...]
    attribute_filters: tuple[AttributeFilter, ...]
    title_ids: tuple[str, ...]
    # Can contain account/device data. Never include it in repr or diagnostics.
    common_fields: tuple[tuple[str, str], ...] = field(repr=False)


def _simple(element):
    if len(element) or element.attrib:
        raise SoapContractError("Expected a simple CAS element")
    return _text(element.text or "")


def _container(element):
    if element.attrib or (element.text or "").strip():
        raise SoapContractError("Unexpected container attributes or text")
    if any((child.tail or "").strip() for child in element):
        raise SoapContractError("Unexpected mixed XML content")


def parse_list_titles_request(data: bytes, *, soap_action: str) -> ListTitlesRequest:
    """Parse only the recovered ListTitles request shape; preserve repeat order.

    Accept arbitrary namespace prefixes and quoted/unquoted SOAPAction. Common
    account/device fields remain opaque, unverified and excluded from repr.
    The parser does not require or manufacture a connected account.
    """
    if not isinstance(soap_action, str) or soap_action not in (
            LIST_TITLES_ACTION, '"' + LIST_TITLES_ACTION + '"'):
        raise SoapContractError("Unsupported SOAPAction")
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES:
        raise SoapContractError("Invalid or oversized XML input")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SoapContractError("Expected UTF-8 XML") from None
    if "<!DOCTYPE" in decoded.upper() or "<!ENTITY" in decoded.upper():
        raise SoapContractError("XML declarations with entities are unsupported")
    scopes, pending, operation_scope = [], {}, {}
    count = 0
    try:
        parser = ET.iterparse(StringIO(decoded),
                              events=("start-ns", "start", "end"))
        for event, item in parser:
            if event == "start-ns":
                pending[item[0]] = item[1]
            elif event == "start":
                scope = dict(scopes[-1]) if scopes else {}
                scope.update(pending)
                pending.clear()
                scopes.append(scope)
                count += 1
                if len(scopes) > 5 or count > MAX_ELEMENTS:
                    raise SoapContractError("XML structure exceeds local bounds")
                if len(scopes) == 3:
                    operation_scope = scope
            else:
                scopes.pop()
        root = parser.root
    except ET.ParseError:
        raise SoapContractError("Malformed XML") from None
    if root.tag != f"{{{SOAP_NS}}}Envelope" or len(root) != 1:
        raise SoapContractError("Expected one SOAP 1.1 body")
    _container(root)
    body = root[0]
    if body.tag != f"{{{SOAP_NS}}}Body" or len(body) != 1:
        raise SoapContractError("Expected one SOAP operation")
    _container(body)
    operation = body[0]
    if operation.tag != f"{{{CAS_NS}}}ListTitles":
        raise SoapContractError("Unsupported CAS operation")
    type_value = operation.attrib.get(f"{{{XSI_NS}}}type")
    if set(operation.attrib) - {f"{{{XSI_NS}}}type"}:
        raise SoapContractError("Unsupported operation attributes")
    if type_value is not None:
        parts = type_value.split(":")
        prefix, local = (parts if len(parts) == 2 else ("", type_value))
        if local != "ListTitlesRequestType" or operation_scope.get(prefix) != CAS_NS:
            raise SoapContractError("Unsupported request type")
    if (operation.text or "").strip() or any((e.tail or "").strip() for e in operation):
        raise SoapContractError("Unexpected operation text")
    single, repeated = {}, {name: [] for name in _REPEATED}
    allowed = set(_COMMON) | set(_REPEATED) | {"ListResultOffset", "ListResultLimit"}
    for element in operation:
        if not element.tag.startswith("{" + CAS_NS + "}"):
            raise SoapContractError("Unexpected field namespace")
        name = element.tag[len(CAS_NS) + 2:]
        if name not in allowed:
            raise SoapContractError("Unsupported request field")
        if name == "AttributeFilters":
            _container(element)
            if [e.tag for e in element] != [f"{{{CAS_NS}}}Name", f"{{{CAS_NS}}}Value"]:
                raise SoapContractError("Expected filter Name and Value")
            value = AttributeFilter(_simple(element[0]), _simple(element[1]))
        else:
            value = _simple(element)
        if name in repeated:
            repeated[name].append(value)
            if len(repeated[name]) > MAX_REPEATS:
                raise SoapContractError("Too many repeated fields")
        elif name in single:
            raise SoapContractError("Duplicate singleton field")
        else:
            single[name] = value
    if any(name not in single for name in (*_REQUIRED_COMMON, "ListResultOffset", "ListResultLimit")):
        raise SoapContractError("Missing required request field")
    if single["Version"] != "2.0":
        raise SoapContractError("Unsupported library request version")
    numbers = []
    for name in ("ListResultOffset", "ListResultLimit"):
        if not re.fullmatch(r"[0-9]{1,10}", single[name]):
            raise SoapContractError("Invalid list range")
        numbers.append(_uint32(int(single[name])))
    return ListTitlesRequest(*numbers, tuple(repeated["Attributes"]),
                             tuple(repeated["AttributeFilters"]),
                             tuple(_title_id(v) for v in repeated["TitleId"]),
                             tuple((k, single[k]) for k in _COMMON if k in single))


@dataclass(frozen=True)
class CatalogAttribute:
    """Explicitly supplied native attribute name/value and supporting reference."""
    name: str
    value: str
    source_ref: str


@dataclass(frozen=True)
class CatalogTitle:
    title_id: str
    source_ref: str
    attributes: tuple[CatalogAttribute, ...] = ()


def serialize_list_titles_response(*, total_size: int, total_source_ref: str,
                                   titles: tuple[CatalogTitle, ...], error_code: str,
                                   timestamp: str | None = None) -> bytes:
    """Build an OFFLINE response from explicitly supplied evidenced fields.

    No field is inferred from the offline catalog. Evidence references are not
    sent on the wire. No ownership, price, license or installation data is
    supported. An explicit zero error code represents only a synthetic codec
    fixture until an authorized, matched service contract is integrated.
    """
    _uint32(total_size)
    _source(total_source_ref)
    if error_code != "0":
        raise SoapContractError("Only explicit offline zero-status fixtures are supported")
    if not isinstance(titles, tuple) or len(titles) > MAX_REPEATS or len(titles) > total_size:
        raise SoapContractError("Invalid supplied title count")
    output = bytearray()

    def append_line(line):
        # Check UTF-8 bytes after escaping, before growing the bounded buffer.
        # Each transient line is itself bounded by MAX_TEXT and XML escaping.
        encoded = (line + "\n").encode("utf-8")
        if len(output) + len(encoded) > MAX_XML_BYTES:
            raise SoapContractError("Response exceeds local byte bound")
        output.extend(encoded)

    # Keep these lexical forms: the recovered reader is not namespace-aware.
    append_line('<?xml version="1.0" encoding="UTF-8"?>')
    append_line(f'<soapenv:Envelope xmlns:soapenv="{SOAP_NS}">')
    append_line('<soapenv:Body>')
    append_line(f'<ListTitlesResponse xmlns="{CAS_NS}">')
    if timestamp is not None:
        if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{1,20}", timestamp):
            raise SoapContractError("Expected explicitly supplied decimal timestamp")
        append_line(f'<TimeStamp>{timestamp}</TimeStamp>')
    append_line('<ErrorCode>0</ErrorCode>')
    append_line(f'<ListResultTotalSize>{total_size}</ListResultTotalSize>')
    for title in titles:
        if not isinstance(title, CatalogTitle):
            raise SoapContractError("Expected supplied catalog title")
        _source(title.source_ref)
        identifier = _title_id(title.title_id)
        if not isinstance(title.attributes, tuple) or len(title.attributes) > MAX_REPEATS:
            raise SoapContractError("Invalid supplied attribute count")
        append_line('<Titles>')
        append_line(f'<TitleId>{identifier}</TitleId>')
        for attribute in title.attributes:
            if not isinstance(attribute, CatalogAttribute):
                raise SoapContractError("Expected supplied catalog attribute")
            _source(attribute.source_ref)
            append_line('<Attributes>')
            append_line(f'<Name>{escape(_text(attribute.name))}</Name>')
            append_line(f'<Value>{escape(_text(attribute.value))}</Value>')
            append_line('</Attributes>')
        append_line('</Titles>')
    append_line('</ListTitlesResponse>')
    append_line('</soapenv:Body>')
    append_line('</soapenv:Envelope>')
    return bytes(output)
