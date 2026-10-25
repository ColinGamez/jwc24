"""Offline ECS GetECConfig subset checked against selected retail v21 paths.

No route, network, identity, connected-state or endpoint default is implemented.
The request includes the native optional PostalCode attribute. Selected retail
request and response execution is separate from full connection/authentication.
See ec_config.md for the exact verification scope and separate URI/local limits.
"""
from dataclasses import dataclass, field
from io import StringIO
import re
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
ECS_NS = 'urn:ecs.wsapi.broadon.com'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
GET_EC_CONFIG_ACTION = ECS_NS+'/GetECConfig'
URL_FIELDS = ('ContentPrefixURL', 'UncachedContentPrefixURL', 'EcsURL', 'IasURL', 'CasURL')
# Defensive JWC24 limits and URI policy, not recovered native acceptance limits.
MAX_XML_BYTES = 64*1024
MAX_TEXT = 4096
MAX_ELEMENTS = 64
MAX_DEPTH = 5
MAX_NAMESPACES = 32
_COMMON = ('Version', 'MessageId', 'DeviceId', 'DeviceToken', 'AccountId',
           'ApplicationId', 'TIN', 'Region', 'Country', 'Language', 'SerialNo')
_REQUIRED = ('Version', 'MessageId', 'Region', 'Country', 'Language', 'SerialNo', 'ECVersion')


class EcConfigContractError(ValueError):
    """Malformed or unsupported offline input; messages never include values."""


def _text(value):
    if (not isinstance(value, str) or len(value) > MAX_TEXT
            or any(not (c in '\t\n\r' or '\x20' <= c <= '\ud7ff'
                        or '\ue000' <= c <= '\ufffd' or '\U00010000' <= c <= '\U0010ffff')
                   for c in value)):
        raise EcConfigContractError('Invalid or oversized XML text')
    return value


def _source(value):
    if not _text(value).strip():
        raise EcConfigContractError('An explicit fixture evidence reference is required')


def _container(element):
    if (element.attrib or (element.text or '').strip()
            or any((child.tail or '').strip() for child in element)):
        raise EcConfigContractError('Unexpected XML container attributes or mixed text')


@dataclass(frozen=True)
class GetECConfigRequest:
    ec_version: str = field(repr=False)
    # Opaque account/device fields confer no authentication and stay private.
    common_fields: tuple[tuple[str, str], ...] = field(repr=False)
    postal_code: str | None = field(default=None, repr=False)


def parse_get_ec_config_request(data: bytes, *, soap_action: str) -> GetECConfigRequest:
    """Structurally validate the reviewed ECS request subset, without authenticating.

    Prefix spelling is arbitrary. xsi:type may be absent; when present it must
    resolve to the ECS GetECConfigRequestType. SerialNo is an ECS common field;
    the CAS-only Age field and CAS namespace/action are intentionally rejected.
    A single native Attributes/PostalCode pair is retained as opaque private
    text. Unknown attribute names and repeated pairs are outside this subset.
    """
    if not isinstance(soap_action, str) or soap_action not in (
            GET_EC_CONFIG_ACTION, '"'+GET_EC_CONFIG_ACTION+'"'):
        raise EcConfigContractError('Unsupported ECS SOAPAction')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES:
        raise EcConfigContractError('Invalid or oversized XML input')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise EcConfigContractError('Expected UTF-8 XML') from None
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise EcConfigContractError('XML entity declarations are unsupported')
    scopes, pending, operation_scope = [], {}, {}
    elements = namespaces = 0
    try:
        parser = ET.iterparse(StringIO(text), events=('start-ns', 'start', 'end'))
        for event, item in parser:
            if event == 'start-ns':
                namespaces += 1
                if namespaces > MAX_NAMESPACES:
                    raise EcConfigContractError('XML namespace count exceeds local bound')
                pending[item[0]] = item[1]
            elif event == 'start':
                scope = dict(scopes[-1]) if scopes else {}
                scope.update(pending)
                pending.clear()
                scopes.append(scope)
                elements += 1
                if elements > MAX_ELEMENTS or len(scopes) > MAX_DEPTH:
                    raise EcConfigContractError('XML structure exceeds local bounds')
                if len(scopes) == 3:
                    operation_scope = scope
            else:
                scopes.pop()
        root = parser.root
    except ET.ParseError:
        raise EcConfigContractError('Malformed XML') from None
    if root.tag != f'{{{SOAP_NS}}}Envelope' or len(root) != 1:
        raise EcConfigContractError('Expected one SOAP 1.1 body')
    _container(root)
    body = root[0]
    if body.tag != f'{{{SOAP_NS}}}Body' or len(body) != 1:
        raise EcConfigContractError('Expected one SOAP operation')
    _container(body)
    operation = body[0]
    if operation.tag != f'{{{ECS_NS}}}GetECConfig':
        raise EcConfigContractError('Unsupported ECS operation')
    if set(operation.attrib)-{f'{{{XSI_NS}}}type'}:
        raise EcConfigContractError('Unsupported operation attributes')
    request_type = operation.attrib.get(f'{{{XSI_NS}}}type')
    if request_type is not None:
        parts = request_type.split(':')
        prefix, local = parts if len(parts) == 2 else ('', request_type)
        if local != 'GetECConfigRequestType' or operation_scope.get(prefix) != ECS_NS:
            raise EcConfigContractError('Unsupported ECS request type')
    if (operation.text or '').strip() or any((child.tail or '').strip() for child in operation):
        raise EcConfigContractError('Unexpected operation text')
    values = {}
    for element in operation:
        if not element.tag.startswith('{'+ECS_NS+'}'):
            raise EcConfigContractError('Unexpected ECS field namespace')
        name = element.tag[len(ECS_NS)+2:]
        if name not in (*_COMMON, 'ECVersion', 'Attributes'):
            raise EcConfigContractError('Unsupported ECS request field')
        if name in values:
            raise EcConfigContractError('Duplicate ECS request field')
        if name == 'Attributes':
            _container(element)
            if [child.tag for child in element] != [f'{{{ECS_NS}}}Name', f'{{{ECS_NS}}}Value']:
                raise EcConfigContractError('Unsupported ECS configuration attribute structure')
            if any(child.attrib or len(child) for child in element):
                raise EcConfigContractError('Expected simple ECS configuration attribute fields')
            if _text(element[0].text or '') != 'PostalCode':
                raise EcConfigContractError('Unsupported ECS configuration attribute name')
            values[name] = _text(element[1].text or '')
            continue
        if element.attrib or len(element):
            raise EcConfigContractError('Expected a simple ECS field')
        values[name] = _text(element.text or '')
    if any(name not in values for name in _REQUIRED):
        raise EcConfigContractError('Missing required ECS request field')
    if values['Version'] != '2.0':
        raise EcConfigContractError('Unsupported reviewed request version')
    if not values['ECVersion'].strip():
        raise EcConfigContractError('Missing explicit ECVersion')
    return GetECConfigRequest(values['ECVersion'], tuple((k, values[k]) for k in _COMMON if k in values),
                              values.get('Attributes'))


