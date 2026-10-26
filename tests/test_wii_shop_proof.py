"""Generated binary-curve fixtures, not Nintendo device/account material."""
from dataclasses import replace
import base64
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from jwc24.wii_shop_proof import (DeviceProofError, DeviceProofInspection, PinnedDeviceContext,
                                 inspect_registration_sync_proof)
from jwc24.wii_shop_registration import IAS_NS, SOAP_NS


def certificate(issuer, name, public_key):
    data = bytearray(384)
    struct.pack_into('>I', data, 0, 0x10002)
    data[0x80:0x80 + len(issuer)] = issuer
    struct.pack_into('>I', data, 0xC0, 2)
    data[0xC4:0xC4 + len(name)] = name
    struct.pack_into('>I', data, 0x104, 7)
    data[0x108:0x144] = public_key
    return bytes(data)


def raw_signature(der):
    # Independent test-only ASN.1 reader for OpenSSL's short ECDSA signature.
    if der[0] != 0x30 or der[1] != len(der) - 2:
        raise AssertionError('Unexpected generated ECDSA sequence')
    values, cursor = [], 2
    for _ in range(2):
        if der[cursor] != 2:
            raise AssertionError('Unexpected generated ECDSA integer')
        length = der[cursor + 1]
        value = int.from_bytes(der[cursor + 2:cursor + 2 + length], 'big')
        values.append(value.to_bytes(30, 'big'))
        cursor += 2 + length
    if cursor != len(der):
        raise AssertionError('Trailing generated signature bytes')
    return b''.join(values)


def document(ng, ap, signature, *, challenge='a&b', device_id=(4 << 32) | 0x12345678,
             operation='SyncRegistration', override=None):
    envelope = ET.Element(f'{{{SOAP_NS}}}Envelope')
    body = ET.SubElement(envelope, f'{{{SOAP_NS}}}Body')
    request = ET.SubElement(body, f'{{{IAS_NS}}}{operation}')
    values = {'Version': '2.0', 'MessageId': 'synthetic-request', 'DeviceId': str(device_id),
              'Region': 'JPN', 'Country': 'JP', 'Language': 'ja',
              'DeviceCert': base64.b64encode(ng).decode(), 'Signature': base64.b64encode(signature).decode(),
              'CertChain': base64.b64encode(ap).decode(), 'Challenge': challenge}
    values.update(override or {})
    for name, value in values.items():
        ET.SubElement(request, f'{{{IAS_NS}}}{name}').text = value
    return ET.tostring(envelope, encoding='utf-8')


class DeviceProofInputTests(unittest.TestCase):
    def test_invalid_context_rejects_before_xml_or_crypto_without_echo(self):
        context = PinnedDeviceContext('a' * 64, 1, 1, 2, 'synthetic', 'SyncRegistration', 'synthetic-evidence')
        for bad in (None, replace(context, certificate_sha256='private-marker'),
                    replace(context, device_id=True), replace(context, ng_id=2),
                    replace(context, title_id=1 << 64), replace(context, challenge='x' * 12),
                    replace(context, challenge=''), replace(context, challenge='\r'),
                    replace(context, evidence_ref='')):
            with self.subTest(context=type(bad).__name__), self.assertRaises(DeviceProofError) as caught:
                inspect_registration_sync_proof(b'not XML', soap_action=IAS_NS + '/SyncRegistration', context=bad)
            self.assertNotIn('private-marker', str(caught.exception))
        self.assertNotIn('synthetic-evidence', repr(context))
        self.assertNotIn('synthetic', repr(context))

    def test_unchecked_result_cannot_report_verified_signatures(self):
        with self.assertRaisesRegex(DeviceProofError, 'has not completed'):
            DeviceProofInspection().metadata()


