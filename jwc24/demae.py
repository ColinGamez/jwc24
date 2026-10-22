"""Inspect Demae's processed postal records, not its encrypted wire format."""
from dataclasses import dataclass
import struct

MAX_INSPECTION_BYTES = 1024 * 1024
MAX_NATIVE_DOWNLOAD_BYTES = 0x40000


class PostalFormatError(ValueError):
    pass


def decode_postal_download(data: bytes, key: bytes, iv: bytes) -> bytes:
    """Decode stock application-level task data, after WC24 delivery.

    Keys are supplied by the caller; none are bundled. This checks CBC/zpcd/LZ
    structure, not signatures or native acceptance. Header offsets outside the
    buffer are rejected; no assumption about PKCS#7 padding is made.
    """
    if len(key) != 32 or len(iv) != 16:
        raise ValueError('Postal decoding requires a 32-byte key and 16-byte IV')
    if not 16 <= len(data) <= MAX_NATIVE_DOWNLOAD_BYTES or len(data) % 16:
        raise PostalFormatError('Invalid encrypted postal download length')
    from Crypto.Cipher import AES
    plain = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(data)
    if plain[:4] != b'zpcd':
        raise PostalFormatError('Postal download has no zpcd header')
    offset = plain[4]
    if not 5 <= offset <= len(plain) - 8:
        raise PostalFormatError('Invalid zpcd payload offset')
    compressed = plain[offset:]
    kind = compressed[0]
    if kind not in (0x10, 0x11):
        raise PostalFormatError('Postal payload is not Nintendo LZ10/LZ11')
    size = int.from_bytes(compressed[1:4], 'little')
    if kind == 0x11 and size == 0:
        size = int.from_bytes(compressed[4:8], 'little')
    if size > MAX_NATIVE_DOWNLOAD_BYTES:
        raise PostalFormatError('Decoded postal size exceeds the native limit')
    try:
        if kind == 0x10:
            from .forecast import decode_lz10
            return decode_lz10(compressed)
        from .lz11 import decode_lz11
        return decode_lz11(compressed)
    except ValueError as error:
        raise PostalFormatError(f'Invalid postal compression: {error}') from error


@dataclass(frozen=True)
class PostalRecord:
    postal_code: int
    strings: tuple[str, str, str]


@dataclass(frozen=True)
class PostalLookup:
    kind: str
    record: PostalRecord | None


def lookup_processed_postal(data: bytes, postal_code: int) -> PostalLookup:
    """Inspect exact/rounded lookup semantics offline, without delivery claims.

    All framing is validated before lookup, unlike the native early-return
    path. Selected strings exceeding native UTF-16 output capacities are
    rejected rather than silently truncated. Source order is retained.
    """
    if type(postal_code) is not int or not 0 <= postal_code <= 9_999_999:
        raise PostalFormatError('Postal query must be a seven-digit-range integer')
    records = inspect_postal_records(data, max_bytes=MAX_NATIVE_DOWNLOAD_BYTES)
    alternative_code = postal_code // 100 * 100
    result = PostalLookup('not_found', None)
    for record in records:
        if record.postal_code == postal_code:
            result = PostalLookup('exact', record)
            break
        if record.postal_code == alternative_code:
            result = PostalLookup('alternative', record)
    if result.record is not None:
        for value, limit in zip(result.record.strings, (31, 31, 63)):
            if len(value.encode('utf-16-be')) > limit*2:
                raise PostalFormatError('Selected postal string exceeds native output capacity')
    return result


def inspect_postal_records(data: bytes, *, max_bytes: int = MAX_INSPECTION_BYTES,
                           max_records: int = 16384) -> tuple[PostalRecord, ...]:
    """Parse U32BE plus three terminated UTF-16BE strings with bounded reads.

    Native parser: HCCJ v2, 0x8002EBCC. Limits and rejection of malformed UTF-16
    are conservative inspection policies. This does not unwrap WC24/zpcd/LZ
    data, validate authenticity, or assert native acceptance.
    """
    if max_bytes < 0 or max_records < 0:
        raise ValueError("Invalid inspection limits")
    if len(data) > max_bytes:
        raise PostalFormatError("Processed postal data exceeds inspection limit")
    cursor = 0
    records = []
    while cursor < len(data):
        if len(records) >= max_records:
            raise PostalFormatError("Postal record count exceeds inspection limit")
        if len(data) - cursor < 4:
            raise PostalFormatError(f"Truncated postal code at offset {cursor}")
        code = struct.unpack_from('>I', data, cursor)[0]
        cursor += 4
        strings = []
        for _ in range(3):
            start = cursor
            while True:
                if len(data) - cursor < 2:
                    raise PostalFormatError(f"Unterminated UTF-16 string at offset {start}")
                if data[cursor:cursor + 2] == b'\0\0':
                    try:
                        strings.append(data[start:cursor].decode('utf-16-be'))
                    except UnicodeDecodeError as error:
                        raise PostalFormatError(f"Malformed UTF-16 at offset {start}") from error
                    cursor += 2
                    break
                cursor += 2
        records.append(PostalRecord(code, tuple(strings)))
    return tuple(records)