@dataclass(frozen=True)
class EvidencedURL:
    """Caller-supplied offline URL and provenance assertion; neither is logged."""
    value: str = field(repr=False)
    source_ref: str = field(repr=False)


def _url(value):
    value = _text(value)
    # getSimple in the older native reader copies raw element text. An ampersand
    # escaped to &amp; would become a different configured URL. Require the caller
    # to supply any evidenced percent-encoded form; never transform a URL here.
    if (not value or any(c.isspace() or c in '\\<>"{}|^`&?#' or ord(c) < 32
                         or 127 <= ord(c) <= 159 for c in value)):
        raise EcConfigContractError('Invalid offline fixture URI')
    try:
        parsed = urlsplit(value)
        port = parsed.port
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or (port is not None and not 1 <= port <= 65535)):
            raise EcConfigContractError('Unsupported offline fixture URI')
    except ValueError:
        raise EcConfigContractError('Invalid offline fixture URI') from None
    return value


def serialize_get_ec_config_response(*, urls: dict[str, EvidencedURL] | None,
                                     error_code: str, status_source_ref: str,
                                     timestamp: str | None = None,
                                     error_message: str | None = None) -> bytes:
    """Serialize an explicit OFFLINE fixture; never an account/connect success.

    Verified retail-v21 semantics use the literal error code, not presence of an
    ErrorMessage, to decide reported error. Nonzero codes forbid URL fields;
    literal zero requires all five explicit URLs even with an informational
    message. URI validation is a local policy, not native URL admission behavior.
    """
    _source(status_source_ref)
    if (not isinstance(error_code, str) or not re.fullmatch(r'0|[1-9][0-9]{0,9}', error_code)
            or int(error_code) > 0xffffffff):
        raise EcConfigContractError('Expected explicit canonical uint32 fixture error status')
    if error_message is not None:
        _text(error_message)
    if timestamp is not None and (not isinstance(timestamp, str) or not re.fullmatch(r'[0-9]{1,20}', timestamp)):
        raise EcConfigContractError('Expected explicit decimal fixture timestamp')
    reported_error = error_code != '0'
    if reported_error:
        if urls is not None:
            raise EcConfigContractError('Reported-error fixtures must not supply URLs')
    elif not isinstance(urls, dict) or set(urls) != set(URL_FIELDS):
        raise EcConfigContractError('A zero-status fixture requires exactly five explicit URL fields')
    output = bytearray()

    def append_line(line):
        encoded = (line+'\n').encode('utf-8')
        if len(output)+len(encoded) > MAX_XML_BYTES:
            raise EcConfigContractError('Response exceeds local byte bound')
        output.extend(encoded)

    # The older source reader requires these lexical forms, not just namespaces.
    append_line('<?xml version="1.0" encoding="UTF-8"?>')
    append_line(f'<soapenv:Envelope xmlns:soapenv="{SOAP_NS}">')
    append_line('<soapenv:Body>')
    append_line(f'<GetECConfigResponse xmlns="{ECS_NS}">')
    if timestamp is not None:
        append_line(f'<TimeStamp>{timestamp}</TimeStamp>')
    append_line(f'<ErrorCode>{error_code}</ErrorCode>')
    if error_message is not None:
        append_line('<ErrorMessage>'+escape(error_message)+'</ErrorMessage>')
    if not reported_error:
        for name in URL_FIELDS:
            endpoint = urls[name]
            if not isinstance(endpoint, EvidencedURL):
                raise EcConfigContractError('Expected an explicitly evidenced offline URL')
            _source(endpoint.source_ref)
            value = _url(endpoint.value)
            append_line('<'+name+'>'+escape(value)+'</'+name+'>')
    append_line('</GetECConfigResponse>')
    append_line('</soapenv:Body>')
    append_line('</soapenv:Envelope>')
    return bytes(output)
