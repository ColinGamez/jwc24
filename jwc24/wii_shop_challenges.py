"""Durable replacement-service challenge issuance and single-use proof receipts.

This binds the recovered IAS wire contract to actual local nonce state. It has
no listener, device enrollment, Nintendo CA authority or account registration.
Caller-selected pins and their provenance remain separate requirements.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid

from .wii_shop_ias_challenge import (ChallengeContractError, EvidencedChallenge,
                                    parse_get_challenge_request, serialize_get_challenge_response)
from .wii_shop_proof import (DeviceProofError, DeviceProofInspection, PinnedDeviceContext,
                             inspect_registration_sync_proof, validate_pinned_device_context)
from .wii_shop_registration import RegistrationContractError, parse_registration_sync_request

_APPLICATION_ID = 0x4A574350
_VERSION = 1
_NONCE = re.compile(r'[A-Za-z0-9_-]{11}\Z')
_MAX_CLOCK = (1 << 63) - 3601
_COMMITTED = object()


class ChallengeStateError(ValueError):
    """Fixed local diagnostic without request, identity, pin or database values."""


@dataclass(frozen=True)
class ChallengeBinding:
    certificate_sha256: str = field(repr=False)
    device_id: int = field(repr=False)
    ng_id: int = field(repr=False)
    title_id: int = field(repr=False)
    operation: str
    evidence_ref: str = field(repr=False)

    def context(self, challenge):
        value = PinnedDeviceContext(self.certificate_sha256, self.device_id, self.ng_id,
                                    self.title_id, challenge, self.operation, self.evidence_ref)
        validate_pinned_device_context(value)
        return value

    def identity(self):
        # The label is retained for provenance but is not a cryptographic identity.
        return (self.certificate_sha256, self.device_id, self.ng_id, self.title_id, self.operation)


def _binding(binding):
    if type(binding) is not ChallengeBinding:
        raise ChallengeStateError('An explicit pinned challenge binding is required')
    try:
        binding.context('validation')
    except DeviceProofError:
        raise ChallengeStateError('Challenge binding did not pass structural inspection') from None


def _document(binding):
    return json.dumps({name: getattr(binding, name) for name in binding.__dataclass_fields__},
                      sort_keys=True, ensure_ascii=True, separators=(',', ':'))


def _stored_binding(document, digest):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate')
            result[key] = value
        return result
    try:
        if type(document) is not str or len(document) > 8192:
            raise ValueError('size')
        if hashlib.sha256(document.encode('utf-8')).hexdigest() != digest:
            raise ValueError('digest')
        decoded = json.loads(document, object_pairs_hook=unique)
        value = ChallengeBinding(**decoded)
        _binding(value)
        if _document(value) != document:
            raise ValueError('canonical')
        return value
    except (ValueError, TypeError, UnicodeError):
        raise ChallengeStateError('Stored challenge binding is invalid') from None


@dataclass(frozen=True)
class IssuedChallenge:
    response: bytes = field(repr=False)
    issued_at: int
    expires_at: int
    _committed: object = field(default=None, init=False, repr=False, compare=False)

    def metadata(self):
        if self._committed is not _COMMITTED:
            raise ChallengeStateError('Challenge issuance has not completed its storage commit')
        return {'challenge_issuance_committed': True, 'native_challenge_byte_capacity_checked': True,
                'issuer': 'JWC24 replacement service', 'device_enrollment_or_account_authorized': False,
                'nintendo_certificate_authority_chain_verified': False, 'network_used': False}


@dataclass(frozen=True)
class ChallengeProofReceipt:
    identifier: str
    inspection: DeviceProofInspection = field(repr=False)
    _committed: object = field(default=None, init=False, repr=False, compare=False)

    def metadata(self):
        if self._committed is not _COMMITTED:
            raise ChallengeStateError('Challenge consumption has not completed its storage commit')
        return {**self.inspection.metadata(),
                'challenge_freshness_or_replay_verified': True,
                'challenge_consumption_committed': True,
                'challenge_bound_to_issued_context': True,
                'clock_source_independently_verified': False,
                'account_registration_transaction_committed': False}


class ChallengeStore:
    """Private SQLite state selected explicitly by the service operator.

    Proof crypto runs outside the write lock. A second transaction rechecks the
    same immutable issuance, its expiry and single-use state before returning a
    receipt. A duplicate, even identical, is rejected as a replay. Receipt IDs
    are not account tokens or idempotent registration results.
    """

    def __init__(self, root: Path, *, clock=time.time):
        if not callable(clock):
            raise ChallengeStateError('A local challenge clock is required')
        self.root = Path(root).resolve()
        self.database_path = self.root / 'challenge_state.sqlite3'
        self.clock = clock

    def _now(self):
        try:
            value = self.clock()
        except Exception:
            raise ChallengeStateError('Local challenge clock could not be read') from None
        if (type(value) not in (int, float) or not 0 <= value <= _MAX_CLOCK
                or not math.isfinite(value)):
            raise ChallengeStateError('Local challenge clock is outside its supported range')
        return int(value)

    @contextmanager
    def _connection(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if self.database_path.resolve().parent != self.root:
                raise ChallengeStateError('Challenge database escapes its explicit root')
            with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
                connection.execute('PRAGMA synchronous = FULL')
                with connection:
                    connection.execute('BEGIN IMMEDIATE')
                    app = connection.execute('PRAGMA application_id').fetchone()[0]
                    version = connection.execute('PRAGMA user_version').fetchone()[0]
                    tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                    if app == 0 and version == 0 and not tables:
                        connection.execute('''CREATE TABLE challenges (
                            challenge TEXT PRIMARY KEY,
                            binding TEXT NOT NULL, binding_sha256 TEXT NOT NULL,
                            issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                            consumed_at INTEGER, receipt_id TEXT UNIQUE, request_sha256 TEXT
                        )''')
                        connection.execute(f'PRAGMA application_id = {_APPLICATION_ID}')
                        connection.execute(f'PRAGMA user_version = {_VERSION}')
                    elif app != _APPLICATION_ID or version != _VERSION:
                        raise ChallengeStateError('Challenge database format is unsupported')
                yield connection
        except (sqlite3.Error, OSError):
            raise ChallengeStateError('Challenge storage operation could not complete') from None

    @staticmethod
    def _row(connection, challenge):
        return connection.execute('''SELECT binding,binding_sha256,issued_at,expires_at,
                                    consumed_at,receipt_id,request_sha256
                                    FROM challenges WHERE challenge=?''', (challenge,)).fetchone()

    @staticmethod
    def _require_fresh(row, expected, now):
        if row is None:
            raise ChallengeStateError('Challenge was not issued by this store')
        stored = _stored_binding(row[0], row[1])
        if stored.identity() != expected.identity():
            raise ChallengeStateError('Challenge binding does not match the explicit context')
        issued, expires = row[2:4]
        if (type(issued) is not int or type(expires) is not int or not 0 <= issued < expires <= _MAX_CLOCK + 3600
                or not 1 <= expires - issued <= 3600):
            raise ChallengeStateError('Stored challenge window is invalid')
        if any(value is not None for value in row[4:]):
            raise ChallengeStateError('Challenge has already been consumed or is inconsistent')
        if not issued <= now < expires:
            raise ChallengeStateError('Challenge is outside its issued validity window')
        return stored

    def issue(self, data: bytes, *, soap_action: str, binding: ChallengeBinding,
              ttl_seconds: int) -> IssuedChallenge:
        """Commit a genuine local challenge before returning its IAS response.

        An explicit matching DeviceId is required by this supported service path;
        the broader offline codec can inspect other native request forms.
        """
        _binding(binding)
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise ChallengeStateError('An explicit bounded challenge lifetime is required')
        try:
            request = parse_get_challenge_request(data, soap_action=soap_action)
        except ChallengeContractError:
            raise ChallengeStateError('Challenge request did not pass structural inspection') from None
        device = dict(request.common_fields).get('DeviceId')
        if device != str(binding.device_id):
            raise ChallengeStateError('Challenge request device does not match the explicit binding')
        document = _document(binding)
        digest = hashlib.sha256(document.encode('utf-8')).hexdigest()
        with self._connection() as connection:
            for _ in range(8):
                challenge = secrets.token_urlsafe(8)  # Exactly 11 ASCII bytes, 64 random bits.
                if _NONCE.fullmatch(challenge) is None:
                    raise ChallengeStateError('Challenge generator returned an unsupported value')
                response = serialize_get_challenge_response(
                    challenge=EvidencedChallenge(challenge, 'urn:jwc24:durable-local-challenge'),
                    error_code='0', status_source_ref='urn:jwc24:durable-local-challenge-issuance')
                try:
                    with connection:
                        connection.execute('BEGIN IMMEDIATE')
                        now = self._now()
                        connection.execute('''INSERT INTO challenges
                            (challenge,binding,binding_sha256,issued_at,expires_at) VALUES (?,?,?,?,?)''',
                            (challenge, document, digest, now, now + ttl_seconds))
                    if not now <= self._now() < now + ttl_seconds:
                        raise ChallengeStateError('Issued challenge expired before its response was returned')
                    result = IssuedChallenge(response, now, now + ttl_seconds)
                    object.__setattr__(result, '_committed', _COMMITTED)
                    return result
                except sqlite3.IntegrityError:
                    if self._row(connection, challenge) is None:
                        raise
            raise ChallengeStateError('Challenge uniqueness attempts were exhausted')

    def consume(self, data: bytes, *, soap_action: str,
                binding: ChallengeBinding) -> ChallengeProofReceipt:
        """Verify proof and commit one receipt, without registering an account."""
        _binding(binding)
        try:
            request = parse_registration_sync_request(data, soap_action=soap_action)
        except RegistrationContractError:
            raise ChallengeStateError('Proof request did not pass structural inspection') from None
        challenge = dict(request.proof_fields)['Challenge']
        if _NONCE.fullmatch(challenge) is None:
            raise ChallengeStateError('Proof challenge is outside this store issuance format')
        with self._connection() as connection:
            initial = self._row(connection, challenge)
            stored = self._require_fresh(initial, binding, self._now())
            try:
                inspection = inspect_registration_sync_proof(
                    data, soap_action=soap_action, context=stored.context(challenge))
            except DeviceProofError:
                raise ChallengeStateError('Challenge proof did not verify') from None
            receipt = uuid.uuid4().hex
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                current = self._row(connection, challenge)
                now = self._now()
                self._require_fresh(current, binding, now)
                if current != initial:
                    raise ChallengeStateError('Challenge issuance changed during proof verification')
                changed = connection.execute('''UPDATE challenges
                    SET consumed_at=?,receipt_id=?,request_sha256=?
                    WHERE challenge=? AND consumed_at IS NULL AND receipt_id IS NULL AND request_sha256 IS NULL''',
                    (now, receipt, hashlib.sha256(data).hexdigest(), challenge)).rowcount
                if changed != 1:
                    raise ChallengeStateError('Challenge was not consumed exactly once')
            result = ChallengeProofReceipt(receipt, inspection)
            object.__setattr__(result, '_committed', _COMMITTED)
            return result
