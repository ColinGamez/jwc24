"""Offline IAS registration-sync wire facts; no signer, authority or account route.

Explicit response facts are caller assertions, never authentication or ownership.
Both reviewed operation names are retained without substituting their meanings.
"""
from dataclasses import dataclass, field
import hashlib
from io import StringIO
import re
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
IAS_NS = 'urn:ias.wsapi.broadon.com'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
OPERATIONS = ('SyncRegistration', 'GetRegistrationInfo')
_PROOF = ('DeviceCert', 'Signature', 'CertChain', 'Challenge')
MAX_XML_BYTES = 64*1024
MAX_TEXT = 4096
MAX_ELEMENTS = 64
MAX_DEPTH = 5
MAX_NAMESPACES = 32
_COMMON = ('Version', 'MessageId', 'DeviceId', 'DeviceToken', 'AccountId',
           'Region', 'Country', 'Language')
_REQUIRED = ('Version', 'MessageId', 'Region', 'Country', 'Language')


class RegistrationContractError(ValueError):
    """Invalid or unsupported offline fixture; messages exclude private values."""


def _text(value):
    if (not isinstance(value, str) or len(value) > MAX_TEXT
            or any(not (c in '\t\n\r' or '\x20' <= c <= '\ud7ff'
                        or '\ue000' <= c <= '\ufffd' or '\U00010000' <= c <= '\U0010ffff')
                   for c in value)):
        raise RegistrationContractError('Invalid or oversized XML text')
    return value


def _source(value):
    if not _text(value).strip():
        raise RegistrationContractError('An explicit offline evidence reference is required')


def _container(element):
    if (element.attrib or (element.text or '').strip()
            or any((child.tail or '').strip() for child in element)):
        raise RegistrationContractError('Unexpected XML container attributes or mixed text')


@dataclass(frozen=True)
class RegistrationSyncRequest:
    operation: str
    common_fields: tuple[tuple[str, str], ...] = field(repr=False)
    proof_fields: tuple[tuple[str, str], ...] = field(repr=False)
    postal_code: str | None = field(default=None, repr=False)


def parse_registration_sync_request(data: bytes, *, soap_action: str) -> RegistrationSyncRequest:
    """Validate the observed IAS shape; opaque fields are never authenticated."""
    if not isinstance(soap_action, str):
        raise RegistrationContractError('Unsupported IAS SOAPAction')
    action = soap_action[1:-1] if soap_action.startswith('"') and soap_action.endswith('"') else soap_action
    operation_name = next((name for name in OPERATIONS if action == IAS_NS+'/'+name), None)
    if operation_name is None:
        raise RegistrationContractError('Unsupported IAS SOAPAction')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES:
        raise RegistrationContractError('Invalid or oversized XML input')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        raise RegistrationContractError('Expected UTF-8 XML') from None
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise RegistrationContractError('XML entity declarations are unsupported')
    scopes, pending, operation_scope = [], {}, {}
    elements = namespaces = 0
    try:
        parser = ET.iterparse(StringIO(text), events=('start-ns', 'start', 'end'))
        for event, item in parser:
            if event == 'start-ns':
                namespaces += 1
                if namespaces > MAX_NAMESPACES:
                    raise RegistrationContractError('XML namespace count exceeds local bound')
                pending[item[0]] = item[1]
            elif event == 'start':
                scope = dict(scopes[-1]) if scopes else {}
                scope.update(pending)
                pending.clear()
                scopes.append(scope)
                elements += 1
                if elements > MAX_ELEMENTS or len(scopes) > MAX_DEPTH:
                    raise RegistrationContractError('XML structure exceeds local bounds')
                if len(scopes) == 3:
                    operation_scope = scope
            else:
                scopes.pop()
        root = parser.root
    except ET.ParseError:
        raise RegistrationContractError('Malformed XML') from None
    if root.tag != f'{{{SOAP_NS}}}Envelope' or len(root) != 1:
        raise RegistrationContractError('Expected one SOAP 1.1 body')
    _container(root)
    body = root[0]
    if body.tag != f'{{{SOAP_NS}}}Body' or len(body) != 1:
        raise RegistrationContractError('Expected one SOAP operation')
    _container(body)
    operation = body[0]
    if operation.tag != f'{{{IAS_NS}}}{operation_name}':
        raise RegistrationContractError('Unsupported IAS operation')
    if set(operation.attrib)-{f'{{{XSI_NS}}}type'}:
        raise RegistrationContractError('Unsupported operation attributes')
    request_type = operation.attrib.get(f'{{{XSI_NS}}}type')
    if request_type is not None:
        parts = request_type.split(':')
        prefix, local = parts if len(parts) == 2 else ('', request_type)
        if local != operation_name+'RequestType' or operation_scope.get(prefix) != IAS_NS:
            raise RegistrationContractError('Unsupported IAS request type')
    if (operation.text or '').strip() or any((child.tail or '').strip() for child in operation):
        raise RegistrationContractError('Unexpected operation text')
    values = {}
    for element in operation:
        if not element.tag.startswith('{'+IAS_NS+'}'):
            raise RegistrationContractError('Unexpected IAS field namespace')
        name = element.tag[len(IAS_NS)+2:]
        if name not in (*_COMMON, *_PROOF, 'Attributes'):
            raise RegistrationContractError('Unsupported IAS request field')
        if name in values:
            raise RegistrationContractError('Duplicate IAS request field')
        if name == 'Attributes':
            _container(element)
            if ([child.tag for child in element] != [f'{{{IAS_NS}}}Name', f'{{{IAS_NS}}}Value']
                    or any(child.attrib or len(child) for child in element)):
                raise RegistrationContractError('Unsupported IAS attribute structure')
            if _text(element[0].text or '') != 'PostalCode':
                raise RegistrationContractError('Unsupported IAS attribute name')
            values[name] = _text(element[1].text or '')
        else:
            if element.attrib or len(element):
                raise RegistrationContractError('Expected a simple IAS field')
            values[name] = _text(element.text or '')
    if any(name not in values for name in (*_REQUIRED, *_PROOF)):
        raise RegistrationContractError('Missing required IAS request field')
    if values['Version'] != '2.0':
        raise RegistrationContractError('Unsupported reviewed IAS request version')
    if not values['Challenge']:
        raise RegistrationContractError('Registration sync requires a nonempty challenge')
    return RegistrationSyncRequest(operation_name, tuple((name, values[name]) for name in _COMMON if name in values),
                                   tuple((name, values[name]) for name in _PROOF), values.get('Attributes'))


