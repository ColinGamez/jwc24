"""Explicit CMOC HMAC-SHA1 processing and observed string-comparison result.

This offline inspection API never establishes resource ownership, trust or
service authentication. Native string comparison is distinct from binary MAC
comparison, including equal-NUL early termination and zero-length acceptance.
"""
from dataclasses import dataclass, field
import hmac


def _chunks(chunks):
    if (type(chunks) is not tuple or len(chunks) > 64
            or any(type(c) is not bytes for c in chunks)
            or sum(map(len, chunks)) > 1024 * 1024):
        raise ValueError('Expected bounded immutable CMOC hash chunks')
    return chunks


def hmac_sha1_digest(key, chunks):
    """Standard algorithm only; no native wrapper or identity is implied."""
    if type(key) is not bytes or len(key) > 4096:
        raise ValueError('Expected bounded explicit CMOC hash key bytes')
    _chunks(chunks)
    context = hmac.new(key, digestmod='sha1')
    for chunk in chunks:
        context.update(chunk)
    return context.digest()


@dataclass(frozen=True)
class HashInspection:
    enabled: bool
    resolved_key_size: int
    update_returns: tuple[int, ...]
    native_match: bool
    full_span_binary_match: bool
    native_compared_bytes: int
    stopped_on_equal_nul: bool
    digest: bytes | None = field(repr=False)

    def metadata(self):
        return dict(algorithm='HMAC-SHA1', enabled=self.enabled,
                    resolved_key_size=self.resolved_key_size,
                    update_returns=list(self.update_returns),
                    native_match=self.native_match,
                    full_span_binary_match=self.full_span_binary_match,
                    native_compared_bytes=self.native_compared_bytes,
                    stopped_on_equal_nul=self.stopped_on_equal_nul,
                    full_twenty_byte_comparison=(self.resolved_key_size == 20
                                                and self.native_compared_bytes == 20),
                    native_check_establishes_authentication=False)


def inspect_application_hash(*, key, key_size, chunks, expected):
    """Mirror the selected application's enabled/setup/update/check behavior.

    Nonzero key_size selects that many binary key bytes; zero selects a C-string
    prefix. The observed wrapper also uses this resolved key size as its digest
    string-comparison limit. The local safe subset rejects limits above the
    actual twenty-byte digest instead of inspecting unrelated stack bytes.
    """
    _chunks(chunks)
    if type(key_size) is not int or not 0 <= key_size <= 4096:
        raise ValueError('Expected explicit bounded CMOC key size')
    if type(expected) is not bytes:
        raise ValueError('Expected explicit CMOC digest comparison bytes')
    if key is None:
        if key_size != 0 or expected:
            raise ValueError('Disabled CMOC hash requires an empty local comparison span')
        return HashInspection(False, 0, tuple(0 for _ in chunks), False, False, 0, False, None)
    if type(key) is not bytes or len(key) > 4096 or key_size > len(key):
        raise ValueError('Expected bounded explicit CMOC hash key bytes')
    if key_size == 0 and b'\0' not in key:
        raise ValueError('CMOC strlen mode requires an explicit supplied NUL terminator')
    selected = key[:key_size] if key_size else key.split(b'\0', 1)[0]
    size = len(selected)
    if size > 20:
        raise ValueError('CMOC application comparison exceeds its actual digest backing')
    if len(expected) != size:
        raise ValueError('CMOC digest comparison span must equal the resolved key size')
    digest = hmac_sha1_digest(selected, chunks)
    native_match = True
    count = 0
    stopped = False
    for actual, supplied in zip(digest[:size], expected):
        count += 1
        if actual != supplied:
            native_match = False
            break
        if actual == 0:
            stopped = True
            break
    return HashInspection(True, size, tuple(map(len, chunks)), native_match,
                          hmac.compare_digest(digest[:size], expected), count, stopped, digest)
