"""CMOC FD first-data record codec; no service/authentication success implied.

Fields retain byte-offset names because their complete product meanings remain
unverified. Producing bytes requires explicit values and a caller evidence ref.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from .cmoc import CMOCFormatError, ResponseHeader, inspect_response

FIRST_DATA_TAG = 0x4644  # FD
FIRST_DATA_SIZE = 12
MAX_NATIVE_CAST_SIZE = 0x60


@dataclass(frozen=True)
class FirstDataRecord:
    byte_length: int
    word_4: int = field(repr=False)
    byte_8: int = field(repr=False)
    byte_9: int = field(repr=False)
    u16_a: int = field(repr=False)
    opaque_extension: bytes = field(repr=False)

    def metadata(self):
        return {'record_size': self.byte_length,
                'opaque_extension_bytes': len(self.opaque_extension),
                'selected_field_layout_checked': True,
                'complete_field_meanings_checked': False,
                'authenticated_or_current_service_data': False,
                'native_startup_or_menu_verified': False}


@dataclass(frozen=True)
class FirstDataResponse:
    record: FirstDataRecord = field(repr=False)
    request_correlation_checked: bool
    other_records: int

    def metadata(self):
        return {**self.record.metadata(),
                'request_correlation_checked': self.request_correlation_checked,
                'other_records_not_decoded': self.other_records,
                'header_byte_2_and_3_checks_executed': False,
                'http_status_or_x_result_checked': False,
                'signatures_or_encryption_checked': False}


def decode_first_data_record(data: bytes) -> FirstDataRecord:
    """Read normal FD data while rejecting the native cast's short-read cases.

    The original producer emits 12 bytes. Its type predicate permits sizes up
    to 96 and even short records/tag zero; the independent subset requires an
    exact FD tag, at least 12 available/declared bytes and matching length.
    Extra bytes are retained as opaque, not interpreted as more known fields.
    """
    if not isinstance(data, bytes) or not FIRST_DATA_SIZE <= len(data) <= MAX_NATIVE_CAST_SIZE:
        raise CMOCFormatError('FD record length is outside the reviewed safe subset')
    tag, size, opaque, first, second, last = struct.unpack_from('>HHIBBH', data)
    if tag != FIRST_DATA_TAG or size != len(data):
        raise CMOCFormatError('FD record tag or declared size does not match the supported subset')
    return FirstDataRecord(len(data), opaque, first, second, last, data[FIRST_DATA_SIZE:])


def encode_first_data_record(*, word_4: int, byte_8: int, byte_9: int,
                             u16_a: int, evidence_ref: str) -> bytes:
    """Encode only the observed 12-byte record from explicit caller evidence.

    A nonempty evidence reference is a provenance requirement, not verification
    of the supplied source or permission to invent fields. No response header,
    authentication envelope or HTTP-success response is generated here.
    """
    if not isinstance(evidence_ref, str) or not evidence_ref.strip() or len(evidence_ref) > 512 or '\0' in evidence_ref:
        raise ValueError('An explicit bounded FD field-evidence reference is required')
    for value, maximum in ((word_4, 0xFFFFFFFF), (byte_8, 0xFF), (byte_9, 0xFF), (u16_a, 0xFFFF)):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError('FD field is outside its observed unsigned width')
    return struct.pack('>HHIBBH', FIRST_DATA_TAG, FIRST_DATA_SIZE, word_4, byte_8, byte_9, u16_a)


def inspect_first_data_response(data: bytes, *, expected_request: ResponseHeader | None = None) -> FirstDataResponse:
    """Locate one FD record within the existing bounded response framing.

    Optional correlation covers only tag/word4/word8. Duplicate FD records are
    rejected as ambiguous local policy; other framed records stay undecoded.
    This does not perform the native header-byte, service or crypto checks.
    """
    response = inspect_response(data)
    if response.header.tag != FIRST_DATA_TAG:
        raise CMOCFormatError('Response does not have the FD request tag')
    if expected_request is not None and not response.header.matches_request(expected_request):
        raise CMOCFormatError('FD response correlation fields do not match the supplied request')
    records = [record for record in response.records if record.prefix_tag == FIRST_DATA_TAG]
    if len(records) != 1:
        raise CMOCFormatError('FD response must contain one unambiguous supported first-data record')
    record = records[0]
    result = decode_first_data_record(data[record.offset:record.offset + record.size])
    return FirstDataResponse(result, expected_request is not None, len(response.records) - 1)