def registration_sync_signing_bytes(request: RegistrationSyncRequest) -> bytes:
    """Return the exact native sync message bytes, never sign or verify them.

    Native sync signs literal UTF-8 concatenation around the challenge. SOAP
    proof elements use XML escaping separately. Re-serializing an XML tree would
    change signed bytes for a metacharacter and is therefore not equivalent.
    Register/Transfer/Unregister sign additional fields and are outside scope.
    """
    if (type(request) is not RegistrationSyncRequest or request.operation not in OPERATIONS
            or type(request.proof_fields) is not tuple or len(request.proof_fields) != len(_PROOF)):
        raise RegistrationContractError('Expected the reviewed explicit registration-sync request')
    for pair, name in zip(request.proof_fields, _PROOF):
        if type(pair) is not tuple or len(pair) != 2 or pair[0] != name:
            raise RegistrationContractError('Expected the reviewed explicit proof fields')
        _text(pair[1])
    challenge = dict(request.proof_fields)['Challenge']
    if not challenge:
        raise RegistrationContractError('Registration sync requires a nonempty challenge')
    return b'<Challenge>'+challenge.encode('utf-8')+b'</Challenge>'


@dataclass(frozen=True)
class EvidencedRegistration:
    """Explicit offline account facts, not proof that the account/device is valid."""
    account_id: str = field(repr=False)
    device_token: str = field(repr=False)
    country: str = field(repr=False)
    token_expired: bool | None = field(repr=False)
    ext_account_id: str | None = field(repr=False)
    device_code: str | None = field(repr=False)
    source_ref: str = field(repr=False)


def _raw_text(value):
    value = _text(value)
    # The native reader retains raw XML element text. Escaping would silently
    # change opaque account/token values, so this serializer rejects that form.
    if any(c in '&<>' for c in value):
        raise RegistrationContractError('Opaque registration facts conflict with local raw-text policy')
    return value


def _response_facts(registration, error_code, status_source_ref):
    _source(status_source_ref)
    if (not isinstance(error_code, str) or not re.fullmatch(r'0|[1-9][0-9]{0,9}', error_code)
            or int(error_code) > 0xffffffff):
        raise RegistrationContractError('Expected canonical explicit uint32 fixture status')
    if error_code == '0':
        if type(registration) is not EvidencedRegistration:
            raise RegistrationContractError('Zero-status fixture needs explicitly evidenced registration facts')
        _source(registration.source_ref)
        for name in ('account_id', 'device_token', 'country'):
            _raw_text(getattr(registration, name))
        for name in ('ext_account_id', 'device_code'):
            value = getattr(registration, name)
            if value is not None:
                _raw_text(value)
        if registration.token_expired is not None and type(registration.token_expired) is not bool:
            raise RegistrationContractError('Expected explicit boolean or omitted token-expiry fact')
    elif registration is not None:
        raise RegistrationContractError('Reported-error fixture must not supply account facts')


