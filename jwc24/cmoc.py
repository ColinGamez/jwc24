"""Read-only framing inspection for CMOC Japanese v512 binary responses.

This validates framing, not record meanings, cryptographic authenticity, or
whether the native client would accept a response. Both native size encodings
are understood; extended prefixes require a conservative 16-byte minimum.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

HEADER_SIZE = 32
RECORD_PREFIX_SIZE = 8
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_RECORDS = 4096


class CMOCFormatError(ValueError):
    """The response does not fit the supported native framing contract."""


class CMOCUnsupportedFormat(CMOCFormatError):
    """The response uses a format whose full contract is not yet established."""


@dataclass(frozen=True)
class ResponseHeader:
    tag: int
    byte_2: int
    byte_3: int
    word_4: int = field(repr=False)
    word_8: int = field(repr=False)

    def matches_request(self, expected: ResponseHeader) -> bool:
        """Compare only the native tag/word-4/word-8 correlation fields.

        This reproduces the predicate at 0x8006A57C. The independent byte-2
        and byte-3 checks, cryptographic verification and FD schema are outside
        this predicate; matching is not evidence of an authenticated response.
        """
        if not isinstance(expected, ResponseHeader):
            raise TypeError('Expected a parsed response header')
        return ((self.tag, self.word_4, self.word_8)
                == (expected.tag, expected.word_4, expected.word_8))


@dataclass(frozen=True)
class Record:
    offset: int
    size: int
    prefix_tag: int
    extended_size: bool = False


@dataclass(frozen=True)
class ResponseInspection:
    header: ResponseHeader
    byte_length: int
    records: tuple[Record, ...]

    def metadata(self) -> dict[str, object]:
        """Expose framing only, excluding opaque identifiers and payload bytes."""
        return {
            'byte_length': self.byte_length,
            'header_size': HEADER_SIZE,
            'header_tag': f'0x{self.header.tag:04x}',
            'record_count': len(self.records),
            'records': [{'offset': record.offset, 'size': record.size,
                         'prefix_tag': f'0x{record.prefix_tag:04x}',
                         'extended_size': record.extended_size} for record in self.records],
            'validation': 'framing only; authenticity and record semantics not checked',
        }


def inspect_response(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES,
                     max_records: int = DEFAULT_MAX_RECORDS) -> ResponseInspection:
    """Inspect the 32-byte header and bounded ordinary records, without decoding Miis.

    Native anchors: header 0x80069634, record bounds 0x8006966c,
    size accessor 0x80068344, cursor advance 0x800697c0. A declared ordinary
    record size includes its prefix. A zero 16-bit size selects a 32-bit size
    at offset 12. The inspector requires 16 bytes to read that field and a size
    at least 16; the native iterator's eight-byte minimum permits an unchecked
    read on malformed extended records. No extended payload schema is implied.
    """
    if (type(max_bytes) is not int or type(max_records) is not int
            or max_bytes < HEADER_SIZE or max_records < 0):
        raise ValueError('Invalid inspection limits')
    if not isinstance(data, bytes):
        raise TypeError('Expected immutable response bytes')
    if len(data) > max_bytes:
        raise CMOCFormatError(f'Response exceeds byte limit ({max_bytes})')
    if len(data) < HEADER_SIZE:
        raise CMOCFormatError('Response is shorter than the 32-byte header')
    header = ResponseHeader(*struct.unpack_from('>HBBII', data))
    records = []
    cursor = HEADER_SIZE
    while cursor < len(data):
        if len(records) >= max_records:
            raise CMOCFormatError(f'Record count exceeds limit ({max_records}) at offset {cursor}')
        if len(data) - cursor < RECORD_PREFIX_SIZE:
            raise CMOCFormatError(f'Truncated record prefix at offset {cursor}')
        tag, size = struct.unpack_from('>HH', data, cursor)
        extended = size == 0
        if extended:
            if len(data) - cursor < 16:
                raise CMOCUnsupportedFormat(f'Incomplete extended record prefix at offset {cursor}')
            size = struct.unpack_from('>I', data, cursor + 12)[0]
            if size < 16:
                raise CMOCFormatError(f'Extended record size is below sixteen bytes at offset {cursor}')
        if size < RECORD_PREFIX_SIZE:
            raise CMOCFormatError(f'Record size {size} is below eight bytes at offset {cursor}')
        if size > len(data) - cursor:
            raise CMOCFormatError(f'Record size {size} exceeds remaining bytes at offset {cursor}')
        records.append(Record(cursor, size, tag, extended))
        cursor += size
    return ResponseInspection(header, len(data), tuple(records))
