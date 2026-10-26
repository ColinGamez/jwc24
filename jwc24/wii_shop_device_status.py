"""Offline ECS CheckDeviceStatus facts and pure sync-update plan.

No route, network, identity, connected-state or endpoint default is implemented.
The request includes native optional PostalCode. Evidence references are caller
assertions, not authentication. No point/ownership authority is inferred.
"""
from dataclasses import dataclass, field
from io import StringIO
import re
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
ECS_NS = 'urn:ecs.wsapi.broadon.com'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
CHECK_DEVICE_STATUS_ACTION = ECS_NS+'/CheckDeviceStatus'
# Defensive JWC24 XML bounds, not recovered native acceptance limits.
MAX_XML_BYTES = 64*1024
MAX_TEXT = 4096
MAX_ELEMENTS = 64
MAX_DEPTH = 5
MAX_NAMESPACES = 32
_COMMON = ('Version', 'MessageId', 'DeviceId', 'DeviceToken', 'AccountId',
           'ApplicationId', 'TIN', 'Region', 'Country', 'Language', 'SerialNo')
_REQUIRED = ('Version', 'MessageId', 'Region', 'Country', 'Language', 'SerialNo')


class DeviceStatusContractError(ValueError):
    """Malformed or unsupported offline input; messages never include values."""


def _text(value):
    if (not isinstance(value, str) or len(value) > MAX_TEXT
            or any(not (c in '\t\n\r' or '\x20' <= c <= '\ud7ff'
                        or '\ue000' <= c <= '\ufffd' or '\U00010000' <= c <= '\U0010ffff')
                   for c in value)):
        raise DeviceStatusContractError('Invalid or oversized XML text')
    return value


def _source(value):
    if not _text(value).strip():
        raise DeviceStatusContractError('An explicit fixture evidence reference is required')


def _container(element):
    if (element.attrib or (element.text or '').strip()
            or any((child.tail or '').strip() for child in element)):
        raise DeviceStatusContractError('Unexpected XML container attributes or mixed text')


@dataclass(frozen=True)
class CheckDeviceStatusRequest:
    # Opaque account/device fields confer no authentication and stay private.
    common_fields: tuple[tuple[str, str], ...] = field(repr=False)
    postal_code: str | None = field(default=None, repr=False)


