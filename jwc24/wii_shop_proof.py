"""Offline Shop proof verification against an explicitly pinned device cert.

This verifies two legacy ECC signatures. A caller-provided pin is not a
Nintendo trust chain, enrollment policy, account, entitlement or replay check.
No server routes, credentials, signer or identity generator are provided.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import os
from pathlib import Path
import re
import subprocess
import tempfile

from .wii_shop_registration import (RegistrationContractError, parse_registration_sync_request,
                                    registration_sync_signing_bytes)

_ECC_CERT_BYTES = 384
_ECC_SIGNATURE_BYTES = 60
_ECC_ORDER = int('01000000000000000000000000000013e974e72f8a6922031d2603cfe0d7', 16)
_ECC_SIGNATURE_TYPE = 0x00010002
_CHECKED = object()


class DeviceProofError(ValueError):
    """A fixed local diagnostic; no input, key or identity values are included."""


@dataclass(frozen=True)
class PinnedDeviceContext:
    certificate_sha256: str = field(repr=False)
    device_id: int = field(repr=False)
    ng_id: int = field(repr=False)
    title_id: int = field(repr=False)
    challenge: str = field(repr=False)
    operation: str
    evidence_ref: str = field(repr=False)


@dataclass(frozen=True)
class DeviceProofInspection:
    """Successful mathematical/context inspection, never an account receipt."""

    _checked: object = field(default=None, init=False, repr=False, compare=False)

    def metadata(self):
        if self._checked is not _CHECKED:
            raise DeviceProofError('Proof inspection has not completed signature/context verification')
        return {
            'pinned_device_certificate_matched': True,
            'application_certificate_signature_verified': True,
            'challenge_signature_verified': True,
            'explicit_device_title_operation_and_challenge_matched': True,
            'crypto': 'ECDSA-sect233r1-SHA1',
            'request_operation_device_and_account_fields_signed': False,
            'pin_provenance_independently_verified': False,
            'nintendo_certificate_authority_chain_verified': False,
            'challenge_freshness_or_replay_verified': False,
            'exclusive_private_key_possession_verified': False,
            'device_enrollment_or_account_authorized': False,
            'profile_modified': False, 'network_used': False,
        }


@dataclass(frozen=True)
class _Certificate:
    raw: bytes = field(repr=False)
    signature: bytes = field(repr=False)
    issuer: bytes = field(repr=False)
    name: bytes = field(repr=False)
    public_key: bytes = field(repr=False)


def _label(data):
    end = data.find(b'\0')
    if end < 1 or re.fullmatch(rb'[A-Za-z0-9-]+', data[:end]) is None:
        raise DeviceProofError('Unsupported certificate identity field')
    return data[:end]


def _certificate(data):
    if (type(data) is not bytes or len(data) != _ECC_CERT_BYTES
            or int.from_bytes(data[:4], 'big') != _ECC_SIGNATURE_TYPE
            or int.from_bytes(data[0xC0:0xC4], 'big') != 2):
        raise DeviceProofError('Expected the reviewed ECC certificate shape')
    return _Certificate(data, data[4:64], _label(data[0x80:0xC0]),
                        _label(data[0xC4:0x104]), data[0x108:0x144])


def _base64(value, size):
    if type(value) is not str or len(value) != (size + 2) // 3 * 4:
        raise DeviceProofError('Unsupported proof field byte length')
    try:
        encoded = value.encode('ascii')
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeError):
        raise DeviceProofError('Invalid proof Base64') from None
    if len(data) != size or base64.b64encode(data) != encoded:
        raise DeviceProofError('Noncanonical or unsupported proof Base64')
    return data


def _context(context):
    if type(context) is not PinnedDeviceContext:
        raise DeviceProofError('An explicit pinned device context is required')
    if (type(context.certificate_sha256) is not str
            or re.fullmatch(r'[0-9a-f]{64}', context.certificate_sha256) is None
            or type(context.operation) is not str
            or context.operation not in ('SyncRegistration', 'GetRegistrationInfo')):
        raise DeviceProofError('Invalid explicit pin or operation context')
    for value, bits in ((context.device_id, 64), (context.ng_id, 32), (context.title_id, 64)):
        if type(value) is not int or not 0 <= value < 1 << bits:
            raise DeviceProofError('Invalid explicit identity context width')
    if context.device_id & 0xFFFFFFFF != context.ng_id:
        raise DeviceProofError('Explicit device and NG contexts disagree')
    try:
        challenge = context.challenge.encode('utf-8') if type(context.challenge) is str else b''
        evidence = context.evidence_ref.encode('utf-8') if type(context.evidence_ref) is str else b''
    except UnicodeError:
        raise DeviceProofError('Invalid explicit challenge or evidence text') from None
    if not 1 <= len(challenge) <= 11 or b'\0' in challenge:
        raise DeviceProofError('Explicit challenge is outside the reviewed native capacity')
    if any(ord(character) < 32 for character in context.challenge):
        raise DeviceProofError('Challenge text is outside the local XML-stable subset')
    if not evidence.strip() or len(evidence) > 2048 or any(byte < 32 for byte in evidence):
        raise DeviceProofError('An explicit bounded pin evidence reference is required')


def _der(tag, data):
    if len(data) < 128:
        length = bytes([len(data)])
    else:
        raw = len(data).to_bytes((len(data).bit_length() + 7) // 8, 'big')
        length = bytes([0x80 | len(raw)]) + raw
    return bytes([tag]) + length + data


def _signature_der(signature):
    if type(signature) is not bytes or len(signature) != _ECC_SIGNATURE_BYTES:
        raise DeviceProofError('Expected one raw ECC signature')
    integers = []
    for raw in (signature[:30], signature[30:]):
        value = int.from_bytes(raw, 'big')
        if not 0 < value < _ECC_ORDER:
            raise DeviceProofError('ECC signature scalar is outside the curve order')
        raw = raw.lstrip(b'\0')
        if raw[0] & 0x80:
            raw = b'\0' + raw
        integers.append(_der(2, raw))
    return _der(0x30, b''.join(integers))


def _public_key_der(public_key):
    if type(public_key) is not bytes or len(public_key) != 60:
        raise DeviceProofError('Expected one raw binary-curve public key')
    # Standard SubjectPublicKeyInfo: id-ecPublicKey, sect233r1, SEC1 point.
    algorithm = _der(0x30, bytes.fromhex('06072a8648ce3d020106052b8104001b'))
    return _der(0x30, algorithm + _der(3, b'\0\x04' + public_key))


def _verify(public_key, signature, message):
    key, signature = _public_key_der(public_key), _signature_der(signature)
    try:
        with tempfile.TemporaryDirectory(prefix='jwc24-shop-proof-') as directory:
            root = Path(directory).resolve()
            if root.parent != Path(tempfile.gettempdir()).resolve():
                raise DeviceProofError('Proof scratch directory escaped its explicit temporary root')
            for filename, data in (('public.der', key), ('signature.der', signature)):
                descriptor = os.open(root / filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(data)
            checked = subprocess.run(
                ['openssl', 'pkey', '-pubin', '-inform', 'DER', '-in', str(root / 'public.der'),
                 '-pubcheck', '-noout'], capture_output=True, check=False, timeout=15)
            if checked.returncode:
                raise DeviceProofError('ECC public key did not validate')
            result = subprocess.run(
                ['openssl', 'dgst', '-sha1', '-keyform', 'DER', '-verify', str(root / 'public.der'),
                 '-signature', str(root / 'signature.der')],
                input=message, capture_output=True, check=False, timeout=15)
            if result.returncode:
                raise DeviceProofError('ECC proof signature did not verify')
    except (OSError, subprocess.TimeoutExpired):
        raise DeviceProofError('Offline ECC proof verification could not run') from None


def inspect_registration_sync_proof(data: bytes, *, soap_action: str,
                                    context: PinnedDeviceContext) -> DeviceProofInspection:
    """Verify a sync proof against an explicit, previously enrolled device pin.

    Pin enrollment/provenance, trust roots, challenge issue/consumption and all
    account/session authority remain the caller's separate unfinished work.
    This function deliberately does not return an authenticated account token.
    """
    _context(context)
    try:
        request = parse_registration_sync_request(data, soap_action=soap_action)
    except RegistrationContractError:
        raise DeviceProofError('Registration proof request did not pass structural inspection') from None
    proof = dict(request.proof_fields)
    if request.operation != context.operation:
        raise DeviceProofError('Request operation does not match the explicit context')
    if not hmac.compare_digest(proof['Challenge'].encode('utf-8'), context.challenge.encode('utf-8')):
        raise DeviceProofError('Request challenge does not match the explicit context')
    device = dict(request.common_fields).get('DeviceId')
    if (type(device) is not str or re.fullmatch(r'0|[1-9][0-9]{0,19}', device) is None
            or int(device) != context.device_id):
        raise DeviceProofError('Request device does not match the explicit context')
    ng_raw = _base64(proof['DeviceCert'], _ECC_CERT_BYTES)
    if not hmac.compare_digest(hashlib.sha256(ng_raw).hexdigest(), context.certificate_sha256):
        raise DeviceProofError('Device certificate does not match the explicit pin')
    ng, ap = _certificate(ng_raw), _certificate(_base64(proof['CertChain'], _ECC_CERT_BYTES))
    if re.fullmatch(rb'NG[0-9A-Fa-f]{8}', ng.name) is None or int(ng.name[2:], 16) != context.ng_id:
        raise DeviceProofError('Device certificate identity does not match the explicit context')
    if (re.fullmatch(rb'AP[0-9A-Fa-f]{16}', ap.name) is None
            or int(ap.name[2:], 16) != context.title_id
            or not hmac.compare_digest(ap.issuer, ng.issuer + b'-' + ng.name)):
        raise DeviceProofError('Application certificate does not match the explicit device/title context')
    _verify(ng.public_key, ap.signature, ap.raw[0x80:])
    _verify(ap.public_key, _base64(proof['Signature'], _ECC_SIGNATURE_BYTES),
            registration_sync_signing_bytes(request))
    result = DeviceProofInspection()
    object.__setattr__(result, '_checked', _CHECKED)
    return result
