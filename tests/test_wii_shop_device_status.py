"""Offline ECS facts/planning tests; no device or provider access."""
from dataclasses import replace
import unittest

from jwc24 import wii_shop_device_status as ds


def snapshot(**changes):
    return replace(ds.LocalSyncState(17, 1, 2, 3, False, False, False,
                                    False, False, False), **changes)


def facts(**changes):
    return replace(ds.EvidencedDeviceStatus(123, 1, 2, 3, 'synthetic:facts'), **changes)


def response(value=None, **changes):
    args = dict(facts=facts() if value is None else value, error_code='0',
                status_source_ref='synthetic:status')
    args.update(changes)
    return ds.serialize_check_device_status_response(**args)


def request(extra='', *, operation='CheckDeviceStatus'):
    return (f'<s:Envelope xmlns:s="{ds.SOAP_NS}" xmlns:e="{ds.ECS_NS}" '
            f'xmlns:i="{ds.XSI_NS}"><s:Body><e:{operation} '
            f'i:type="e:{operation}RequestType"><e:Version>2.0</e:Version>'
            '<e:MessageId>synthetic-message</e:MessageId><e:Region>SYN</e:Region>'
            '<e:Country>ZZ</e:Country><e:Language>zz</e:Language>'
            '<e:SerialNo>synthetic-serial</e:SerialNo>'+extra+
            f'</e:{operation}></s:Body></s:Envelope>').encode()


class DeviceStatusTests(unittest.TestCase):
    def test_request_optional_identity_is_opaque_and_repr_private(self):
        data = request('<e:AccountId>synthetic-private</e:AccountId>'
                       '<e:Attributes><e:Name>PostalCode</e:Name>'
                       '<e:Value>synthetic-postal</e:Value></e:Attributes>')
        parsed = ds.parse_check_device_status_request(data, soap_action='"'+ds.CHECK_DEVICE_STATUS_ACTION+'"')
        self.assertEqual(dict(parsed.common_fields)['AccountId'], 'synthetic-private')
        self.assertEqual(parsed.postal_code, 'synthetic-postal')
        self.assertNotIn('synthetic', repr(parsed))

    def test_request_wrong_action_operation_type_namespace_and_fields_reject(self):
        candidates = [request(operation='GetECConfig'), request('<e:ECVersion>x</e:ECVersion>'),
            request('<e:Age>18</e:Age>'), request('<e:Version>2.0</e:Version>'),
            request().replace(b'urn:ecs.wsapi.broadon.com', b'urn:ias.wsapi.broadon.com'),
            request().replace(b'e:CheckDeviceStatusRequestType', b'e:GetECConfigRequestType'),
            request().replace(b'<e:SerialNo>synthetic-serial</e:SerialNo>', b''),
            request('<e:Attributes><e:Name>Other</e:Name><e:Value>x</e:Value></e:Attributes>')]
        for data in candidates:
            with self.subTest(data=data), self.assertRaises(ds.DeviceStatusContractError):
                ds.parse_check_device_status_request(data, soap_action=ds.CHECK_DEVICE_STATUS_ACTION)
        with self.assertRaises(ds.DeviceStatusContractError):
            ds.parse_check_device_status_request(request(), soap_action=ds.ECS_NS+'/GetECConfig')

    def test_request_hostile_xml_and_local_bounds(self):
        for data in (b'', b'x'*65537, b'\xff', b'<!DOCTYPE x>'+request(),
                     request('<e:AccountId>'+'x'*4097+'</e:AccountId>'),
                     request('<e:AccountId><e:A><e:B>x</e:B></e:A></e:AccountId>')):
            with self.assertRaises(ds.DeviceStatusContractError):
                ds.parse_check_device_status_request(data, soap_action=ds.CHECK_DEVICE_STATUS_ACTION)

    def test_explicit_response_status_and_facts_have_no_defaults_or_value_repr(self):
        raw = response()
        self.assertIn(b'<Balance>\n<Amount>123</Amount>\n<Currency>POINTS</Currency>', raw)
        self.assertNotIn(b'synthetic:facts', raw)
        self.assertNotIn('123', repr(facts()))
        for changes in ({'facts': None}, {'error_code': '00'}, {'status_source_ref': ''},
                        {'facts': facts(source_ref='')}, {'facts': facts(points_balance=True)},
                        {'facts': facts(points_balance=1 << 31)},
                        {'facts': facts(sync_time=1 << 63)}, {'error_code': '42'}):
            with self.assertRaises(ds.DeviceStatusContractError):
                response(**changes)
        raw = response(facts=None, error_code='42', error_message='synthetic & error')
        self.assertNotIn(b'<Balance>', raw)
        self.assertIn(b'synthetic &amp; error', raw)

    def test_complete_success_plan_preserves_local_times_and_pending_flags(self):
        for initial in (snapshot(), snapshot(need_ticket_sync=True, import_all=True),
                        snapshot(ecdk=True)):
            plan = ds.plan_device_status_update(initial, facts())
            self.assertTrue(plan.state.times_match)
            self.assertTrue(plan.state.checked)
            self.assertTrue(plan.state.points_cached)
            self.assertEqual(plan.state.points_balance, 123)
            self.assertEqual(plan.state.need_ticket_sync, initial.need_ticket_sync)
            self.assertEqual(plan.state.import_all, initial.import_all)
            self.assertFalse(plan.save_config_requested)
            self.assertEqual(plan.clear_sync_needed_requested, not initial.ecdk and not initial.need_ticket_sync)
            self.assertFalse(plan.account_or_device_authorized)

    def test_mismatch_plan_only_requests_save_on_transition_to_pending_sync(self):
        for field in ('force_sync_time', 'ext_ticket_time', 'sync_time'):
            for pending in (False, True):
                initial = snapshot(need_ticket_sync=pending)
                plan = ds.plan_device_status_update(initial, facts(**{field: 44}))
                self.assertFalse(plan.state.times_match)
                self.assertTrue(plan.state.need_ticket_sync)
                self.assertEqual(plan.save_config_requested, not pending)
                self.assertEqual(plan.state.import_all, field == 'force_sync_time')
                self.assertEqual((plan.state.force_sync_time, plan.state.ext_ticket_time,
                                  plan.state.sync_time), (1, 2, 3))
                self.assertFalse(plan.clear_sync_needed_requested)

    def test_state_validation_and_signed_facts_are_explicit(self):
        for initial in (None, snapshot(checked=1), snapshot(sync_time=1 << 63)):
            with self.assertRaises(ds.DeviceStatusContractError):
                ds.plan_device_status_update(initial, facts())
        raw = response(facts(points_balance=-(1 << 31), force_sync_time=-(1 << 63),
                             ext_ticket_time=(1 << 63)-1))
        self.assertIn(b'<Amount>-2147483648</Amount>', raw)
