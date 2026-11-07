"""Explicit offline projection of the CMOC cached-request setup boundary.

No keys, provider identities, network requests or native state are created here.
Configuration sizes are caller-resolved values, not a cryptographic validation.
"""
from dataclasses import dataclass, field


def _uint(value, limit, name):
    if type(value) is not int or not 0 <= value <= limit:
        raise ValueError('Invalid CMOC setup ' + name)
    return value


def _bytes(value, bound, name, nullable=False):
    if nullable and value is None:
        return None
    if type(value) is not bytes or len(value) > bound:
        raise ValueError('Invalid CMOC setup ' + name)
    return value


@dataclass(frozen=True)
class ResourceSetup:
    """Explicit resolved resource metadata, independent of secret contents.

    hash_span_size models the effective +0xC8 word after initialization; zero
    is preserved. Prefix pointer absence differs from a present empty span.
    """
    hash_span_size: int
    wire_prefix: bytes | None = field(repr=False)
    decompression_word: int

    def __post_init__(self):
        _uint(self.hash_span_size, 64, 'resolved hash span')
        _bytes(self.wire_prefix, 4096, 'wire prefix', nullable=True)
        _uint(self.decompression_word, 0xFFFFFFFF, 'decompression word')


@dataclass(frozen=True)
class RequestSetup:
    configured: bool
    native_method_word: int
    secure_byte_predicate: bool
    receive_capacity: int
    retained_wire_prefix: bytes = field(repr=False)
    retained_cached_prefix: bytes = field(repr=False)
    requested_headers: tuple = field(repr=False)
    decompression_requested: bool
    evidence_ref: str = field(repr=False)

    def metadata(self):
        return dict(configured=self.configured, native_method_word=self.native_method_word,
                    secure_byte_predicate=self.secure_byte_predicate,
                    receive_capacity=self.receive_capacity,
                    retained_wire_prefix_size=len(self.retained_wire_prefix),
                    retained_cached_prefix_size=len(self.retained_cached_prefix),
                    requested_header_names=[name for name, _ in self.requested_headers],
                    decompression_requested=self.decompression_requested,
                    cryptographic_initialization_verified=False,
                    socket_serialization_verified=False)


def project_request_setup(*, url, native_method_word, configuration,
                          cached_prefix, timestamp_present, date_header_value,
                          appver_header_value, evidence_ref):
    """Project selected setup decisions; no SDK header acceptance is implied.

    Header values are already-produced bytes. A null X-APPVER value is retained
    as an attempted SDK call, not converted into a serialized empty header.
    """
    if (type(url) is not str or not url.isascii() or not 8 <= len(url) < 128
            or any(ord(c) < 33 or ord(c) > 126 for c in url)
            or not url.startswith(('http://', 'https://'))):
        raise ValueError('Invalid CMOC setup URL')
    _uint(native_method_word, 2, 'native method word')
    if configuration is not None and type(configuration) is not ResourceSetup:
        raise ValueError('Invalid CMOC setup resource metadata')
    _bytes(cached_prefix, 4096, 'cached prefix', nullable=True)
    if type(timestamp_present) is not bool:
        raise ValueError('Invalid CMOC setup timestamp predicate')
    for name, value, bound in (('date value', date_header_value, 75),
                               ('appver value', appver_header_value, 63)):
        _bytes(value, bound, name, nullable=True)
        if value is not None and any(c < 32 or c > 126 for c in value):
            raise ValueError('Invalid CMOC setup header value')
    if timestamp_present and date_header_value is None:
        raise ValueError('CMOC setup date producer result is required')
    if (type(evidence_ref) is not str or not 1 <= len(evidence_ref) <= 256
            or any(ord(c) < 32 for c in evidence_ref)):
        raise ValueError('Invalid CMOC setup evidence reference')
    secure = url[4] == 's'  # Exact observed caller predicate, not TLS proof.
    wire = (configuration.wire_prefix or b'')[:64] if configuration else b''
    cached = (cached_prefix or b'')[:64]
    headers = []
    if timestamp_present and not secure:
        headers.append(('If-Modified-Since', date_header_value))
    headers.append(('X-APPVER', appver_header_value))
    return RequestSetup(configuration is not None, native_method_word, secure,
                        configuration.hash_span_size + len(wire) + 1024
                        if configuration else 0x30000,
                        wire, cached, tuple(headers),
                        configuration is not None and configuration.decompression_word != 0,
                        evidence_ref)
