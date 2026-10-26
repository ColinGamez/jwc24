"""Observed CMOC HTTP-completion/header checks, without authentication claims."""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from .cmoc import CMOCFormatError, ResponseHeader
from .cmoc_startup import FirstDataResponse, inspect_first_data_response


@dataclass(frozen=True)
class ResponseGate:
    completion_code: int
    header_gate_passed: bool
    body_header_checked: bool
    next_byte_3: int = field(repr=False)
    byte_3_changed: bool
    http_status_checked: bool
    x_result_checked: bool

    def metadata(self):
        return {'observed_completion_code': self.completion_code,
                'header_gate_passed': self.header_gate_passed,
                'body_header_checked': self.body_header_checked,
                'byte_3_state_changed': self.byte_3_changed,
                'http_status_checked': self.http_status_checked,
                'parsed_x_result_checked': self.x_result_checked,
                'http_header_text_parsing_checked': False,
                'authentication_or_startup_verified': False}


def evaluate_response_gate(data: bytes, *, expected_request: bytes | None,
                           http_status: int, x_result: int, response_flags: int,
                           limit_byte_2: int, learned_byte_3: int) -> ResponseGate:
    """Mirror the selected native completion handler's observed branch ordering.

    All parsed transport values and opaque state bytes are explicit. A None
    request represents the native missing-cache case, whose completion is zero
    even though no header has been checked. Zero alone is never a success flag.
    Host override processing and HTTP header text parsing remain outside scope.
    """
    if type(data) is not bytes or len(data) > 1024 * 1024:
        raise ValueError('Expected bounded CMOC completion bytes')
    if expected_request is not None and (type(expected_request) is not bytes or len(expected_request) != 32):
        raise ValueError('Expected one explicit 32-byte request header or missing request')
    for value in (http_status, x_result):
        if type(value) is not int or not -0x80000000 <= value <= 0x7FFFFFFF:
            raise ValueError('Expected explicit signed native transport value')
    for value in (response_flags, limit_byte_2, learned_byte_3):
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError('Expected explicit unsigned CMOC state byte')
    checked = False
    next_byte = learned_byte_3
    code = 0
    passed = False
    if expected_request is None:
        pass
    elif http_status >= 300:
        code = http_status + 0x3EFD0
    elif x_result >= 100:
        code = x_result + 0x3EBE8
    elif response_flags & 0x40:
        code = 0x3D8C5
    elif response_flags & 0x10:
        code = 0x3D929
    elif not response_flags & 0x20:
        pass
    elif len(data) < 32:
        code = 0x3D98D
    else:
        checked = True
        actual = ResponseHeader(*struct.unpack_from('>HBBII', data))
        expected = ResponseHeader(*struct.unpack_from('>HBBII', expected_request))
        if not actual.matches_request(expected):
            code = 0x3D98E
        elif actual.byte_2 == 255:
            code = 0x3D8C6
        elif actual.byte_2 > limit_byte_2:
            code = 0x3D8C7
        elif learned_byte_3 != 255 and actual.byte_3 != learned_byte_3:
            code = 0x3D8C8
        else:
            passed = True
            if learned_byte_3 == 255:
                next_byte = actual.byte_3
    return ResponseGate(code, passed, checked, next_byte, next_byte != learned_byte_3,
                        expected_request is not None,
                        expected_request is not None and http_status < 300)


@dataclass(frozen=True)
class FirstDataCompletion:
    gate: ResponseGate
    response: FirstDataResponse = field(repr=False)

    def metadata(self):
        return {**self.response.metadata(), **self.gate.metadata(),
                'header_byte_2_and_3_checks_executed': True,
                'http_status_or_x_result_checked': True,
                'signatures_or_encryption_checked': False}


def inspect_first_data_completion(data: bytes, *, expected_request: bytes,
                                  http_status: int, x_result: int, response_flags: int,
                                  limit_byte_2: int, learned_byte_3: int) -> FirstDataCompletion:
    """Combine the observed header gate with the existing safe framed FD decoder.

    This stricter backend handoff rejects zero-code incomplete/no-request cases.
    It does not produce HTTP responses, persist native state or authenticate data.
    """
    gate = evaluate_response_gate(data, expected_request=expected_request,
                                 http_status=http_status, x_result=x_result,
                                 response_flags=response_flags, limit_byte_2=limit_byte_2,
                                 learned_byte_3=learned_byte_3)
    if not gate.header_gate_passed:
        raise CMOCFormatError('CMOC completion did not pass the observed body-header gate')
    expected = ResponseHeader(*struct.unpack_from('>HBBII', expected_request))
    response = inspect_first_data_response(data, expected_request=expected)
    return FirstDataCompletion(gate, response)
