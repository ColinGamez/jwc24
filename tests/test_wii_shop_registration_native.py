"""Complete original registration sync consumer, synthetic proof and IO only."""
from dataclasses import replace
import hashlib
import unittest

from jwc24 import wii_shop_registration as reg
from tests import test_wii_shop_url as native_fixture
from tests.test_wii_shop_registration import registration, response
from tools.verify_wii_shop_registration_sync import (SyntheticRegistrationEnvironment,
    SyntheticRegistrationProof, verify_registration_sync)


def proof(**changes):
    return replace(SyntheticRegistrationProof('synthetic', 'synthetic-cert',
                   'synthetic-signature', 'synthetic-chain'), **changes)


def environment(**changes):
    return replace(SyntheticRegistrationEnvironment(account_id='old-account', token='old-token',
                   strong_token='old-ST', weak_token='old-WT'), **changes)


def snapshot(env):
    return reg.RegistrationSyncState(env.account_id, env.token, env.strong_token, env.weak_token,
        env.account_country, env.ext_account_id, env.account_device_code, env.need_ticket_sync,
        env.import_all, env.force_sync_time, env.ext_ticket_time, env.sync_time, env.last_ticket_sync_time)


class NativeRegistrationTests(unittest.TestCase):
    def source(self):
        return native_fixture.NativeShopUrlTests.source(self)

    def test_actual_worker_sync_entry_virtual_run_and_complete_consumer(self):
        result = verify_registration_sync(self.source(), response(), proof=proof(), environment=environment())
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['signed_payload_bytes'], b'<Challenge>synthetic</Challenge>')
        for field in ('native_worker_sync_caller_executed', 'native_sync_entry_executed',
                      'native_registration_run_executed', 'native_request_builder_executed',
                      'native_common_response_parser_executed', 'native_registration_reader_executed',
                      'native_account_assignment_executed', 'native_token_derivation_executed',
                      'native_md5_executed', 'object_heap_stack_and_write_bounds_verified'):
            self.assertTrue(result[field], field)
        for field in ('native_xml_helpers_stubbed', 'native_token_setter_and_md5_stubbed',
                      'signing_signature_check_or_persistence_executed', 'transport_executed',
                      'account_or_device_authorized', 'connected_flag', 'complete_connection_worker_executed'):
            self.assertFalse(result[field], field)

    def test_native_signed_request_uses_strong_token_and_exact_supplied_proof(self):
        env = environment(key_pair_confirmed=True, postal_code='synthetic-postal',
                          application_id='synthetic-app', tin='synthetic-tin')
        result = verify_registration_sync(self.source(), response(), proof=proof(), environment=env)
        parsed = reg.parse_registration_sync_request(result['request_bytes'], soap_action=reg.IAS_NS+'/SyncRegistration')
        self.assertEqual(dict(parsed.common_fields)['DeviceToken'], 'old-ST')
        self.assertEqual(parsed.postal_code, 'synthetic-postal')
        self.assertEqual(dict(parsed.proof_fields), {'DeviceCert': 'synthetic-cert',
            'Signature': 'synthetic-signature', 'CertChain': 'synthetic-chain', 'Challenge': 'synthetic'})
        for unsupported in ('ApplicationId', 'TIN', 'SerialNo', 'SerialNumber', 'Age', 'ECVersion'):
            self.assertNotIn(unsupported, dict(parsed.common_fields))
        self.assertIn((b'SOAPAction', (reg.IAS_NS+'/SyncRegistration').encode()), result['headers'])

    def test_ecdk_planner_matches_full_native_state_and_save_requests(self):
        source = self.source()
        cases = [(environment(), registration(), '0'),
            (environment(import_all=True, need_ticket_sync=True), registration(), '0'),
            (environment(), registration(token_expired=True), '0'),
            (environment(), registration(token_expired=None, ext_account_id=None, device_code=None), '0'),
            (environment(), registration(device_token='', account_id=''), '0'),
            (environment(import_all=True), None, '901'),
            (environment(), None, '42')]
        for initial, supplied, code in cases:
            with self.subTest(code=code, supplied=supplied):
                result = verify_registration_sync(source, response(registration=supplied, error_code=code),
                                                   proof=proof(), environment=initial)
                plan = reg.plan_ecdk_registration_sync(snapshot(initial), registration=supplied,
                    error_code=code, status_source_ref='synthetic:status')
                self.assertEqual(result['status'], plan.status)
                for key, attribute in (('account_id_bytes', 'account_id'), ('device_token_bytes', 'device_token'),
                        ('strong_token_bytes', 'strong_token'), ('weak_token_bytes', 'weak_token'),
                        ('account_country_bytes', 'country'), ('ext_account_id_bytes', 'ext_account_id'),
                        ('account_device_code_bytes', 'device_code')):
                    self.assertEqual(result[key], getattr(plan.state, attribute).encode(), key)
                self.assertEqual(result['sync_times'], [plan.state.force_sync_time, plan.state.ext_ticket_time,
                                                       plan.state.sync_time, plan.state.last_ticket_sync_time])
                self.assertEqual(result['need_ticket_sync'], plan.state.need_ticket_sync)
                self.assertEqual(result['import_all'], plan.state.import_all)
                self.assertEqual(result['unregistered'], plan.unregistered)
                self.assertEqual(result['save_config_calls'], int(plan.save_config_requested))
                self.assertEqual(result['remove_titles_calls'], 0)

    def test_unicode_raw_account_token_values_and_original_md5_match(self):
        token = 'synthetic-\u5408\u8a08'
        result = verify_registration_sync(self.source(), response(registration=registration(device_token=token)),
                                           proof=proof(), environment=environment())
        self.assertEqual(result['device_token_bytes'], token.encode())
        self.assertEqual(result['weak_token_bytes'], b'WT-'+hashlib.md5(token.encode()).hexdigest().encode())

    def test_explicit_empty_country_and_optional_fields_are_not_inferred(self):
        source = self.source()
        for optional in ('', None):
            supplied = registration(country='', ext_account_id=optional, device_code=optional)
            result = verify_registration_sync(source, response(registration=supplied),
                                               proof=proof(), environment=environment())
            self.assertEqual(result['status'], 0)
            self.assertEqual(result['account_country_bytes'], b'')
            self.assertEqual(result['ext_account_id_bytes'], b'')
            self.assertEqual(result['account_device_code_bytes'], b'')
            plan = reg.plan_ecdk_registration_sync(snapshot(environment()), registration=supplied,
                error_code='0', status_source_ref='synthetic:status')
            self.assertEqual((plan.state.country, plan.state.ext_account_id, plan.state.device_code), ('', '', ''))

    def test_partial_response_never_assigns_account_and_expiry_can_override_its_error(self):
        source = self.source()
        for expired, expected in ((False, -4006), (True, -4042)):
            raw = response(registration=registration(token_expired=expired)).replace(b'<Country>ZZ</Country>\n', b'')
            result = verify_registration_sync(source, raw, proof=proof(), environment=environment())
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['response_account_id_bytes'], b'synthetic-account')
            self.assertEqual(result['account_id_bytes'], b'old-account')
            self.assertEqual(result['device_token_bytes'], b'old-token')
            self.assertFalse(result['native_account_assignment_executed'])
            self.assertEqual(result['save_config_calls'], 0)

    def test_missing_required_account_and_token_stop_full_assignment(self):
        source = self.source()
        for tag, value in (('AccountId', 'synthetic-account'), ('DeviceToken', 'synthetic-token')):
            raw = response().replace(f'<{tag}>{value}</{tag}>\n'.encode(), b'')
            result = verify_registration_sync(source, raw, proof=proof(), environment=environment())
            self.assertEqual(result['status'], -4006)
            self.assertEqual(result['account_id_bytes'], b'old-account')
            self.assertEqual(result['save_config_calls'], 0)

    def test_expiry_boolean_reader_accepts_only_original_forms(self):
        source = self.source()
        for literal, status in (('true', -4042), ('1', -4042), ('false', 0), ('0', 0),
                                ('TRUE', -4034), ('False', -4034), ('', -4034)):
            raw = response().replace(b'<DeviceTokenExpired>false</DeviceTokenExpired>',
                                     f'<DeviceTokenExpired>{literal}</DeviceTokenExpired>'.encode())
            result = verify_registration_sync(source, raw, proof=proof(), environment=environment())
            self.assertEqual(result['status'], status)

    def test_signing_transport_and_empty_challenge_errors_do_not_assign(self):
        source = self.source()
        for changes, expected in (({'sign_status': -4004}, -4004), ({'sign_status': -77}, -4001),
                                  ({'transport_status': -4007}, -4007), ({'proof': proof(challenge='')}, -4004)):
            result = verify_registration_sync(source, response(), environment=environment(),
                                               **({'proof': proof()} | changes))
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['account_id_bytes'], b'old-account')
            self.assertEqual(result['save_config_calls'], 0)
            if 'transport_status' not in changes:
                self.assertIsNone(result['request_bytes'])

    def test_legacy_get_registration_info_is_distinct_and_cleanup_only_a_stub(self):
        source = self.source()
        initial = environment(use_ecdk_sync_registration=False)
        result = verify_registration_sync(source, response(operation='GetRegistrationInfo'),
                                           proof=proof(), environment=initial)
        parsed = reg.parse_registration_sync_request(result['request_bytes'], soap_action=reg.IAS_NS+'/GetRegistrationInfo')
        self.assertEqual(parsed.operation, 'GetRegistrationInfo')
        self.assertTrue(result['need_ticket_sync'])
        self.assertTrue(result['import_all'])
        self.assertEqual(result['shop_log_actions'], [1])
        result = verify_registration_sync(source, response(operation='GetRegistrationInfo', registration=None,
                                                           error_code='901'), proof=proof(), environment=initial)
        self.assertTrue(result['unregistered'])
        self.assertEqual(result['remove_titles_calls'], 1)
        self.assertEqual(result['status'], 0)
        self.assertFalse(result['signing_signature_check_or_persistence_executed'])

    def test_save_failure_does_not_establish_durable_registration(self):
        result = verify_registration_sync(self.source(), response(), proof=proof(),
                                           environment=environment(), save_status=-999)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['save_config_calls'], 1)
        self.assertFalse(result['connected_flag'])

    def test_signing_bytes_stay_literal_while_soap_proof_is_escaped(self):
        result = verify_registration_sync(self.source(), response(), proof=proof(challenge='a&b'),
                                           environment=environment())
        self.assertEqual(result['signed_payload_bytes'], b'<Challenge>a&b</Challenge>')
        self.assertIn(b'<ias:Challenge>a&amp;b</ias:Challenge>', result['request_bytes'])
        parsed = reg.parse_registration_sync_request(result['request_bytes'], soap_action=reg.IAS_NS+'/SyncRegistration')
        self.assertEqual(reg.registration_sync_signing_bytes(parsed), result['signed_payload_bytes'])

    def test_pinned_source_and_synthetic_input_limits(self):
        source = self.source()
        for data in (b'wrong', bytearray(source)):
            with self.assertRaises(ValueError):
                verify_registration_sync(data, response(), proof=proof())
        for raw in (b'', b'x'*16385, b'a\0'):
            with self.assertRaises(ValueError):
                verify_registration_sync(source, raw, proof=proof())
        for changes in ({'proof': proof(challenge='x'*97)}, {'proof': object()},
                        {'environment': environment(import_all=1)}, {'sign_status': True},
                        {'environment': environment(token='\ud800')}):
            with self.assertRaises(ValueError):
                verify_registration_sync(source, response(), **({'proof': proof()} | changes))