@unittest.skipUnless(shutil.which('openssl'), 'Local OpenSSL required for generated binary-curve proofs')
class DeviceProofCryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='jwc24-shop-proof-test-')
        cls.root = Path(cls.temporary.name).resolve()
        if cls.root.parent != Path(tempfile.gettempdir()).resolve():
            raise AssertionError('Generated test-key directory escaped the explicit temporary root')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.ng_key, cls.ap_key = cls.root / 'generated-ng.pem', cls.root / 'generated-ap.pem'
        keys = []
        for path in (cls.ng_key, cls.ap_key):
            result = subprocess.run(['openssl', 'genpkey', '-algorithm', 'EC', '-pkeyopt',
                                     'ec_paramgen_curve:sect233r1', '-out', str(path)],
                                    capture_output=True, timeout=30, check=False)
            if result.returncode:
                raise unittest.SkipTest('Local OpenSSL backend does not support generating sect233r1 keys')
            result = subprocess.run(['openssl', 'pkey', '-in', str(path), '-pubout', '-outform', 'DER'],
                                    capture_output=True, timeout=15, check=True)
            if result.stdout[-61] != 4:
                raise AssertionError('Expected a generated uncompressed binary-curve point')
            keys.append(result.stdout[-60:])
        cls.ng = certificate(b'Root-CA00000001-MS00000002', b'NG12345678', keys[0])
        ap = certificate(b'Root-CA00000001-MS00000002-NG12345678', b'AP0001000248414241', keys[1])
        cls.ap = cls.sign_certificate(ap)
        cls.signature = cls.sign(cls.ap_key, b'<Challenge>a&b</Challenge>')
        cls.context = PinnedDeviceContext(hashlib.sha256(cls.ng).hexdigest(), (4 << 32) | 0x12345678,
                                         0x12345678, 0x0001000248414241, 'a&b', 'SyncRegistration',
                                         'generated synthetic fixture; not a Nintendo enrollment')

    @staticmethod
    def sign(key, data):
        result = subprocess.run(['openssl', 'dgst', '-sha1', '-sign', str(key)], input=data,
                                capture_output=True, timeout=15, check=True)
        return raw_signature(result.stdout)

    @classmethod
    def sign_certificate(cls, data):
        result = bytearray(data)
        result[4:64] = cls.sign(cls.ng_key, data[0x80:])
        return bytes(result)

    def inspect(self, data=None, context=None):
        return inspect_registration_sync_proof(data or document(self.ng, self.ap, self.signature),
                                              soap_action=IAS_NS + '/' + (context or self.context).operation,
                                              context=context or self.context)

    def test_both_real_signatures_match_explicit_context_without_authority_claims(self):
        result = self.inspect()
        metadata = result.metadata()
        for name in ('pinned_device_certificate_matched', 'application_certificate_signature_verified',
                     'challenge_signature_verified', 'explicit_device_title_operation_and_challenge_matched'):
            self.assertTrue(metadata[name])
        for name in ('request_operation_device_and_account_fields_signed',
                     'pin_provenance_independently_verified', 'nintendo_certificate_authority_chain_verified',
                     'challenge_freshness_or_replay_verified', 'device_enrollment_or_account_authorized',
                     'exclusive_private_key_possession_verified',
                     'profile_modified', 'network_used'):
            self.assertFalse(metadata[name])
        self.assertNotIn('12345678', str(metadata))
        self.assertNotIn('a&b', repr(result))

    def test_pin_device_title_operation_and_challenge_mismatches_reject(self):
        contexts = [replace(self.context, certificate_sha256='f' * 64),
                    replace(self.context, device_id=self.context.device_id + (1 << 32)),
                    replace(self.context, title_id=self.context.title_id + 1),
                    replace(self.context, challenge='other')]
        for context in contexts:
            with self.subTest(context=repr(context)), self.assertRaises(DeviceProofError):
                self.inspect(context=context)
        with self.assertRaises(DeviceProofError):
            self.inspect(document(self.ng, self.ap, self.signature, operation='GetRegistrationInfo'))
        with self.assertRaises(DeviceProofError):
            self.inspect(document(self.ng, self.ap, self.signature, override={'DeviceId': '00001'}))

    def test_ap_body_signature_and_message_tampering_fail_independently(self):
        for offset in (4, 0x104, 0x17F):
            ap = bytearray(self.ap)
            ap[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(DeviceProofError):
                self.inspect(document(self.ng, bytes(ap), self.signature))
        signature = bytearray(self.signature)
        signature[-1] ^= 1
        with self.assertRaises(DeviceProofError):
            self.inspect(document(self.ng, self.ap, bytes(signature)))
        with self.assertRaises(DeviceProofError):
            self.inspect(document(self.ng, self.ap, self.signature, challenge='changed'),
                         context=replace(self.context, challenge='changed'))

    def test_relinked_application_identity_and_invalid_points_reject(self):
        for offset, value in ((0x80, ord('X')), (0xC4, ord('X'))):
            ap = bytearray(self.ap)
            ap[offset] = value
            with self.subTest(offset=offset), self.assertRaises(DeviceProofError):
                self.inspect(document(self.ng, self.sign_certificate(bytes(ap)), self.signature))
        ap = bytearray(self.ap)
        ap[0x108:0x144] = bytes(60)
        with self.assertRaises(DeviceProofError):
            self.inspect(document(self.ng, self.sign_certificate(bytes(ap)), self.signature))

    def test_exact_raw_shapes_base64_and_signature_scalar_bounds(self):
        for override in ({'Signature': 'not base64 private-marker'},
                         {'CertChain': base64.b64encode(self.ap + b'x').decode()},
                         {'DeviceCert': base64.b64encode(self.ng).decode() + '\n'},
                         {'Signature': base64.b64encode(bytes(60)).decode()},
                         {'Signature': base64.b64encode(b'\xff' * 60).decode()}):
            with self.subTest(field=next(iter(override))), self.assertRaises(DeviceProofError) as caught:
                self.inspect(document(self.ng, self.ap, self.signature, override=override))
            self.assertNotIn('private-marker', str(caught.exception))

    def test_a_caller_pin_does_not_verify_the_device_certificate_issuer_signature(self):
        ng = bytearray(self.ng)
        ng[4:64] = b'\xA5' * 60  # Deliberately no valid issuing-authority signature.
        result = self.inspect(document(bytes(ng), self.ap, self.signature),
                              context=replace(self.context, certificate_sha256=hashlib.sha256(ng).hexdigest()))
        self.assertFalse(result.metadata()['nintendo_certificate_authority_chain_verified'])

    def test_operation_and_other_soap_fields_are_context_checks_not_message_signature_coverage(self):
        alternate = replace(self.context, operation='GetRegistrationInfo')
        result = self.inspect(document(self.ng, self.ap, self.signature, operation=alternate.operation,
                                       override={'AccountId': 'different synthetic account'}), context=alternate)
        self.assertFalse(result.metadata()['request_operation_device_and_account_fields_signed'])
        self.assertFalse(result.metadata()['challenge_freshness_or_replay_verified'])

    def test_original_signing_wrapper_handoff_matches_the_generated_crypto_proof(self):
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
        except ImportError:
            self.skipTest('Optional native verification dependencies unavailable')
        from tests import test_wii_shop_url as native_fixture
        from tools.verify_wii_shop_signing import verify_signing_wrapper
        source = native_fixture.NativeShopUrlTests.source(self)
        native = verify_signing_wrapper(source, b'<Challenge>a&b</Challenge>',
                                        signature=self.signature, signer_certificate=self.ap)
        response = self.inspect(document(self.ng, self.ap, self.signature, override={
            'Signature': native.signature_base64.decode('ascii'),
            'CertChain': native.certificate_base64.decode('ascii')}))
        self.assertTrue(response.metadata()['challenge_signature_verified'])
        self.assertFalse(response.metadata()['device_enrollment_or_account_authorized'])

    def test_missing_crypto_backend_is_an_explicit_failure_without_input_leak(self):
        with patch('jwc24.wii_shop_proof.subprocess.run', side_effect=OSError('private-marker')), \
                self.assertRaises(DeviceProofError) as caught:
            self.inspect()
        self.assertNotIn('private-marker', str(caught.exception))