def parse_check_device_status_request(data: bytes, *, soap_action: str) -> CheckDeviceStatusRequest:
    """Structurally validate the reviewed ECS request subset, without authenticating.

    Prefix spelling is arbitrary. xsi:type may be absent; when present it must
    resolve to the ECS CheckDeviceStatusRequestType. SerialNo is an ECS common field;
    the CAS-only Age field and CAS namespace/action are intentionally rejected.
    A single native Attributes/PostalCode pair is retained as opaque private
    text. Unknown attribute names and repeated pairs are outside this subset.
    """
    if not isinstance(soap_action, str) or soap_action not in (
            CHECK_DEVICE_STATUS_ACTION, '"'+CHECK_DEVICE_STATUS_ACTION+'"'):
        raise DeviceStatusContractError('Unsupported ECS SOAPAction')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML_BYTES:
        raise DeviceStatusContractError('Invalid or oversized XML input')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise DeviceStatusContractError('Expected UTF-8 XML') from None
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise DeviceStatusContractError('XML entity declarations are unsupported')
    scopes, pending, operation_scope = [], {}, {}
    elements = namespaces = 0
    try:
        parser = ET.iterparse(StringIO(text), events=('start-ns', 'start', 'end'))
        for event, item in parser:
            if event == 'start-ns':
                namespaces += 1
                if namespaces > MAX_NAMESPACES:
                    raise DeviceStatusContractError('XML namespace count exceeds local bound')
                pending[item[0]] = item[1]
            elif event == 'start':
                scope = dict(scopes[-1]) if scopes else {}
                scope.update(pending)
                pending.clear()
                scopes.append(scope)
                elements += 1
                if elements > MAX_ELEMENTS or len(scopes) > MAX_DEPTH:
                    raise DeviceStatusContractError('XML structure exceeds local bounds')
                if len(scopes) == 3:
                    operation_scope = scope
            else:
                scopes.pop()
        root = parser.root
    except ET.ParseError:
        raise DeviceStatusContractError('Malformed XML') from None
    if root.tag != f'{{{SOAP_NS}}}Envelope' or len(root) != 1:
        raise DeviceStatusContractError('Expected one SOAP 1.1 body')
    _container(root)
    body = root[0]
    if body.tag != f'{{{SOAP_NS}}}Body' or len(body) != 1:
        raise DeviceStatusContractError('Expected one SOAP operation')
    _container(body)
    operation = body[0]
    if operation.tag != f'{{{ECS_NS}}}CheckDeviceStatus':
        raise DeviceStatusContractError('Unsupported ECS operation')
    if set(operation.attrib)-{f'{{{XSI_NS}}}type'}:
        raise DeviceStatusContractError('Unsupported operation attributes')
    request_type = operation.attrib.get(f'{{{XSI_NS}}}type')
    if request_type is not None:
        parts = request_type.split(':')
        prefix, local = parts if len(parts) == 2 else ('', request_type)
        if local != 'CheckDeviceStatusRequestType' or operation_scope.get(prefix) != ECS_NS:
            raise DeviceStatusContractError('Unsupported ECS request type')
    if (operation.text or '').strip() or any((child.tail or '').strip() for child in operation):
        raise DeviceStatusContractError('Unexpected operation text')
    values = {}
    for element in operation:
        if not element.tag.startswith('{'+ECS_NS+'}'):
            raise DeviceStatusContractError('Unexpected ECS field namespace')
        name = element.tag[len(ECS_NS)+2:]
        if name not in (*_COMMON, 'Attributes'):
            raise DeviceStatusContractError('Unsupported ECS request field')
        if name in values:
            raise DeviceStatusContractError('Duplicate ECS request field')
        if name == 'Attributes':
            _container(element)
            if [child.tag for child in element] != [f'{{{ECS_NS}}}Name', f'{{{ECS_NS}}}Value']:
                raise DeviceStatusContractError('Unsupported ECS configuration attribute structure')
            if any(child.attrib or len(child) for child in element):
                raise DeviceStatusContractError('Expected simple ECS configuration attribute fields')
            if _text(element[0].text or '') != 'PostalCode':
                raise DeviceStatusContractError('Unsupported ECS configuration attribute name')
            values[name] = _text(element[1].text or '')
            continue
        if element.attrib or len(element):
            raise DeviceStatusContractError('Expected a simple ECS field')
        values[name] = _text(element.text or '')
    if any(name not in values for name in _REQUIRED):
        raise DeviceStatusContractError('Missing required ECS request field')
    if values['Version'] != '2.0':
        raise DeviceStatusContractError('Unsupported reviewed request version')
    return CheckDeviceStatusRequest(tuple((k, values[k]) for k in _COMMON if k in values),
                              values.get('Attributes'))


def _integer(value, bits):
    if type(value) is not int or not -(1 << (bits-1)) <= value < (1 << (bits-1)):
        raise DeviceStatusContractError('Expected explicit bounded signed integer fact')


@dataclass(frozen=True)
class EvidencedDeviceStatus:
    """Explicit fixture facts; source_ref asserts provenance without verifying it."""
    points_balance: int = field(repr=False)
    force_sync_time: int = field(repr=False)
    ext_ticket_time: int = field(repr=False)
    sync_time: int = field(repr=False)
    source_ref: str = field(repr=False)


def _facts(value):
    if type(value) is not EvidencedDeviceStatus:
        raise DeviceStatusContractError('Expected explicitly evidenced status facts')
    _source(value.source_ref)
    _integer(value.points_balance, 32)
    for name in ('force_sync_time', 'ext_ticket_time', 'sync_time'):
        _integer(getattr(value, name), 64)


@dataclass(frozen=True)
class LocalSyncState:
    """Caller-supplied snapshot; never loaded from or saved to a device here."""
    points_balance: int = field(repr=False)
    force_sync_time: int = field(repr=False)
    ext_ticket_time: int = field(repr=False)
    sync_time: int = field(repr=False)
    points_cached: bool
    need_ticket_sync: bool
    import_all: bool
    checked: bool
    times_match: bool
    ecdk: bool


