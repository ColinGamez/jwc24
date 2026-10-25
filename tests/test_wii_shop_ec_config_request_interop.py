"""Original retail request construction consumed by the offline ECS parser."""
from pathlib import Path
import os
import unittest

from jwc24.wii_shop_ec_config import EcConfigContractError, parse_get_ec_config_request
from tools.verify_wii_shop_ec_config_request import (
    SyntheticRequestEnvironment, verify_ec_config_request,
)


class NativeRequestInteropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        appdata = os.environ.get('APPDATA')
        path = (Path(appdata)/'Dolphin Emulator/Wii/title/00010002/48414241/content/0000005e.app'
                if appdata else Path('private/wii_shop/main.dol'))
        cls.source = path.read_bytes() if path.is_file() else None

    def build(self, environment=None, product_version='synthetic-product'):
        if self.source is None:
            self.skipTest('Private original v21 executable unavailable')
        return verify_ec_config_request(self.source, environment=environment, product_version=product_version)

    def parse(self, built):
        return parse_get_ec_config_request(built['request_bytes'], soap_action=built['soap_action'])

    def test_default_retail_constructor_and_headers_match_the_parser_contract(self):
        built = self.build()
        parsed = self.parse(built)
        fields = dict(parsed.common_fields)
        self.assertEqual(fields['Version'], '2.0')
        self.assertEqual(fields['SerialNo'], 'synthetic-serial')
        self.assertEqual(parsed.ec_version, 'synthetic-product')
        self.assertIsNone(parsed.postal_code)
        self.assertNotIn('DeviceId', fields)
        headers = {name.lower(): value for name, value in built['headers']}
        self.assertEqual(headers['soapaction'], built['soap_action'])
        self.assertEqual(headers['accept'], 'application/xml')
        self.assertTrue(built['native_constructor_executed'])
        self.assertFalse(built['native_xml_builder_stubbed'])
        self.assertTrue(built['object_heap_and_write_bounds_verified'])
        self.assertFalse(built['transport_executed'])
        self.assertFalse(built['account_or_key_pair_verified'])

    def test_optional_native_postal_pair_is_retained_without_becoming_identity(self):
        env = SyntheticRequestEnvironment(postal_code='synthetic-private-postal')
        parsed = self.parse(self.build(env))
        self.assertEqual(parsed.postal_code, env.postal_code)
        self.assertNotIn(env.postal_code, repr(parsed))
        self.assertNotIn('Attributes', dict(parsed.common_fields))

    def test_native_optional_fields_remain_opaque_and_private(self):
        env = SyntheticRequestEnvironment(
            account_id='synthetic-private-account', token='synthetic-trigger',
            weak_token='synthetic-private-weak', strong_token='synthetic-unused-strong',
            application_id='synthetic-app', tin='synthetic-private-tin', key_pair_confirmed=True)
        parsed = self.parse(self.build(env))
        fields = dict(parsed.common_fields)
        self.assertEqual(fields['DeviceId'], env.device_id)
        self.assertEqual(fields['AccountId'], env.account_id)
        self.assertEqual(fields['ApplicationId'], env.application_id)
        self.assertEqual(fields['TIN'], env.tin)
        self.assertTrue(fields['DeviceToken'])
        for value in fields.values():
            if value.startswith('synthetic-'):
                self.assertNotIn(value, repr(parsed))

    def test_native_ec_version_escaping_round_trips(self):
        product = 'synthetic & <product>'
        built = self.build(product_version=product)
        self.assertIn(b'synthetic &amp; &lt;product&gt;', built['request_bytes'])
        self.assertEqual(self.parse(built).ec_version, product)

    def test_raw_common_stream_text_does_not_make_malformed_xml_acceptable(self):
        built = self.build(SyntheticRequestEnvironment(region='synthetic&broken'))
        with self.assertRaises(EcConfigContractError) as raised:
            self.parse(built)
        self.assertNotIn('synthetic&broken', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
