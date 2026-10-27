"""Real local nonce/crypto/SQLite races; all identities and keys are generated."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import base64
import hashlib
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from jwc24 import wii_shop_challenges as state
from jwc24.wii_shop_ias_challenge import GET_CHALLENGE_ACTION, IAS_NS
from tests.test_wii_shop_ias_challenge import request as challenge_request
from tests.test_wii_shop_proof import certificate, document, raw_signature


def nonce(issued):
    return ET.fromstring(issued.response)[0][0].find(f'{{{IAS_NS}}}Challenge').text


def request(binding):
    return challenge_request(f'<ias:DeviceId>{binding.device_id}</ias:DeviceId>')


class ChallengeStoreInputTests(unittest.TestCase):
    def test_unchecked_result_objects_cannot_claim_a_storage_commit(self):
        from jwc24.wii_shop_proof import DeviceProofInspection
        for value in (state.IssuedChallenge(b'not-issued', 0, 1),
                      state.ChallengeProofReceipt('not-committed', DeviceProofInspection())):
            with self.assertRaisesRegex(state.ChallengeStateError, 'storage commit'):
                value.metadata()

    def test_invalid_binding_request_lifetime_or_clock_never_returns_a_challenge(self):
        binding = state.ChallengeBinding('a' * 64, 1, 1, 2, 'SyncRegistration', 'synthetic')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'not-created'
            store = state.ChallengeStore(root, clock=lambda: 1000)
            cases = [dict(binding=None, ttl_seconds=30), dict(binding=binding, ttl_seconds=0),
                     dict(binding=binding, ttl_seconds=True), dict(binding=binding, ttl_seconds=3601)]
            for args in cases:
                with self.assertRaises(state.ChallengeStateError):
                    store.issue(request(binding), soap_action=GET_CHALLENGE_ACTION, **args)
            with self.assertRaises(state.ChallengeStateError):
                store.issue(b'private-marker', soap_action=GET_CHALLENGE_ACTION,
                            binding=binding, ttl_seconds=30)
            with self.assertRaises(state.ChallengeStateError):
                store.issue(challenge_request(), soap_action=GET_CHALLENGE_ACTION,
                            binding=binding, ttl_seconds=30)
            self.assertFalse(root.exists())
            for value in (float('nan'), float('inf'), True, -1):
                bad = state.ChallengeStore(root, clock=lambda: value)
                with self.assertRaises(state.ChallengeStateError):
                    bad.issue(request(binding), soap_action=GET_CHALLENGE_ACTION,
                              binding=binding, ttl_seconds=30)


@unittest.skipUnless(shutil.which('openssl'), 'Local OpenSSL required for actual generated proof checks')
class ChallengeStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='jwc24-challenge-key-test-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.key_root = Path(cls.temporary.name).resolve()
        if cls.key_root.parent != Path(tempfile.gettempdir()).resolve():
            raise AssertionError('Generated test-key root escaped temporary directory')
        cls.ng_key, cls.ap_key = cls.key_root / 'ng.pem', cls.key_root / 'ap.pem'
        public = []
        for path in (cls.ng_key, cls.ap_key):
            generated = subprocess.run(['openssl', 'genpkey', '-algorithm', 'EC', '-pkeyopt',
                'ec_paramgen_curve:sect233r1', '-out', str(path)], capture_output=True, timeout=30)
            if generated.returncode:
                raise unittest.SkipTest('OpenSSL binary-curve key generation unavailable')
            key = subprocess.run(['openssl', 'pkey', '-in', str(path), '-pubout', '-outform', 'DER'],
                                 capture_output=True, check=True, timeout=15).stdout
            if key[-61] != 4:
                raise AssertionError('Generated key has unexpected point form')
            public.append(key[-60:])
        cls.ng = certificate(b'Root-CA00000001-MS00000002', b'NG12345678', public[0])
        ap = bytearray(certificate(b'Root-CA00000001-MS00000002-NG12345678',
                                  b'AP0001000248414241', public[1]))
        ap[4:64] = cls.sign(cls.ng_key, bytes(ap[0x80:]))
        cls.ap = bytes(ap)
        cls.binding = state.ChallengeBinding(hashlib.sha256(cls.ng).hexdigest(),
            (4 << 32) | 0x12345678, 0x12345678, 0x0001000248414241,
            'SyncRegistration', 'generated synthetic pin; no Nintendo enrollment')

    @staticmethod
    def sign(key, message):
        signed = subprocess.run(['openssl', 'dgst', '-sha1', '-sign', str(key)], input=message,
                                capture_output=True, check=True, timeout=15).stdout
        return raw_signature(signed)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='jwc24-challenge-store-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.assertEqual(self.root.parent, Path(tempfile.gettempdir()).resolve())
        self.clock = [1000]
        self.store = state.ChallengeStore(self.root, clock=lambda: self.clock[0])

    def issue(self, **changes):
        return self.store.issue(request(self.binding), soap_action=GET_CHALLENGE_ACTION,
                                binding=self.binding, ttl_seconds=changes.get('ttl', 60))

    def proof(self, challenge, *, bad_signature=False):
        signature = self.sign(self.ap_key, f'<Challenge>{challenge}</Challenge>'.encode())
        if bad_signature:
            signature = signature[:-1] + bytes([signature[-1] ^ 1])
        return document(self.ng, self.ap, signature, challenge=challenge)

    def consume(self, data, **changes):
        return self.store.consume(data, soap_action=IAS_NS + '/SyncRegistration',
                                  binding=changes.get('binding', self.binding))

    def row(self, challenge):
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            return connection.execute('SELECT consumed_at,receipt_id,request_sha256 FROM challenges '
                                      'WHERE challenge=?', (challenge,)).fetchone()

    def test_real_proof_commits_one_private_receipt_and_replay_rejects_after_restart(self):
        issued = self.issue()
        challenge = nonce(issued)
        self.assertRegex(challenge, r'^[A-Za-z0-9_-]{11}$')
        data = self.proof(challenge)
        receipt = self.consume(data)
        self.assertRegex(receipt.identifier, r'^[0-9a-f]{32}$')
        self.assertEqual(self.row(challenge), (1000, receipt.identifier, hashlib.sha256(data).hexdigest()))
        self.assertTrue(receipt.metadata()['challenge_consumption_committed'])
        self.assertTrue(receipt.metadata()['challenge_freshness_or_replay_verified'])
        for key in ('device_enrollment_or_account_authorized',
                    'nintendo_certificate_authority_chain_verified', 'account_registration_transaction_committed'):
            self.assertFalse(receipt.metadata()[key])
        for output in (repr(issued), repr(receipt), repr(self.binding), str(receipt.metadata())):
            self.assertNotIn(challenge, output)
            self.assertNotIn(self.binding.certificate_sha256, output)
        reopened = state.ChallengeStore(self.root, clock=lambda: 1001)
        with self.assertRaisesRegex(state.ChallengeStateError, 'consumed'):
            reopened.consume(data, soap_action=IAS_NS + '/SyncRegistration', binding=self.binding)

    def test_invalid_crypto_does_not_burn_challenge_and_scope_is_bound_to_issuance(self):
        challenge = nonce(self.issue())
        with self.assertRaisesRegex(state.ChallengeStateError, 'did not verify'):
            self.consume(self.proof(challenge, bad_signature=True))
        self.assertEqual(self.row(challenge), (None, None, None))
        with patch.object(state, 'inspect_registration_sync_proof') as crypto:
            for changed in (replace(self.binding, operation='GetRegistrationInfo'),
                            replace(self.binding, title_id=self.binding.title_id + 1),
                            replace(self.binding, certificate_sha256='f' * 64)):
                with self.assertRaisesRegex(state.ChallengeStateError, 'binding'):
                    self.consume(self.proof(challenge), binding=changed)
            crypto.assert_not_called()
        self.assertTrue(self.consume(self.proof(challenge)).metadata()['challenge_consumption_committed'])

    def test_expiry_and_clock_before_issuance_reject_before_crypto(self):
        issued = self.issue(ttl=3)
        challenge = nonce(issued)
        data = self.proof(challenge)
        with patch.object(state, 'inspect_registration_sync_proof') as crypto:
            for now in (999, 1003, 2000):
                self.clock[0] = now
                with self.assertRaisesRegex(state.ChallengeStateError, 'validity window'):
                    self.consume(data)
            crypto.assert_not_called()
        self.assertEqual(self.row(challenge), (None, None, None))

    def test_expiry_is_rechecked_after_actual_crypto_without_consuming(self):
        challenge = nonce(self.issue(ttl=3))
        data = self.proof(challenge)
        original = state.inspect_registration_sync_proof
        def delayed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.clock[0] = 1003
            return result
        with patch.object(state, 'inspect_registration_sync_proof', side_effect=delayed):
            with self.assertRaisesRegex(state.ChallengeStateError, 'validity window'):
                self.consume(data)
        self.assertEqual(self.row(challenge), (None, None, None))

    def test_two_real_proofs_racing_across_connections_have_only_one_winner(self):
        challenge = nonce(self.issue())
        data = self.proof(challenge)
        rendezvous = threading.Barrier(2)
        original = state.inspect_registration_sync_proof
        def verified(*args, **kwargs):
            result = original(*args, **kwargs)
            rendezvous.wait(timeout=15)
            return result
        def consume():
            try:
                return state.ChallengeStore(self.root, clock=lambda: 1000).consume(
                    data, soap_action=IAS_NS + '/SyncRegistration', binding=self.binding)
            except state.ChallengeStateError:
                return None
        with patch.object(state, 'inspect_registration_sync_proof', side_effect=verified):
            with ThreadPoolExecutor(max_workers=2) as workers:
                results = list(workers.map(lambda _: consume(), range(2)))
        winners = [value for value in results if value is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(self.row(challenge)[1], winners[0].identifier)

    def test_issuance_integrity_and_unknown_challenges_fail_closed(self):
        challenge = nonce(self.issue())
        data = self.proof(challenge)
        with closing(sqlite3.connect(self.store.database_path)) as connection, connection:
            connection.execute("UPDATE challenges SET binding=binding||' ' WHERE challenge=?", (challenge,))
        with self.assertRaisesRegex(state.ChallengeStateError, 'binding is invalid'):
            self.consume(data)
        with self.assertRaisesRegex(state.ChallengeStateError, 'not issued'):
            self.consume(self.proof('Z' * 11))

    def test_duplicate_generator_values_do_not_replace_an_issued_challenge(self):
        first = nonce(self.issue())
        with patch.object(state.secrets, 'token_urlsafe', return_value=first):
            with self.assertRaisesRegex(state.ChallengeStateError, 'uniqueness'):
                self.issue()
        self.assertEqual(self.row(first), (None, None, None))

    def test_actual_commit_failure_returns_no_receipt_and_preserves_nonce_for_retry(self):
        challenge = nonce(self.issue())
        data = self.proof(challenge)
        original = sqlite3.connect
        def denied_commit(*args, **kwargs):
            connection = original(*args, **kwargs)
            changed = [False]
            def authorize(action, first, _second, _database, _source):
                if action == sqlite3.SQLITE_UPDATE and first == 'challenges':
                    changed[0] = True
                if action == sqlite3.SQLITE_TRANSACTION and first == 'COMMIT' and changed[0]:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            connection.set_authorizer(authorize)
            return connection
        with patch.object(state.sqlite3, 'connect', side_effect=denied_commit):
            with self.assertRaisesRegex(state.ChallengeStateError, 'storage operation'):
                self.consume(data)
        self.assertEqual(self.row(challenge), (None, None, None))
        self.assertTrue(self.consume(data).metadata()['challenge_consumption_committed'])

    def test_issuance_commit_failure_never_returns_a_challenge(self):
        original = sqlite3.connect
        def denied_commit(*args, **kwargs):
            connection = original(*args, **kwargs)
            inserted = [False]
            def authorize(action, first, _second, _database, _source):
                if action == sqlite3.SQLITE_INSERT and first == 'challenges':
                    inserted[0] = True
                if action == sqlite3.SQLITE_TRANSACTION and first == 'COMMIT' and inserted[0]:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            connection.set_authorizer(authorize)
            return connection
        with patch.object(state.sqlite3, 'connect', side_effect=denied_commit):
            with self.assertRaisesRegex(state.ChallengeStateError, 'storage operation'):
                self.issue()
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM challenges').fetchone()[0], 0)

    def test_expiry_before_response_returns_no_issued_result(self):
        with patch.object(self.store, 'clock', side_effect=(1000, 1001)):
            with self.assertRaisesRegex(state.ChallengeStateError, 'expired before'):
                self.issue(ttl=1)
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            self.assertEqual(connection.execute('SELECT issued_at,expires_at,consumed_at FROM challenges').fetchall(),
                             [(1000, 1001, None)])

    def test_issuance_changed_while_real_crypto_runs_cannot_produce_a_receipt(self):
        challenge = nonce(self.issue())
        data = self.proof(challenge)
        original = state.inspect_registration_sync_proof
        def changed_issuance(*args, **kwargs):
            result = original(*args, **kwargs)
            with closing(sqlite3.connect(self.store.database_path)) as connection, connection:
                connection.execute('UPDATE challenges SET expires_at=expires_at+1 WHERE challenge=?', (challenge,))
            return result
        with patch.object(state, 'inspect_registration_sync_proof', side_effect=changed_issuance):
            with self.assertRaisesRegex(state.ChallengeStateError, 'changed during'):
                self.consume(data)
        self.assertEqual(self.row(challenge), (None, None, None))

    def test_unrelated_database_is_not_migrated_or_modified(self):
        with closing(sqlite3.connect(self.store.database_path)) as connection, connection:
            connection.execute('CREATE TABLE owner_data (value TEXT)')
            connection.execute("INSERT INTO owner_data VALUES ('private-marker')")
        before = self.store.database_path.read_bytes()
        with self.assertRaisesRegex(state.ChallengeStateError, 'format is unsupported') as caught:
            self.issue()
        self.assertEqual(before, self.store.database_path.read_bytes())
        self.assertNotIn('private-marker', str(caught.exception))

    def test_committed_issuance_uses_original_reader_capacity_without_profile_operations(self):
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
        except ImportError:
            self.skipTest('Optional native verification dependencies unavailable')
        from tests import test_wii_shop_url as native_fixture
        from tools.verify_wii_shop_get_challenge import verify_get_challenge
        issued = self.issue()
        source = native_fixture.NativeShopUrlTests.source(self)
        result = verify_get_challenge(source, issued.response)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['challenge_bytes'], nonce(issued).encode('ascii'))
        self.assertTrue(result['native_challenge_reader_executed'])
        self.assertFalse(result['account_or_device_authorized'])

    def test_original_getchallenge_signer_and_registration_wire_feed_real_local_consumption(self):
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
        except ImportError:
            self.skipTest('Optional native verification dependencies unavailable')
        from tests import test_wii_shop_url as native_fixture
        from tools.verify_wii_shop_get_challenge import verify_get_challenge, SyntheticRequestEnvironment
        from tools.verify_wii_shop_signing import verify_signing_wrapper
        from tools.verify_wii_shop_registration_sync import (
            verify_registration_sync, SyntheticRegistrationEnvironment, SyntheticRegistrationProof)
        from jwc24.wii_shop_ias_challenge import EvidencedChallenge, serialize_get_challenge_response
        from jwc24.wii_shop_registration import serialize_registration_sync_response
        source = native_fixture.NativeShopUrlTests.source(self)
        environment = SyntheticRequestEnvironment(device_id=str(self.binding.device_id), key_pair_confirmed=True)
        bootstrap = serialize_get_challenge_response(
            challenge=EvidencedChallenge('bootstrap', 'synthetic-only native request capture'),
            error_code='0', status_source_ref='synthetic-only')
        original = verify_get_challenge(source, bootstrap, environment=environment)
        issued = self.store.issue(original['request_bytes'], soap_action=GET_CHALLENGE_ACTION,
                                  binding=self.binding, ttl_seconds=60)
        received = verify_get_challenge(source, issued.response, environment=environment)
        self.assertEqual(received['status'], 0)
        message = b'<Challenge>' + received['challenge_bytes'] + b'</Challenge>'
        encoded = verify_signing_wrapper(source, message, signature=self.sign(self.ap_key, message),
                                         signer_certificate=self.ap)
        proof = SyntheticRegistrationProof(received['challenge_bytes'].decode('ascii'),
            base64.b64encode(self.ng).decode('ascii'), encoded.signature_base64.decode('ascii'),
            encoded.certificate_base64.decode('ascii'))
        # Deliberate reported service error prevents a synthetic account assignment.
        # This test proves request construction/receipt, not a working account flow.
        reported_error = serialize_registration_sync_response(operation='SyncRegistration', registration=None,
            error_code='42', status_source_ref='synthetic native request capture; no account authority')
        native = verify_registration_sync(source, reported_error, proof=proof,
            environment=SyntheticRegistrationEnvironment(device_id=str(self.binding.device_id), key_pair_confirmed=True))
        self.assertEqual(native['signed_payload_bytes'], message)
        self.assertEqual(native['status'], -4015)
        self.assertFalse(native['native_account_assignment_executed'])
        self.assertFalse(native['connected_flag'])
        self.assertTrue(native['object_heap_stack_and_write_bounds_verified'])
        result = self.consume(native['request_bytes'])
        self.assertTrue(result.metadata()['challenge_consumption_committed'])
        self.assertFalse(result.metadata()['device_enrollment_or_account_authorized'])
