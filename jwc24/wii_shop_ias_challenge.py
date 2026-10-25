"""Offline IAS GetChallenge fixtures checked against the retail v21 operation.

No account route, challenge generator, credential check, signature, registration
or connected-state transition is implemented. Evidence references are explicit
caller assertions, not authorization or an independent provenance check.
"""
from dataclasses import dataclass, field
from io import StringIO
import re
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
IAS_NS = 'urn:ias.wsapi.broadon.com'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
GET_CHALLENGE_ACTION = IAS_NS+'/GetChallenge'
MAX_XML_BYTES = 64*1024
MAX_TEXT = 4096
MAX_ELEMENTS = 64
MAX_DEPTH = 5
MAX_NAMESPACES = 32
# The observed native limit is a byte count, including no terminator here.
MAX_CHALLENGE_BYTES = 11
_COMMON = ('Version', 'MessageId', 'DeviceId', 'DeviceToken', 'AccountId',
           'Region', 'Country', 'Language')
_REQUIRED = ('Version', 'MessageId', 'Region', 'Country', 'Language')


class ChallengeContractError(ValueError):
    """Invalid or unsupported offline fixture; messages exclude private values."""


def _text(value):
    if (not isinstance(value, str) or len(value) > MAX_TEXT
            or any(not (c in '\t\n\r' or '\x20' <= c <= '\ud7ff'
                        or '\ue000' <= c <= '\ufffd' or '\U00010000' <= c <= '\U0010ffff')
                   for c in value)):
        raise ChallengeContractError('Invalid or oversized XML text')
    return value


def _source(value):
    if not _text(value).strip():
        raise ChallengeContractError('An explicit offline evidence reference is required')


def _container(element):
    if (element.attrib or (element.text or '').strip()
            or any((child.tail or '').strip() for child in element)):
        raise ChallengeContractError('Unexpected XML container attributes or mixed text')


@dataclass(frozen=True)
class GetChallengeRequest:
    common_fields: tuple[tuple[str, str], ...] = field(repr=False)
    postal_code: str | None = field(default=None, repr=False)


def parse_get_challenge_request(data: bytes, *, soap_action: str) -> GetChallengeRequest:
    """Validate the observed IAS shape; opaque fields are never authenticated."""
    if not isinstance(soap_action, str) or soap_action not in (
            GET_CHALLENGE_ACTION, '"'+GET_CHALLENGE_ACTION+'"'):
        raise ChallengeContractError('Unsupported IAS SOAPAction')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES:
        raise ChallengeContractError('Invalid or oversized XML input')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        raise ChallengeContractError('Expected UTF-8 XML') from None
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ChallengeContractError('XML entity declarations are unsupported')
    scopes, pending, operation_scope = [], {}, {}
    elements = namespaces = 0
    try:
        parser = ET.iterparse(StringIO(text), events=('start-ns', 'start', 'end'))
        for event, item in parser:
            if event == 'start-ns':
                namespaces += 1
                if namespaces > MAX_NAMESPACES:
                    raise ChallengeContractError('XML namespace count exceeds local bound')
                pending[item[0]] = item[1]
            elif event == 'start':
                scope = dict(scopes[-1]) if scopes else {}
                scope.update(pending)
                pending.clear()
                scopes.append(scope)
                elements += 1
                if elements > MAX_ELEMENTS or len(scopes) > MAX_DEPTH:
                    raise ChallengeContractError('XML structure exceeds local bounds')
                if len(scopes) == 3:
                    operation_scope = scope
            else:
                scopes.pop()
        root = parser.root
    except ET.ParseError:
        raise ChallengeContractError('Malformed XML') from None
    if root.tag != f'{{{SOAP_NS}}}Envelope' or len(root) != 1:
        raise ChallengeContractError('Expected one SOAP 1.1 body')
    _container(root)
    body = root[0]
    if body.tag != f'{{{SOAP_NS}}}Body' or len(body) != 1:
        raise ChallengeContractError('Expected one SOAP operation')
    _container(body)
    operation = body[0]
    if operation.tag != f'{{{IAS_NS}}}GetChallenge':
        raise ChallengeContractError('Unsupported IAS operation')
    if set(operation.attrib)-{f'{{{XSI_NS}}}type'}:
        raise ChallengeContractError('Unsupported operation attributes')
    request_type = operation.attrib.get(f'{{{XSI_NS}}}type')
    if request_type is not None:
        parts = request_type.split(':')
        prefix, local = parts if len(parts) == 2 else ('', request_type)
        if local != 'GetChallengeRequestType' or operation_scope.get(prefix) != IAS_NS:
            raise ChallengeContractError('Unsupported IAS request type')
    if (operation.text or '').strip() or any((child.tail or '').strip() for child in operation):
        raise ChallengeContractError('Unexpected operation text')
    values = {}
    for element in operation:
        if not element.tag.startswith('{'+IAS_NS+'}'):
            raise ChallengeContractError('Unexpected IAS field namespace')
        name = element.tag[len(IAS_NS)+2:]
        if name not in (*_COMMON, 'Attributes'):
            raise ChallengeContractError('Unsupported IAS request field')
        if name in values:
            raise ChallengeContractError('Duplicate IAS request field')
        if name == 'Attributes':
            _container(element)
            if ([child.tag for child in element] != [f'{{{IAS_NS}}}Name', f'{{{IAS_NS}}}Value']
                    or any(child.attrib or len(child) for child in element)):
                raise ChallengeContractError('Unsupported IAS attribute structure')
            if _text(element[0].text or '') != 'PostalCode':
                raise ChallengeContractError('Unsupported IAS attribute name')
            values[name] = _text(element[1].text or '')
        else:
            if element.attrib or len(element):
                raise ChallengeContractError('Expected a simple IAS field')
            values[name] = _text(element.text or '')
    if any(name not in values for name in _REQUIRED):
        raise ChallengeContractError('Missing required IAS request field')
    if values['Version'] != '2.0':
        raise ChallengeContractError('Unsupported reviewed IAS request version')
    return GetChallengeRequest(tuple((name, values[name]) for name in _COMMON if name in values),
                               values.get('Attributes'))


