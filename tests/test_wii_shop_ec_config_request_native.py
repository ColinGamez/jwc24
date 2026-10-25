"""Native v21 request construction with synthetic values; no real identities."""
from dataclasses import replace
import os
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

from tools.verify_wii_shop_ec_config_request import (
    SyntheticRequestEnvironment, verify_ec_config_request,
)

ECS = 'urn:ecs.wsapi.broadon.com'


class NativeECConfigRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get('APPDATA')
        path = Path(root) / 'Dolphin Emulator/Wii/title/00010002/48414241/content/0000005e.app' if root else Path('private/wii_shop/main.dol')
        cls.source = path.read_bytes() if path.is_file() else None

    def verify(self, environment=None, **options):
        if self.source is None:
            self.skipTest('Private original v21 executable unavailable')
        return verify_ec_config_request(self.source, environment=environment, **options)

    def operation(self, result):
        return ET.fromstring(result['request_bytes'])[0][0]

    def pairs(self, result):
        return [(node.tag.split('}')[1], node.text or '') for node in self.operation(result)]

    def test_original_constructor_version_namespace_type_and_headers(self):
        result = self.verify(product_version='synthetic-opaque-product')
        op = self.operation(result)
        self.assertEqual(op.tag, '{' + ECS + '}GetECConfig')
        self.assertEqual(op.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'], 'ecs:GetECConfigRequestType')
        self.assertEqual(result['native_default_version'], '2.0')
        self.assertTrue(result['native_constructor_executed'])
        self.assertFalse(result['native_xml_builder_stubbed'])
        self.assertEqual(result['soap_action'], ECS + '/GetECConfig')
        self.assertEqual(result['headers'], [('Accept', 'application/xml'), ('Accept-Charset', 'UTF-8'),
                         ('Content-type', 'text/xml; charset=utf-8'), ('SOAPAction', ECS + '/GetECConfig')])
        self.assertEqual(result['header_text'], 'SOAPAction: "' + ECS + '/GetECConfig"\r\n')
        self.assertEqual([name for name, _ in self.pairs(result)],
                         ['Version', 'MessageId', 'Region', 'Country', 'Language', 'SerialNo', 'ECVersion'])
        self.assertEqual(dict(self.pairs(result))['ECVersion'], 'synthetic-opaque-product')
        self.assertTrue(result['object_heap_and_write_bounds_verified'])
        self.assertFalse(result['transport_executed'])

    def test_native_message_id_uses_substituted_prefix_device_and_tick(self):
        result = self.verify(SyntheticRequestEnvironment(device_id='synthetic-specific-device'))
        self.assertEqual(dict(self.pairs(result))['MessageId'],
                         'synthetic-prefix-synthetic-specific-device-123')
        self.assertNotIn('DeviceId', dict(self.pairs(result)))

    def test_nonempty_postal_is_original_single_name_value_attribute_before_serial(self):
        result = self.verify(SyntheticRequestEnvironment(postal_code='synthetic-postal'))
        nodes = list(self.operation(result))
        names = [n.tag.split('}')[1] for n in nodes]
        self.assertEqual(names, ['Version', 'MessageId', 'Region', 'Country', 'Language', 'Attributes', 'SerialNo', 'ECVersion'])
        attribute = nodes[names.index('Attributes')]
        self.assertEqual([(n.tag, n.text) for n in attribute],
                         [('{'+ECS+'}Name', 'PostalCode'), ('{'+ECS+'}Value', 'synthetic-postal')])

    def test_optional_fields_appear_in_native_order_and_weak_prefixed_slot_is_used(self):
        env = SyntheticRequestEnvironment(key_pair_confirmed=True, account_id='synthetic-account',
                token='synthetic-token-trigger', weak_token='synthetic-weak-prefixed',
                strong_token='synthetic-strong-prefixed', application_id='synthetic-app', tin='synthetic-tin')
        result = self.verify(env)
        pairs = self.pairs(result)
        self.assertEqual([name for name, _ in pairs], ['Version','MessageId','DeviceId','DeviceToken',
                         'AccountId','ApplicationId','TIN','Region','Country','Language','SerialNo','ECVersion'])
        self.assertEqual(dict(pairs)['DeviceToken'], 'synthetic-weak-prefixed')
        self.assertNotIn(b'synthetic-strong-prefixed', result['request_bytes'])
        self.assertFalse(result['account_or_key_pair_verified'])

    def test_empty_token_trigger_omits_even_nonempty_prefixed_slots(self):
        result = self.verify(SyntheticRequestEnvironment(weak_token='synthetic-weak-prefixed'))
        self.assertNotIn('DeviceToken', dict(self.pairs(result)))

    def test_common_empty_values_are_still_emitted_and_no_age_added_to_ecs(self):
        env = SyntheticRequestEnvironment(serial_no='', region='', country='', language='')
        pairs = dict(self.pairs(self.verify(env, product_version='')))
        for name in ('SerialNo', 'Region', 'Country', 'Language', 'ECVersion'):
            self.assertIn(name, pairs)
            self.assertEqual(pairs[name], '')
        self.assertNotIn('Age', pairs)

    def test_product_version_uses_original_element_escape_helper(self):
        result = self.verify(product_version='synthetic & <product>')
        self.assertIn(b'synthetic &amp; &lt;product&gt;', result['request_bytes'])
        self.assertEqual(dict(self.pairs(result))['ECVersion'], 'synthetic & <product>')

    def test_common_values_are_original_stream_insertions_not_xml_escaped(self):
        result = self.verify(SyntheticRequestEnvironment(postal_code='synthetic & postal'))
        self.assertIn(b'<ecs:Value>synthetic & postal</ecs:Value>', result['request_bytes'])
        with self.assertRaises(ET.ParseError):
            self.operation(result)

    def test_environment_repr_excludes_identity_values(self):
        value = SyntheticRequestEnvironment(device_id='synthetic-private-device',postal_code='synthetic-private-postal')
        self.assertNotIn('synthetic-private', repr(value))

    def test_fingerprint_and_input_bounds_reject_before_execution(self):
        for invalid in (b'wrong-program', '', b'', b'x' * (4 * 1024 * 1024 + 1)):
            with self.subTest(type=type(invalid)), self.assertRaises(ValueError):
                verify_ec_config_request(invalid)
        if self.source is None:
            self.skipTest('Private original v21 executable unavailable')
        for value in ('x' * 97, 'synthetic\0', '\ud800'):
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                self.verify(product_version=value)
        with self.assertRaises(ValueError):
            self.verify(replace(SyntheticRequestEnvironment(), key_pair_confirmed=1))


if __name__ == '__main__':
    unittest.main()
