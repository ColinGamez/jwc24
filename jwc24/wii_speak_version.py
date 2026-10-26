"""HCFJ v512 version-file inspection and explicitly experimental capture replay.

This does not build a version response or authenticate/decrypt an IOS envelope.
The channel's downloaded VF data and the opaque HTTP capture are separate inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
import struct

VERSION_DATA_BYTES = 8
CAPTURE_BYTES = 320 + VERSION_DATA_BYTES
VERSION_ROUTE = '/hcf/version.enc'


class WiiSpeakVersionError(ValueError):
    pass


@dataclass(frozen=True)
class VersionDataInspection:
    version_word: int
    size_limit_kib_word: int

    def metadata(self):
        return {'decoded_vf_bytes': VERSION_DATA_BYTES,
                'version_word': self.version_word,
                'newer_than_native_client_2': self.version_word > 2,
                'size_limit_kib_word': self.size_limit_kib_word,
                'size_limit_bytes_native_u32': (self.size_limit_kib_word << 10) & 0xFFFFFFFF,
                'size_limit_overflows_u32': self.size_limit_kib_word > 0x3FFFFF,
                'native_payload_schema_validated': False,
                'service_release_metadata_verified': False,
                'native_ios_crypto_delivery_or_voice_verified': False}


def inspect_version_data(data: bytes) -> VersionDataInspection:
    """Inspect exactly two BE words; the native reader accepts shorter files too.

Exactly eight bytes is a local completeness policy, not a recovered native
validator. No default response is provided; constructor values are not a feed.
    """
    if type(data) is not bytes or len(data) != VERSION_DATA_BYTES:
        raise WiiSpeakVersionError('Expected exactly 8 explicit decoded VF bytes')
    return VersionDataInspection(*struct.unpack('>II', data))


def inspect_version_capture(data: bytes) -> dict:
    """Check a narrow, Dolphin-corroborated encrypted transport shape only.

No genuine service sample or retail IOS crypto path has been verified. This
does not establish that the encrypted body contains eight valid version bytes.
    """
    if type(data) is not bytes or len(data) != CAPTURE_BYTES:
        raise WiiSpeakVersionError('Expected a bounded 328-byte explicit capture')
    if data[:4] != b'Wc24' or data[4:8] != b'\0\0\0\1' or data[12] != 1:
        raise WiiSpeakVersionError('Capture is outside the reviewed WC24 envelope shape')
    return {'capture_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'header_bytes': 320, 'opaque_body_bytes': 8,
            'envelope_layout_source': 'Dolphin implementation, independently labeled',
            'local_header_policy_checked': True, 'native_header_policy_verified': False,
            'decrypted_body_checked': False, 'signature_checked': False,
            'capture_authenticity_verified': False,
            'native_ios_crypto_delivery_or_voice_verified': False}


def _reference(value):
    if (type(value) is not str or not value.strip() or len(value) > 2048
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise WiiSpeakVersionError('Expected a bounded explicit source/rights reference')
    return value


@dataclass(frozen=True, init=False)
class ExperimentalVersionReplay:
    """Immutable exact-byte inspection experiment; never enabled by default.

Manual mount only, intentionally no standalone server/provisioning command.
Source/rights references and a matching caller-supplied digest record intent;
they do not prove Nintendo provenance, rights, valid signature or native use.
    """
    _capture: bytes = field(repr=False)
    source_ref: str = field(repr=False)
    rights_ref: str = field(repr=False)

    def __init__(self, capture: bytes, *, expected_sha256: str,
                 source_ref: str, rights_ref: str):
        inspected = inspect_version_capture(capture)
        if (type(expected_sha256) is not str
                or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None
                or inspected['sha256'] != expected_sha256):
            raise WiiSpeakVersionError('Explicit capture SHA-256 does not match')
        object.__setattr__(self, '_capture', capture)
        object.__setattr__(self, 'source_ref', _reference(source_ref))
        object.__setattr__(self, 'rights_ref', _reference(rights_ref))

    def metadata(self):
        return dict(inspect_version_capture(self._capture),
                    mode='opaque_capture_inspection_experiment',
                    source_and_rights_references_recorded=True,
                    rights_independently_verified=False,
                    usable_native_version_service_verified=False)

    def get(self, request_target: str):
        if request_target != VERSION_ROUTE:
            return 404, 'application/octet-stream', b''
        return 200, 'application/octet-stream', self._capture