@dataclass(frozen=True)
class EvidencedChallenge:
    value: str = field(repr=False)
    source_ref: str = field(repr=False)


def serialize_get_challenge_response(*, challenge: EvidencedChallenge | None,
                                     error_code: str, status_source_ref: str,
                                     timestamp: str | None = None,
                                     error_message: str | None = None) -> bytes:
    """Serialize an explicit offline IAS fixture; never generate a live challenge.

    V21 copies Challenge as raw element text, rather than decoding XML entities.
    The local fixture policy rejects XML metacharacters to preserve the exact
    supplied value instead of silently changing the challenge through escaping.
    Empty challenges are accepted by the tested native reader. That does not
    establish that an empty value can pass a real signing/registration service.
    """
    _source(status_source_ref)
    if (not isinstance(error_code, str) or not re.fullmatch(r'0|[1-9][0-9]{0,9}', error_code)
            or int(error_code) > 0xffffffff):
        raise ChallengeContractError('Expected explicit canonical uint32 fixture status')
    if timestamp is not None and (not isinstance(timestamp, str) or not re.fullmatch(r'[0-9]{1,20}', timestamp)):
        raise ChallengeContractError('Expected explicit decimal fixture timestamp')
    if error_message is not None:
        _text(error_message)
    if error_code != '0':
        if challenge is not None:
            raise ChallengeContractError('Reported-error fixtures must not supply a challenge')
    else:
        if type(challenge) is not EvidencedChallenge:
            raise ChallengeContractError('Zero-status fixtures need an explicitly evidenced challenge')
        _source(challenge.source_ref)
        value = _text(challenge.value)
        if len(value.encode('utf-8')) > MAX_CHALLENGE_BYTES or any(c in '&<>' for c in value):
            raise ChallengeContractError('Challenge exceeds native byte capacity or local raw-text policy')
    output = bytearray()

    def append(line):
        encoded = (line+'\n').encode('utf-8')
        if len(output)+len(encoded) > MAX_XML_BYTES:
            raise ChallengeContractError('Response exceeds local byte bound')
        output.extend(encoded)

    append('<?xml version="1.0" encoding="UTF-8"?>')
    append(f'<soapenv:Envelope xmlns:soapenv="{SOAP_NS}">')
    append('<soapenv:Body>')
    append(f'<GetChallengeResponse xmlns="{IAS_NS}">')
    if timestamp is not None:
        append(f'<TimeStamp>{timestamp}</TimeStamp>')
    append(f'<ErrorCode>{error_code}</ErrorCode>')
    if error_message is not None:
        append('<ErrorMessage>'+escape(error_message)+'</ErrorMessage>')
    if error_code == '0':
        append('<Challenge>'+challenge.value+'</Challenge>')
    append('</GetChallengeResponse>')
    append('</soapenv:Body>')
    append('</soapenv:Envelope>')
    return bytes(output)
