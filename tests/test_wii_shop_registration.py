"""Explicit offline registration fixtures and ECDK-mode state plans only."""
from dataclasses import replace
import unittest

from jwc24 import wii_shop_registration as reg


def registration(**changes):
    return replace(reg.EvidencedRegistration('synthetic-account', 'synthetic-token', 'ZZ',
        False, 'synthetic-ext', 'synthetic-code', 'synthetic:facts'), **changes)


def state(**changes):
    return replace(reg.RegistrationSyncState('old-account', 'old-token', 'old-ST', 'old-WT',
        'old-country', 'old-ext', 'old-code', False, False, 11, 22, 33, 44), **changes)


def response(**changes):
    args = dict(operation='SyncRegistration', registration=registration(), error_code='0',
                status_source_ref='synthetic:status')
    args.update(changes)
    return reg.serialize_registration_sync_response(**args)


def request(operation='SyncRegistration', extra=''):
    return (f'<s:Envelope xmlns:s="{reg.SOAP_NS}" xmlns:r="{reg.IAS_NS}" xmlns:i="{reg.XSI_NS}">'
        f'<s:Body><r:{operation} i:type="r:{operation}RequestType">'
        '<r:Version>2.0</r:Version><r:MessageId>synthetic-message</r:MessageId>'
        '<r:Region>SYN</r:Region><r:Country>ZZ</r:Country><r:Language>zz</r:Language>'
        '<r:DeviceCert>synthetic-cert</r:DeviceCert><r:Signature>synthetic-signature</r:Signature>'
        '<r:CertChain>synthetic-chain</r:CertChain><r:Challenge>synthetic</r:Challenge>'+extra+
        f'</r:{operation}></s:Body></s:Envelope>').encode()


