"""Bounded partial HATJ ListData records for offline catalog inspection.

This decodes proven software-title and linked-row fields, not a complete service
catalog, price/availability feed, media codec or native browsing implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from .forecast import decode_lz10
from .lz11 import decode_lz11

MIN_LIST_BYTES = 0x5E8
MAX_LIST_BYTES = 0x1FC7CC
MAX_INPUT_BYTES = MAX_LIST_BYTES * 2 + 8  # Explicit local compressed-input cap.
DESCRIPTOR_OFFSET = 0x25
DESCRIPTOR_COUNT = 16
KNOWN_STRIDES = {0: 0x22, 1: 0x6C, 3: 0xEC, 5: 0x116, 15: 0xCE}
MAX_TITLE_UNITS = 499  # Observed UI destination is 500 units including NUL.


class ListDataFormatError(ValueError):
    """Input violates the implemented framing/record subset or local policy."""


@dataclass(frozen=True)
class ListTable:
    index: int
    count: int
    offset: int
    stride: int | None


@dataclass(frozen=True)
class SoftwareListRow:
    index: int
    file_offset: int = field(repr=False)
    byte_field_08: int
    title_reference: int = field(repr=False)
    title_prefix: bytes = field(repr=False)
    title: str | None = field(repr=False)


@dataclass(frozen=True)
class LinkedListRow:
    index: int
    software_index: int | None
    u16_field_04: int = field(repr=False)
    u32_field_06: int = field(repr=False)
    byte_field_0a: int
    byte_field_0b: int
    byte_field_1a: int
    flag_field_1b: bool
    flag_field_1c: bool


@dataclass(frozen=True)
class NintendoListInspection:
    byte_length: int
    compression: str
    tables: tuple[ListTable, ...]
    software_rows: tuple[SoftwareListRow, ...] = field(repr=False)
    linked_rows: tuple[LinkedListRow, ...] = field(repr=False)

    def metadata(self):
        return {
            'byte_length': self.byte_length,
            'compression': self.compression,
            'software_rows': len(self.software_rows),
            'software_titles_present': sum(row.title is not None for row in self.software_rows),
            'linked_rows': len(self.linked_rows),
            'linked_rows_without_software': sum(row.software_index is None for row in self.linked_rows),
            'tables': [{'index': table.index, 'count': table.count,
                        'stride_verified': table.stride is not None}
                       for table in self.tables],
            'undecoded_nonempty_tables': [table.index for table in self.tables
                                         if table.count and table.index not in (3, 5)],
            'decoded_record_fields': 'selected software-title and linked-row fields only',
            'known_table_byte_spans_checked': True,
            'unknown_table_record_bounds_checked': False,
            'crc_or_signature_checked': False,
            'freshness_checked': False,
            'complete_catalog_schema_checked': False,
            'media_playability_checked': False,
            'native_download_or_ui_verified': False,
        }


def decode_listdata(payload: bytes) -> tuple[bytes, str]:
    """Bound known LZ10/LZ11 output before decoding; accept uncompressed input."""
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_INPUT_BYTES:
        raise ListDataFormatError('Nintendo list input violates local byte bounds')
    if payload[0] & 0xF0 != 0x10:
        if len(payload) > MAX_LIST_BYTES:
            raise ListDataFormatError('Uncompressed Nintendo list exceeds its reviewed native range')
        return payload, 'none'
    if len(payload) < 4 or payload[0] not in (0x10, 0x11):
        raise ListDataFormatError('Unsupported or truncated Nintendo list compression header')
    expected = int.from_bytes(payload[1:4], 'little')
    encoded = payload
    if expected == 0:
        if len(payload) < 8:
            raise ListDataFormatError('Truncated extended Nintendo list compression header')
        expected = int.from_bytes(payload[4:8], 'little')
        if expected <= MAX_LIST_BYTES:
            encoded = payload[:1] + expected.to_bytes(3, 'little') + payload[8:]
    if not MIN_LIST_BYTES <= expected <= MAX_LIST_BYTES:
        raise ListDataFormatError('Nintendo list decompressed length exceeds the supported range')
    try:
        raw = decode_lz10(encoded) if payload[0] == 0x10 else decode_lz11(encoded)
    except ValueError:
        raise ListDataFormatError('Nintendo list compression stream is malformed') from None
    return raw, 'lz10' if payload[0] == 0x10 else 'lz11'


def inspect_listdata(payload: bytes) -> NintendoListInspection:
    """Decode proven record fields without filling missing metadata or tables.

    Exact declared length, bounded count*stride, non-overlap, strict UTF-16 and
    exact software-row references are local safeguards beyond the narrow native
    validator. No CRC meaning is assigned to the word at header offset 8.
    """
    raw, compression = decode_listdata(payload)
    if not MIN_LIST_BYTES <= len(raw) <= MAX_LIST_BYTES:
        raise ListDataFormatError('Nintendo list length exceeds its reviewed native range')
    if raw[:2] != bytes(2) or raw[2] != 6:
        raise ListDataFormatError('Unsupported Nintendo list format prefix')
    if struct.unpack_from('>I', raw, 4)[0] != len(raw):
        raise ListDataFormatError('Nintendo list declared size differs from available bytes')
    tables, spans = [], []
    for index in range(DESCRIPTOR_COUNT):
        count, offset = struct.unpack_from('>II', raw, DESCRIPTOR_OFFSET + index * 8)
        if count > 65536 or (offset and not MIN_LIST_BYTES <= offset <= len(raw)):
            raise ListDataFormatError('Nintendo list descriptor exceeds local bounds')
        if count and not MIN_LIST_BYTES <= offset < len(raw):
            raise ListDataFormatError('Nintendo list nonempty descriptor has no bounded data')
        stride = KNOWN_STRIDES.get(index)
        if count and stride is not None:
            end = offset + count * stride
            if end > len(raw) or any(offset < hi and end > lo for lo, hi in spans):
                raise ListDataFormatError('Nintendo list known record tables exceed or overlap their data region')
            spans.append((offset, end))
        tables.append(ListTable(index, count, offset, stride))
    for table in tables:
        if table.count and table.stride is None and any(lo <= table.offset < hi for lo, hi in spans):
            raise ListDataFormatError('Nintendo list undecoded table aliases a known record table')

    def title(reference):
        if reference == 0:
            return b'', None
        if reference < MIN_LIST_BYTES or reference + 6 > len(raw) or (reference + 4) & 1:
            raise ListDataFormatError('Nintendo list title reference is outside its bounded region')
        start = reference + 4
        for units in range(MAX_TITLE_UNITS + 1):
            end = start + units * 2
            if end + 2 > len(raw):
                break
            if raw[end:end + 2] == bytes(2):
                if any(reference < hi and end + 2 > lo for lo, hi in spans):
                    raise ListDataFormatError('Nintendo list title aliases record-table storage')
                try:
                    return raw[reference:start], raw[start:end].decode('utf-16-be')
                except UnicodeDecodeError:
                    raise ListDataFormatError('Nintendo list title contains malformed UTF-16BE') from None
        raise ListDataFormatError('Nintendo list title exceeds bounded termination policy')

    software = tables[3]
    software_rows = []
    for index in range(software.count):
        offset = software.offset + index * 0xEC
        reference = struct.unpack_from('>I', raw, offset + 0x0C)[0]
        prefix, text = title(reference)
        software_rows.append(SoftwareListRow(index, offset, raw[offset + 8], reference, prefix, text))
    linked = tables[5]
    linked_rows = []
    for index in range(linked.count):
        offset = linked.offset + index * 0x116
        reference = struct.unpack_from('>I', raw, offset)[0]
        software_index = None
        if reference:
            relative = reference - software.offset
            if relative < 0 or relative % 0xEC or relative // 0xEC >= software.count:
                raise ListDataFormatError('Nintendo list linked row references no exact software record')
            software_index = relative // 0xEC
        if raw[offset + 0x0A] > 10 or raw[offset + 0x1B] > 1 or raw[offset + 0x1C] > 1:
            raise ListDataFormatError('Nintendo list linked-row enum or boolean field is outside native bounds')
        linked_rows.append(LinkedListRow(index, software_index,
                                         struct.unpack_from('>H', raw, offset + 4)[0],
                                         struct.unpack_from('>I', raw, offset + 6)[0],
                                         raw[offset + 0x0A], raw[offset + 0x0B], raw[offset + 0x1A],
                                         bool(raw[offset + 0x1B]), bool(raw[offset + 0x1C])))
    return NintendoListInspection(len(raw), compression, tuple(tables), tuple(software_rows), tuple(linked_rows))