def validate_sync_state(value):
    if type(value) is not LocalSyncState:
        raise DeviceStatusContractError('Expected explicit local sync snapshot')
    _integer(value.points_balance, 32)
    for name in ('force_sync_time', 'ext_ticket_time', 'sync_time'):
        _integer(getattr(value, name), 64)
    for name in ('points_cached', 'need_ticket_sync', 'import_all', 'checked', 'times_match', 'ecdk'):
        if type(getattr(value, name)) is not bool:
            raise DeviceStatusContractError('Expected explicit local boolean flags')


@dataclass(frozen=True)
class SyncUpdatePlan:
    state: LocalSyncState = field(repr=False)
    save_config_requested: bool
    make_shop_log_requested: bool
    clear_sync_needed_requested: bool
    account_or_device_authorized: bool = field(default=False, init=False)


def plan_device_status_update(state: LocalSyncState, facts: EvidencedDeviceStatus) -> SyncUpdatePlan:
    """Pure plan for a COMPLETE zero-status response; perform no side effects.

    Original run() does not overwrite local sync times here, clear a previously
    pending sync/import-all flag, or propagate saveConfig failure. Partial native
    extraction can update points before later field failure; this planner only
    accepts complete typed facts and is not that partial-state error path.
    """
    validate_sync_state(state)
    _facts(facts)
    same = all(getattr(state, k) == getattr(facts, k)
               for k in ('force_sync_time', 'ext_ticket_time', 'sync_time'))
    need_sync = state.need_ticket_sync or not same
    updated = LocalSyncState(facts.points_balance, state.force_sync_time,
        state.ext_ticket_time, state.sync_time, True, need_sync,
        state.import_all or state.force_sync_time != facts.force_sync_time,
        True, same, state.ecdk)
    return SyncUpdatePlan(updated, not same and not state.need_ticket_sync,
                          not state.ecdk, not state.ecdk and not need_sync)


def serialize_check_device_status_response(*, facts: EvidencedDeviceStatus | None,
        error_code: str, status_source_ref: str, timestamp: str | None = None,
        error_message: str | None = None) -> bytes:
    """Serialize explicit offline facts/errors; never infer balance or entitlement."""
    _source(status_source_ref)
    if (not isinstance(error_code, str) or not re.fullmatch(r'0|[1-9][0-9]{0,9}', error_code)
            or int(error_code) > 0xffffffff):
        raise DeviceStatusContractError('Expected canonical explicit uint32 fixture status')
    if timestamp is not None and (not isinstance(timestamp, str) or not re.fullmatch(r'[0-9]{1,20}', timestamp)):
        raise DeviceStatusContractError('Expected explicit decimal fixture timestamp')
    if error_message is not None:
        _text(error_message)
    if error_code == '0':
        _facts(facts)
    elif facts is not None:
        raise DeviceStatusContractError('Reported-error fixture must not supply status facts')
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<soapenv:Envelope xmlns:soapenv="{SOAP_NS}">', '<soapenv:Body>',
             f'<CheckDeviceStatusResponse xmlns="{ECS_NS}">']
    if timestamp is not None:
        lines.append(f'<TimeStamp>{timestamp}</TimeStamp>')
    lines.append(f'<ErrorCode>{error_code}</ErrorCode>')
    if error_message is not None:
        lines.append('<ErrorMessage>'+escape(error_message)+'</ErrorMessage>')
    if error_code == '0':
        lines.extend(['<Balance>', f'<Amount>{facts.points_balance}</Amount>',
            '<Currency>POINTS</Currency>', '</Balance>',
            f'<ForceSyncTime>{facts.force_sync_time}</ForceSyncTime>',
            f'<ExtTicketTime>{facts.ext_ticket_time}</ExtTicketTime>',
            f'<SyncTime>{facts.sync_time}</SyncTime>'])
    lines.extend(['</CheckDeviceStatusResponse>', '</soapenv:Body>', '</soapenv:Envelope>'])
    data = ('\n'.join(lines)+'\n').encode('utf-8')
    if len(data) > MAX_XML_BYTES:
        raise DeviceStatusContractError('Response exceeds local byte bound')
    return data
