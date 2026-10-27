"""Explicit first-data request descriptors, without network or identity claims."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import struct
from urllib.parse import urlsplit

_TARGET = re.compile(r'/first/(0|[1-9][0-9]{0,9})(\.ces|\.bin)\Z')


@dataclass(frozen=True)
class FirstDataRequest:
    url: str = field(repr=False)
    cached_header: bytes = field(repr=False)
    family_word: int = field(default=0, init=False)
    method_word: int = field(default=0, init=False)

    def metadata(self):
        return {'tag': 'FD', 'cached_header_bytes': len(self.cached_header),
                'url_bytes': len(self.url.encode('ascii')),
                'native_family_word': self.family_word, 'native_method_word': self.method_word,
                'opaque_header_tail_supplied_by_caller': True,
                'request_body_serialization_verified': False,
                'transport_or_authentication_verified': False}


@dataclass(frozen=True)
class FirstDataTarget:
    word_4: int = field(repr=False)
    configuration_2c_predicate: bool


def parse_first_data_target(target: str) -> FirstDataTarget:
    """Decode only the canonical path shape produced by the native FD builder.

    This is a backend routing primitive, not a device identity or authorization
    check. It accepts no aliases, query strings or inferred file-type meaning.
    """
    match = _TARGET.fullmatch(target) if type(target) is str and len(target) <= 32 else None
    if match is None or int(match[1]) > 0xFFFFFFFF:
        raise ValueError('Unsupported canonical CMOC first-data target')
    return FirstDataTarget(int(match[1]), match[2] == '.bin')


def _uint(value, bits):
    if type(value) is not int or not 0 <= value < (1 << bits):
        raise ValueError('Expected explicit unsigned CMOC request field')
    return value


def _origin(value):
    if (type(value) is not str or not value.isascii() or len(value) > 100
            or any(ord(char) <= 32 or ord(char) >= 127 for char in value)):
        raise ValueError('Expected explicit bounded ASCII service origin')
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ('http', 'https') and parsed.hostname is not None
                 and all(char.isalnum() or char in '.:-_' for char in (parsed.hostname or ''))
                 and parsed.username is None and parsed.password is None
                 and parsed.path in ('', '/') and not parsed.query and not parsed.fragment
                 and (parsed.port is None or 1 <= parsed.port <= 65535)
                 and '?' not in value and '#' not in value and '\\' not in value)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Expected explicit service origin without path or credentials')
    return value.rstrip('/')


def build_first_data_request(*, origin: str, word_4: int, word_8: int,
                             byte_2: int, byte_3: int, opaque_header_tail: bytes,
                             configuration_2c_predicate: bool,
                             evidence_ref: str) -> FirstDataRequest:
    """Preserve the native FD prefix/path and explicitly supplied opaque state.

    The original constructor leaves cached-header bytes 12..31 untouched. They
    must be supplied, never inferred to be zero. The predicate is the observed
    configuration-table lookup reached through manager offset 0x2C; its product
    meaning is unverified. True selects .bin and false selects .ces.
    """
    word_4, word_8 = _uint(word_4, 32), _uint(word_8, 32)
    byte_2, byte_3 = _uint(byte_2, 8), _uint(byte_3, 8)
    if type(opaque_header_tail) is not bytes or len(opaque_header_tail) != 20:
        raise ValueError('Expected twenty explicit opaque cached-header bytes')
    if type(configuration_2c_predicate) is not bool:
        raise ValueError('Expected explicit configuration lookup predicate')
    if (type(evidence_ref) is not str or not evidence_ref.strip() or len(evidence_ref) > 512
            or any(ord(char) < 32 for char in evidence_ref)):
        raise ValueError('Expected explicit bounded request evidence reference')
    url = _origin(origin) + f'/first/{word_4}' + ('.bin' if configuration_2c_predicate else '.ces')
    if len(url.encode('ascii')) >= 128:
        raise ValueError('Request URL exceeds the original descriptor capacity')
    header = struct.pack('>HBBII', 0x4644, byte_2, byte_3, word_4, word_8) + opaque_header_tail
    return FirstDataRequest(url, header)
