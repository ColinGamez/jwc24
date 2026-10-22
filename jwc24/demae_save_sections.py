"""Bounded metadata inspection of an already-decrypted HCCJ save buffer.

No cipher, personal-field decoding, checksum or authenticity validation.
Bounds are conservative inspection policy, not a claim of native validation.
"""
from dataclasses import dataclass
import struct

BUFFER_BYTES = 0x4000
SECTION_START = 0x80
SECTION_HEADER_BYTES = 12


@dataclass(frozen=True)
class SaveSection:
    tag: bytes
    offset: int
    byte_length: int
    stop_byte: int

    @property
    def payload_offset(self):
        return self.offset + SECTION_HEADER_BYTES

    @property
    def payload_length(self):
        return self.byte_length - SECTION_HEADER_BYTES


def inspect_sections(data: bytes) -> tuple[int, tuple[SaveSection, ...]]:
    if not isinstance(data, bytes) or len(data) != BUFFER_BYTES:
        raise ValueError('Expected a complete decrypted address-save buffer')
    if data[:4] != b'PDFF':
        raise ValueError('Missing post-transformation address-save marker')
    offset = SECTION_START
    sections = []
    while offset < len(data):
        if offset + SECTION_HEADER_BYTES > len(data):
            raise ValueError('Truncated address-save section header')
        tag, length, stop = struct.unpack_from('>4sIB', data, offset)
        if length < SECTION_HEADER_BYTES:
            raise ValueError('Address-save section does not advance safely')
        if length > len(data) - offset:
            raise ValueError('Address-save section exceeds buffer bounds')
        sections.append(SaveSection(tag, offset, length, stop))
        if stop:
            break
        offset += length
    return data[4], tuple(sections)
