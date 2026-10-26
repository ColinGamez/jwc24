"""Read-only inspection of HFNJ v256 plaintext dataset header integrity.

This does not decrypt WC24 envelopes, authenticate RSA signatures, or validate
health records. The CRC protects only twelve header bytes, not the payload.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct
import zlib

HEADER_SIZE = 16
MAX_DATASET_BYTES = 0x8000


class BodyCheckFormatError(ValueError):
    """The plaintext violates the supported length or header checksum policy."""


@dataclass(frozen=True)
class DatasetInspection:
    byte_length: int

    def metadata(self) -> dict[str, object]:
        """Return inspection scope and sizes without header or health data."""
        return {
            'byte_length': self.byte_length,
            'header_size': HEADER_SIZE,
            'header_integrity': 'CRC-32 matches',
            'checksum_covered_offset': 4,
            'checksum_covered_length': 12,
            'payload_integrity_checked': False,
            'record_semantics_checked': False,
            'rsa_authenticity_checked': False,
            'validation': 'plaintext header only; native acceptance not established',
        }


def inspect_dataset(data: bytes) -> DatasetInspection:
    """Check BE32@0 against CRC32(data[4:16]) within the native read limit.

    Native read/check anchors are 0x802BBBF8 and 0x802BBCB8. Requiring sixteen
    available bytes is our explicit truncation policy, not a proven native
    minimum-length check. Bytes following the header are deliberately opaque.
    """
    if len(data) > MAX_DATASET_BYTES:
        raise BodyCheckFormatError(f'Dataset exceeds byte limit ({MAX_DATASET_BYTES})')
    if len(data) < HEADER_SIZE:
        raise BodyCheckFormatError('Dataset is shorter than the 16-byte header')
    stored_crc = struct.unpack_from('>I', data)[0]
    if stored_crc != zlib.crc32(data[4:HEADER_SIZE]):
        raise BodyCheckFormatError('Dataset header CRC-32 mismatch')
    return DatasetInspection(len(data))
