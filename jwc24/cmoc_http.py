"""Observed CMOC SDK header lookup/conversion over an explicit safe HTTP subset."""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from .cmoc import CMOCFormatError, CMOCUnsupportedFormat
from .cmoc_response_gate import inspect_first_data_completion

_TOKEN = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")


@dataclass(frozen=True)
class CompletionTransport:
    http_status: int
    x_result: int
    host_override: bytes | None = field(repr=False)
    response_available: bool
    response_ready: bool
    x_result_fields: int
    host_override_fields: int

    def metadata(self):
        return {'http_status_field': self.http_status, 'parsed_x_result': self.x_result,
                'response_available': self.response_available, 'response_ready': self.response_ready,
                'host_override_present': self.host_override is not None,
                'x_result_fields': self.x_result_fields, 'host_override_fields': self.host_override_fields,
                'http_wire_status_line_parsing_verified': False,
                'host_override_processing_verified': False,
                'authentication_or_startup_verified': False}


def decode_completion_transport(*, status_field: int | None, response_ready: bool,
                                 headers: tuple[tuple[bytes, bytes], ...]) -> CompletionTransport:
    """Mirror first matching SDK header lookup and native ``%03d`` conversion.

    Inputs are explicit post-HTTP-parser state, not raw response wire bytes.
    Missing/malformed X-RESULT produces the original initialized integer zero.
    The native scanf field width is THREE characters after whitespace, including
    any sign: for example 0100 becomes 10, and -100 becomes -10.
    """
    if status_field is not None and (type(status_field) is not int
                                     or not -0x80000000 <= status_field <= 0x7FFFFFFF):
        raise ValueError('Expected explicit signed SDK status field or unavailable response')
    if type(response_ready) is not bool or type(headers) not in (tuple, list) or len(headers) > 64:
        raise ValueError('Expected explicit ready flag and bounded HTTP header pairs')
    size = 19  # Synthetic status line plus final CRLF, used only to cap the safe subset.
    selected = {b'x-result': [], b'x-mc-host': []}
    for pair in headers:
        if type(pair) not in (tuple, list) or len(pair) != 2:
            raise ValueError('Expected bounded HTTP header name/value pairs')
        name, value = pair
        if (type(name) is not bytes or not 1 <= len(name) <= 64 or not _TOKEN.fullmatch(name)
                or type(value) is not bytes or len(value) > 256
                or any(byte != 9 and not 32 <= byte <= 126 for byte in value)):
            raise ValueError('HTTP header pair is outside the reviewed ASCII subset')
        size += len(name) + len(value) + 4
        if size > 1024:
            raise ValueError('HTTP headers exceed the reviewed inline SDK buffer subset')
        key = name.lower()
        if key in selected:
            selected[key].append(value)
    available = status_field is not None
    status = status_field if available and response_ready else -1
    raw_result = selected[b'x-result'][0] if selected[b'x-result'] else b''
    value = 0
    if available and response_ready:
        # Leading scanf whitespace is excluded from its maximum field width.
        match = re.match(rb'[+-]?[0-9]+', raw_result.lstrip(b' \t')[:3])
        if match:
            value = int(match[0])
    # The observed SDK lookup skips leading ASCII spaces only; trailing
    # whitespace and leading tabs remain part of its returned header value.
    host = (selected[b'x-mc-host'][0].lstrip(b' ')
            if available and response_ready and selected[b'x-mc-host'] else None)
    return CompletionTransport(status, value, host, available, response_ready,
                               len(selected[b'x-result']), len(selected[b'x-mc-host']))


def inspect_first_data_http_completion(data: bytes, *, status_field: int | None,
                                       response_ready: bool, headers,
                                       expected_request: bytes, response_flags: int,
                                       limit_byte_2: int, learned_byte_3: int):
    """Hand parsed SDK-equivalent HTTP data through the gate and FD decoder.

    Ambiguous selected headers and host-override processing are outside this
    safe handoff. This stricter policy does not claim native rejection of them.
    """
    transport = decode_completion_transport(status_field=status_field,
                                            response_ready=response_ready, headers=headers)
    if not transport.response_available or not response_ready:
        raise CMOCFormatError('CMOC HTTP response state is unavailable or incomplete')
    if transport.x_result_fields > 1 or transport.host_override_fields > 1:
        raise CMOCUnsupportedFormat('Ambiguous CMOC completion headers require separate handling')
    if transport.host_override is not None:
        raise CMOCUnsupportedFormat('CMOC host-override processing is outside this handoff')
    result = inspect_first_data_completion(data, expected_request=expected_request,
                                          http_status=transport.http_status, x_result=transport.x_result,
                                          response_flags=response_flags, limit_byte_2=limit_byte_2,
                                          learned_byte_3=learned_byte_3)
    return transport, result
