"""Original complete CheckDeviceStatus consumer and virtual dispatch, synthetic IO."""
from dataclasses import replace
import unittest

from tests import test_wii_shop_url as native_fixture
from tests.test_wii_shop_device_status import snapshot, facts, response
from jwc24 import wii_shop_device_status as ds
from tools.verify_wii_shop_device_status import verify_device_status, SyntheticRequestEnvironment


class NativeDeviceStatusTests(unittest.TestCase):
    def source(self):
        return native_fixture.NativeShopUrlTests.source(self)

    def test_complete_original_consumer_and_both_worker_dispatches(self):
        source = self.source()
        for dispatch in ('before_registration', 'after_registration'):
            result = verify_device_status(source, response(), state=snapshot(), worker_dispatch=dispatch)
            self.assertEqual(result['status'], 0)
            parsed = ds.parse_check_device_status_request(result['request_bytes'],
                                                         soap_action=ds.CHECK_DEVICE_STATUS_ACTION)
            self.assertEqual(dict(parsed.common_fields)['SerialNo'], 'synthetic-serial')
            self.assertIn((b'SOAPAction', ds.CHECK_DEVICE_STATUS_ACTION.encode()), result['headers'])
            for field in ('native_request_builder_executed', 'native_common_response_parser_executed',
                          'native_response_reader_executed', 'native_sync_decision_executed',
                          'native_worker_virtual_dispatch_executed', 'object_heap_stack_and_write_bounds_verified'):
                self.assertTrue(result[field], field)
            for field in ('native_xml_helpers_stubbed', 'transport_executed', 'connected_flag',
                          'complete_connection_worker_executed', 'persistence_or_shop_log_executed',
                          'account_or_device_authorized'):
                self.assertFalse(result[field], field)

    def test_native_common_identity_application_and_postal_contract(self):
        result = verify_device_status(self.source(), response(), state=snapshot(),
            environment=SyntheticRequestEnvironment(key_pair_confirmed=True, token='synthetic-trigger',
                weak_token='weak:synthetic', account_id='synthetic-account', application_id='synthetic-app',
                tin='synthetic-tin', postal_code='synthetic-postal'))
        parsed = ds.parse_check_device_status_request(result['request_bytes'], soap_action=ds.CHECK_DEVICE_STATUS_ACTION)
        common = dict(parsed.common_fields)
        self.assertEqual(common['DeviceToken'], 'weak:synthetic')
        self.assertEqual(common['ApplicationId'], 'synthetic-app')
        self.assertEqual(common['TIN'], 'synthetic-tin')
        self.assertEqual(parsed.postal_code, 'synthetic-postal')
        self.assertNotIn('Age', common)
        self.assertNotIn('ECVersion', common)

    def test_pure_plan_matches_complete_native_state_and_side_effect_requests(self):
        source = self.source()
        cases = [(snapshot(), facts()),
                 (snapshot(), facts(force_sync_time=44)),
                 (snapshot(), facts(ext_ticket_time=44)),
                 (snapshot(), facts(sync_time=44)),
                 (snapshot(need_ticket_sync=True), facts(force_sync_time=44)),
                 (snapshot(need_ticket_sync=True, import_all=True), facts()),
                 (snapshot(ecdk=True), facts()),
                 (snapshot(ecdk=True), facts(sync_time=44)),
                 (snapshot(import_all=True), facts(ext_ticket_time=44))]
        for initial, supplied in cases:
            with self.subTest(initial=initial, supplied=supplied):
                actual = verify_device_status(source, response(supplied), state=initial)
                plan = ds.plan_device_status_update(initial, supplied)
                self.assertEqual(actual['status'], 0)
                for key in ('points_balance', 'points_cached', 'need_ticket_sync', 'import_all', 'checked', 'times_match'):
                    self.assertEqual(actual[key], getattr(plan.state, key), key)
                self.assertEqual(actual['local_sync_times'],
                                 [initial.force_sync_time, initial.ext_ticket_time, initial.sync_time])
                self.assertEqual(actual['response_sync_times'],
                                 [supplied.force_sync_time, supplied.ext_ticket_time, supplied.sync_time])
                for key, flag in (('save_config_calls', plan.save_config_requested),
                                  ('shop_log_calls', plan.make_shop_log_requested),
                                  ('clear_sync_needed_calls', plan.clear_sync_needed_requested)):
                    self.assertEqual(actual[key], int(flag), key)

    def test_original_signed_numeric_conversion_matches_explicit_limits(self):
        supplied = facts(points_balance=-(1 << 31), force_sync_time=-(1 << 63),
                         ext_ticket_time=(1 << 63)-1, sync_time=0)
        result = verify_device_status(self.source(), response(supplied), state=snapshot())
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['points_balance'], supplied.points_balance)
        self.assertEqual(result['response_sync_times'], [supplied.force_sync_time, supplied.ext_ticket_time, 0])

    def test_reported_error_and_transport_failure_leave_snapshot_untouched(self):
        source = self.source()
        for raw, transport, expected in ((response(facts=None, error_code='42'), 0, -4015),
                                         (response(), -4007, -4007)):
            result = verify_device_status(source, raw, state=snapshot(), transport_status=transport)
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['points_balance'], 17)
            self.assertFalse(result['points_cached'])
            self.assertFalse(result['checked'])
            self.assertFalse(result['native_response_reader_executed'])
            self.assertFalse(result['native_sync_decision_executed'])
            self.assertEqual(result['save_config_calls'], 0)

    def test_missing_late_fields_cache_points_before_failure_but_not_sync(self):
        source = self.source()
        for field, value in (('ForceSyncTime', '1'), ('ExtTicketTime', '2'), ('SyncTime', '3')):
            raw = response().replace(f'<{field}>{value}</{field}>\n'.encode(), b'')
            result = verify_device_status(source, raw, state=snapshot())
            self.assertEqual(result['status'], -4006)
            self.assertEqual(result['points_balance'], 123)
            self.assertTrue(result['points_cached'])
            self.assertFalse(result['checked'])
            self.assertEqual(result['response_sync_times'], [-777]*3)
            self.assertFalse(result['native_sync_decision_executed'])

    def test_bad_currency_missing_balance_and_missing_amount_do_not_cache(self):
        source = self.source()
        for raw, expected in ((response().replace(b'POINTS', b'JPY'), -4034),
                              (response().replace(b'<Amount>123</Amount>\n', b''), -4006),
                              (response().replace(b'<Balance>\n<Amount>123</Amount>\n<Currency>POINTS</Currency>\n</Balance>\n', b''), -4006)):
            result = verify_device_status(source, raw, state=snapshot())
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['points_balance'], 17)
            self.assertFalse(result['points_cached'])
            self.assertFalse(result['checked'])

    def test_save_failure_is_not_propagated_by_original_run(self):
        result = verify_device_status(self.source(), response(facts(sync_time=44)),
                                      state=snapshot(), save_status=-999)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['save_config_calls'], 1)
        self.assertTrue(result['checked'])
        self.assertFalse(result['connected_flag'])

    def test_noncanonical_numeric_native_leniency_is_not_serializer_policy(self):
        raw = response().replace(b'<Amount>123</Amount>', b'<Amount>123junk</Amount>')
        result = verify_device_status(self.source(), raw, state=snapshot())
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['points_balance'], 123)
        with self.assertRaises(ds.DeviceStatusContractError):
            response(facts(points_balance='123junk'))

    def test_guards_run_before_emulation(self):
        source = self.source()
        for invalid in (b'not-original', bytearray(source)):
            with self.assertRaises(ValueError):
                verify_device_status(invalid, response(), state=snapshot())
        for raw in (b'', b'x'*16385, b'x\0'):
            with self.assertRaises(ValueError):
                verify_device_status(source, raw, state=snapshot())
        for changes in ({'worker_dispatch': 'invented'}, {'save_status': True},
                        {'environment': SyntheticRequestEnvironment(region='\ud800')}):
            with self.assertRaises(ValueError):
                verify_device_status(source, response(), state=snapshot(), **changes)
