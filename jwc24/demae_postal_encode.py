"""Encode recovered processed postal records; no WC24 envelope or keys."""
import struct

from .demae import MAX_NATIVE_DOWNLOAD_BYTES, PostalFormatError, PostalRecord


def postal_bucket(postal_code: int) -> int:
    """Stock HCCJ default: ten leading-three-digit buckets per file."""
    if type(postal_code) is not int or not 0 <= postal_code <= 9_999_999:
        raise PostalFormatError('Postal code must be a seven-digit-range integer')
    return (postal_code // 100_000) * 10


def encode_processed_records(records, *, bucket: int | None = None) -> bytes:
    """Build safe U32BE/UTF16BE records for offline inspection.

    Duplicate codes are rejected because native lookup chooses the first exact
    match. Address-field semantics and source normalization remain the caller's
    responsibility. This output is NOT a stock channel's HTTP response body.
    """
    if bucket is not None and (type(bucket) is not int or not 0 <= bucket <= 990
                               or bucket % 10):
        raise PostalFormatError('Invalid native postal bucket')
    result = bytearray()
    seen = set()
    for record in records:
        if not isinstance(record, PostalRecord):
            raise PostalFormatError('Expected PostalRecord')
        actual_bucket = postal_bucket(record.postal_code)
        if bucket is not None and actual_bucket != bucket:
            raise PostalFormatError('Postal record is outside the selected bucket')
        if record.postal_code in seen:
            raise PostalFormatError('Duplicate postal code requires explicit source resolution')
        seen.add(record.postal_code)
        if not isinstance(record.strings, tuple) or len(record.strings) != 3:
            raise PostalFormatError('Postal record requires three strings')
        encoded = []
        for value, units in zip(record.strings, (31, 31, 63)):
            if not isinstance(value, str) or '\0' in value:
                raise PostalFormatError('Invalid postal string')
            try:
                data = value.encode('utf-16-be')
            except UnicodeEncodeError as error:
                raise PostalFormatError('Malformed postal Unicode') from error
            if len(data) > units * 2:
                raise PostalFormatError('Postal string exceeds its native output capacity')
            encoded.append(data + b'\0\0')
        chunk = struct.pack('>I', record.postal_code) + b''.join(encoded)
        if len(result) + len(chunk) > MAX_NATIVE_DOWNLOAD_BYTES:
            raise PostalFormatError('Processed postal bucket exceeds the native size limit')
        result.extend(chunk)
    return bytes(result)