def serialize_registration_sync_response(*, operation: str,
        registration: EvidencedRegistration | None, error_code: str,
        status_source_ref: str, timestamp: str | None = None,
        error_message: str | None = None) -> bytes:
    """Serialize an explicit fixture; never generate an account, token or proof.

    Status 901 is retained as an error on the wire. The original sync consumer
    may map it to an unregistered result; that mapping is not authentication.
    """
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise RegistrationContractError('Unsupported IAS registration-sync operation')
    _response_facts(registration, error_code, status_source_ref)
    if timestamp is not None and (not isinstance(timestamp, str) or not re.fullmatch(r'[0-9]{1,20}', timestamp)):
        raise RegistrationContractError('Expected explicit decimal fixture timestamp')
    if error_message is not None:
        _text(error_message)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
        f'<soapenv:Envelope xmlns:soapenv="{SOAP_NS}">', '<soapenv:Body>',
        f'<{operation}Response xmlns="{IAS_NS}">']
    if timestamp is not None:
        lines.append(f'<TimeStamp>{timestamp}</TimeStamp>')
    lines.append(f'<ErrorCode>{error_code}</ErrorCode>')
    if error_message is not None:
        lines.append('<ErrorMessage>'+escape(error_message)+'</ErrorMessage>')
    if error_code == '0':
        lines.extend([f'<AccountId>{registration.account_id}</AccountId>',
                      f'<DeviceToken>{registration.device_token}</DeviceToken>'])
        if registration.token_expired is not None:
            lines.append('<DeviceTokenExpired>'+str(registration.token_expired).lower()+'</DeviceTokenExpired>')
        lines.append(f'<Country>{registration.country}</Country>')
        for tag, value in (('ExtAccountId', registration.ext_account_id), ('DeviceCode', registration.device_code)):
            if value is not None:
                lines.append(f'<{tag}>{value}</{tag}>')
    lines.extend([f'</{operation}Response>', '</soapenv:Body>', '</soapenv:Envelope>'])
    data = ('\n'.join(lines)+'\n').encode('utf-8')
    if len(data) > MAX_XML_BYTES:
        raise RegistrationContractError('Response exceeds local byte bound')
    return data


@dataclass(frozen=True)
class RegistrationSyncState:
    """Explicit local snapshot; no profile, account authority or credential IO."""
    account_id: str = field(repr=False)
    device_token: str = field(repr=False)
    strong_token: str = field(repr=False)
    weak_token: str = field(repr=False)
    country: str = field(repr=False)
    ext_account_id: str = field(repr=False)
    device_code: str = field(repr=False)
    need_ticket_sync: bool
    import_all: bool
    force_sync_time: int = field(repr=False)
    ext_ticket_time: int = field(repr=False)
    sync_time: int = field(repr=False)
    last_ticket_sync_time: int = field(repr=False)


@dataclass(frozen=True)
class RegistrationSyncPlan:
    state: RegistrationSyncState = field(repr=False)
    status: int
    unregistered: bool
    save_config_requested: bool
    account_or_device_authorized: bool = field(default=False, init=False)


def plan_ecdk_registration_sync(state: RegistrationSyncState, *,
        registration: EvidencedRegistration | None, error_code: str,
        status_source_ref: str) -> RegistrationSyncPlan:
    """Pure plan for complete IAS responses in the real connection worker's mode.

    The connection worker sets useECDKSyncRegistration before calling sync. The
    other mode can request title removal and is intentionally outside this pure
    planner. Partial parsing/signing/transport failures are also outside scope.
    MD5 here reproduces the old weak-token derivation, not a signature or proof.
    """
    if type(state) is not RegistrationSyncState:
        raise RegistrationContractError('Expected explicit registration sync snapshot')
    for name in ('account_id', 'device_token', 'strong_token', 'weak_token',
                 'country', 'ext_account_id', 'device_code'):
        _text(getattr(state, name))
    for name in ('need_ticket_sync', 'import_all'):
        if type(getattr(state, name)) is not bool:
            raise RegistrationContractError('Expected explicit local registration flags')
    for name in ('force_sync_time', 'ext_ticket_time', 'sync_time', 'last_ticket_sync_time'):
        value = getattr(state, name)
        if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
            raise RegistrationContractError('Expected explicit signed sync-time snapshot')
    _response_facts(registration, error_code, status_source_ref)

    def result(snapshot, status, unregistered, save):
        return RegistrationSyncPlan(snapshot, status, unregistered, save)

    if error_code not in ('0', '901'):
        return result(state, -4015, False, False)
    if error_code == '901':
        cleared = RegistrationSyncState('', '', '', '', '', '', '', True, state.import_all, 0, 0, 0, 0)
        return result(cleared, 0, True, True)
    token = registration.device_token
    strong = 'ST-'+token if token else ''
    weak = 'WT-'+hashlib.md5(token.encode('utf-8'), usedforsecurity=False).hexdigest() if token else ''
    updated = RegistrationSyncState(registration.account_id, registration.device_token,
        strong, weak, registration.country, registration.ext_account_id or '', registration.device_code or '',
        state.need_ticket_sync, state.import_all, state.force_sync_time, state.ext_ticket_time,
        state.sync_time, state.last_ticket_sync_time)
    return result(updated, -4042 if registration.token_expired else 0, False, True)
