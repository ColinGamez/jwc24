"""Bounded HATJ v1792 CSData framing inspection, not a catalog implementation.

Version, CRC and reference-field checks follow selected original consumers.
Record meanings, authentication, delivery and UI acceptance remain unverified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct
import zlib

from .forecast import decode_lz10
from .lz11 import decode_lz11

MIN_CSDATA_BYTES = 0x136
MAX_CSDATA_BYTES = 0x142EE
REFERENCE_OFFSET = 0x35
REFERENCE_CAPACITY = 0x100
MAX_COMPRESSED_BYTES = MAX_CSDATA_BYTES * 2 + 8  # Local input policy.


class CSDataFormatError(ValueError):
    """Input is outside the independently supported CSData subset."""


@dataclass(frozen=True)
class CSDataInspection:
    byte_length: int
    format_byte: int
    secondary_format_byte: int
    reference: bytes = field(repr=False)
    compression: str

    def metadata(self) -> dict[str, object]:
        return {
            'byte_length': self.byte_length,
            'format_byte': self.format_byte,
            'secondary_format_byte': self.secondary_format_byte,
            'reference_byte_length': len(self.reference),
            'compression': self.compression,
            'crc32_checked_with_field_zeroed': True,
            'record_semantics_checked': False,
            'reference_url_or_host_authorized': False,
            'freshness_checked': False,
            'wc24_authenticity_checked': False,
            'native_download_or_ui_verified': False,
        }


def decompress_csdata(payload: bytes) -> tuple[bytes, str]:
    """Decode known LZ10/LZ11 framing after bounding the advertised output size.

    The original loader dispatches on a 0x10 high nibble. This implementation
    deliberately supports only the verified standard 0x10/0x11 type bytes.
    No compression input is emitted or timestamp changed.
    """
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_COMPRESSED_BYTES:
        raise CSDataFormatError('CSData input violates the local byte limit')
    if payload[0] & 0xF0 != 0x10:
        if len(payload) > MAX_CSDATA_BYTES:
            raise CSDataFormatError('Uncompressed CSData exceeds the native buffer budget')
        return payload, 'none'
    if payload[0] not in (0x10, 0x11) or len(payload) < 4:
        raise CSDataFormatError('Unsupported or truncated CSData compression header')
    expected = int.from_bytes(payload[1:4], 'little')
    encoded = payload
    if expected == 0:
        if len(payload) < 8:
            raise CSDataFormatError('Truncated extended CSData compression header')
        expected = int.from_bytes(payload[4:8], 'little')
        # The recovered native size/decompression helpers accept this extended
        # form for both types; normalize it for our existing bounded decoders.
        if expected <= MAX_CSDATA_BYTES:
            encoded = payload[:1] + expected.to_bytes(3, 'little') + payload[8:]
    if not MIN_CSDATA_BYTES <= expected <= MAX_CSDATA_BYTES:
        raise CSDataFormatError('CSData decompressed size is outside the supported native range')
    try:
        result = decode_lz10(encoded) if payload[0] == 0x10 else decode_lz11(encoded)
    except ValueError as error:
        raise CSDataFormatError('Malformed CSData compression stream') from error
    if len(result) != expected:
        raise CSDataFormatError('CSData decompressed size differs from its header')
    return result, 'lz10' if payload[0] == 0x10 else 'lz11'


def inspect_csdata(payload: bytes) -> CSDataInspection:
    """Inspect framing for the normal v6 consumer without interpreting records.

    Requiring declared size == available bytes, exactly supported format byte 6,
    zero opaque status byte and bounded termination is local safe-subset policy.
    Native early-success branches for other versions/status are not full startup
    success; the outer caller rejects them separately.
    """
    raw, compression = decompress_csdata(payload)
    if not MIN_CSDATA_BYTES <= len(raw) <= MAX_CSDATA_BYTES:
        raise CSDataFormatError('CSData length is outside the supported native range')
    declared, checksum = struct.unpack_from('>II', raw, 4)
    if declared != len(raw):
        raise CSDataFormatError('CSData declared size differs from available bytes')
    covered = raw[:8] + bytes(4) + raw[12:]
    if zlib.crc32(covered) != checksum:
        raise CSDataFormatError('CSData CRC-32 mismatch')
    if raw[:2] != bytes(2) or raw[2] != 6:
        raise CSDataFormatError('Unsupported CSData format prefix')
    if raw[0x28] != 0:
        raise CSDataFormatError('Opaque CSData status byte is outside the supported normal-data subset')
    field_bytes = raw[REFERENCE_OFFSET:REFERENCE_OFFSET + REFERENCE_CAPACITY]
    terminator = field_bytes.find(b'\0')
    if terminator < 0:
        raise CSDataFormatError('CSData reference field is not terminated within its native capacity')
    return CSDataInspection(len(raw), raw[2], raw[3], field_bytes[:terminator], compression)