class RegistrationTests(unittest.TestCase):
    def test_both_operation_names_and_proof_fields_stay_explicit_private(self):
        for operation in reg.OPERATIONS:
            parsed = reg.parse_registration_sync_request(request(operation),
                soap_action='"'+reg.IAS_NS+'/'+operation+'"')
            self.assertEqual(parsed.operation, operation)
            self.assertEqual(dict(parsed.proof_fields)['Signature'], 'synthetic-signature')
            self.assertNotIn('synthetic', repr(parsed))

    def test_request_operation_action_type_namespace_and_proof_isolation(self):
        for raw, action in ((request('Register'), reg.IAS_NS+'/Register'),
                (request(), reg.IAS_NS+'/GetRegistrationInfo'),
                (request().replace(b'r:SyncRegistrationRequestType', b'r:GetRegistrationInfoRequestType'), reg.IAS_NS+'/SyncRegistration'),
                (request().replace(reg.IAS_NS.encode(), b'urn:ecs.wsapi.broadon.com'), reg.IAS_NS+'/SyncRegistration'),
                (request().replace(b'<r:Signature>synthetic-signature</r:Signature>', b''), reg.IAS_NS+'/SyncRegistration'),
                (request(extra='<r:SerialNumber>x</r:SerialNumber>'), reg.IAS_NS+'/SyncRegistration'),
                (request(extra='<r:ApplicationId>x</r:ApplicationId>'), reg.IAS_NS+'/SyncRegistration'),
                (request(extra='<r:Signature>x</r:Signature>'), reg.IAS_NS+'/SyncRegistration')):
            with self.assertRaises(reg.RegistrationContractError):
                reg.parse_registration_sync_request(raw, soap_action=action)

    def test_signing_bytes_preserve_the_native_literal_fragment_separate_from_soap_escaping(self):
        raw = request().replace(b'<r:Challenge>synthetic</r:Challenge>', b'<r:Challenge>a&amp;b</r:Challenge>')
        parsed = reg.parse_registration_sync_request(raw, soap_action=reg.IAS_NS+'/SyncRegistration')
        self.assertEqual(reg.registration_sync_signing_bytes(parsed), b'<Challenge>a&b</Challenge>')
        for invalid in (None, replace(parsed, proof_fields=()), replace(parsed, operation='Register')):
            with self.assertRaises(reg.RegistrationContractError):
                reg.registration_sync_signing_bytes(invalid)

    def test_parser_limits_and_entities_do_not_echo_input(self):
        for raw in (b'', b'x'*65537, b'\xff', b'<!DOCTYPE x>'+request(),
                    request(extra='<r:AccountId>'+'x'*4097+'</r:AccountId>')):
            with self.assertRaises(reg.RegistrationContractError) as error:
                reg.parse_registration_sync_request(raw, soap_action=reg.IAS_NS+'/SyncRegistration')
            self.assertNotIn('synthetic', str(error.exception))

    def test_zero_status_needs_explicit_facts_and_nonzero_forbids_them(self):
        for changes in ({'registration': None}, {'error_code': '00'}, {'error_code': '4294967296'},
                        {'status_source_ref': ''}, {'operation': 'Register'}, {'error_code': '901'},
                        {'registration': registration(source_ref='')},
                        {'registration': registration(token_expired=1)}):
            with self.assertRaises(reg.RegistrationContractError):
                response(**changes)
        raw = response(registration=None, error_code='901')
        self.assertIn(b'<ErrorCode>901</ErrorCode>', raw)
        self.assertNotIn(b'<AccountId>', raw)
        self.assertNotIn('synthetic', repr(registration()))

    def test_optional_omission_empty_values_and_literal_identity_policy(self):
        raw = response(registration=registration(account_id='', device_token='', token_expired=None,
                                                ext_account_id=None, device_code=None))
        self.assertIn(b'<AccountId></AccountId>', raw)
        self.assertNotIn(b'DeviceTokenExpired', raw)
        self.assertNotIn(b'ExtAccountId', raw)
        for text in ('a&b', 'a<b', 'a>b', '\0', '\ud800', 'x'*4097):
            with self.assertRaises(reg.RegistrationContractError):
                response(registration=registration(device_token=text))

    def test_complete_ecdk_plan_updates_only_supplied_fields_and_derives_tokens(self):
        initial = state(need_ticket_sync=True, import_all=True)
        plan = reg.plan_ecdk_registration_sync(initial, registration=registration(),
            error_code='0', status_source_ref='synthetic:status')
        self.assertEqual(plan.state.account_id, 'synthetic-account')
        self.assertEqual(plan.state.strong_token, 'ST-synthetic-token')
        self.assertEqual(plan.state.weak_token, 'WT-874ae4f9a105bd7c66ef814ccf705702')
        self.assertEqual((plan.state.force_sync_time, plan.state.ext_ticket_time,
                          plan.state.sync_time, plan.state.last_ticket_sync_time), (11, 22, 33, 44))
        self.assertTrue(plan.state.need_ticket_sync)
        self.assertTrue(plan.state.import_all)
        self.assertTrue(plan.save_config_requested)
        self.assertFalse(plan.account_or_device_authorized)
        self.assertNotIn('synthetic', repr(plan))

    def test_expired_response_updates_snapshot_but_reports_registration_needed(self):
        plan = reg.plan_ecdk_registration_sync(state(), registration=registration(token_expired=True),
            error_code='0', status_source_ref='synthetic:status')
        self.assertEqual(plan.status, -4042)
        self.assertEqual(plan.state.account_id, 'synthetic-account')
        self.assertTrue(plan.save_config_requested)

    def test_901_clears_identity_and_sync_times_but_preserves_import_all(self):
        plan = reg.plan_ecdk_registration_sync(state(import_all=True), registration=None,
            error_code='901', status_source_ref='synthetic:status')
        self.assertTrue(plan.unregistered)
        self.assertEqual(plan.status, 0)
        self.assertEqual(plan.state.device_token, '')
        self.assertEqual(plan.state.strong_token, '')
        self.assertEqual(plan.state.weak_token, '')
        self.assertEqual((plan.state.force_sync_time, plan.state.ext_ticket_time,
                          plan.state.sync_time, plan.state.last_ticket_sync_time), (0, 0, 0, 0))
        self.assertTrue(plan.state.import_all)
        self.assertTrue(plan.state.need_ticket_sync)
        self.assertFalse(plan.account_or_device_authorized)

    def test_other_service_error_preserves_every_explicit_local_field(self):
        initial = state(strong_token='opaque-local-ST', weak_token='opaque-local-WT')
        plan = reg.plan_ecdk_registration_sync(initial, registration=None,
            error_code='42', status_source_ref='synthetic:status')
        self.assertEqual(plan.state, initial)
        self.assertEqual(plan.status, -4015)
        self.assertFalse(plan.save_config_requested)
        for bad in (None, state(import_all=1), state(sync_time=1 << 63)):
            with self.assertRaises(reg.RegistrationContractError):
                reg.plan_ecdk_registration_sync(bad, registration=None,
                    error_code='42', status_source_ref='synthetic:status')
