"""Offline serializer fixtures consumed by the original v21 response reader."""
import unittest

from jwc24.wii_shop_ec_config import (
    ECS_NS, URL_FIELDS, EvidencedURL, serialize_get_ec_config_response,
)
from tests import test_wii_shop_url as url_fixture
from tools.verify_wii_shop_ec_config import verify_ec_config_response


def fixture_urls():
    return {name: EvidencedURL('https://synthetic.invalid/'+name, 'synthetic:'+name)
            for name in URL_FIELDS}


class EcConfigInteropTests(unittest.TestCase):
    def verify(self, **changes):
        options = dict(urls=fixture_urls(), error_code='0',
                       status_source_ref='synthetic:configuration-status')
        options.update(changes)
        response = serialize_get_ec_config_response(**options)
        source = url_fixture.NativeShopUrlTests.source(self)
        return verify_ec_config_response(source, response)

    def test_serialized_configuration_passes_the_original_common_xml_reader(self):
        result = self.verify(timestamp='1234567890')
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['timestamp'], '1234567890')
        self.assertEqual(result['error_code'], '0')
        self.assertEqual(result['error_message'], '')
        expected = {name: value.value for name, value in fixture_urls().items()}
        self.assertEqual(result['urls'], expected)
        self.assertEqual(result['extracted_urls'], expected)
        self.assertTrue(result['namespace_comparison_equal'])
        self.assertEqual(result['native_url_setter_calls'], 2)
        self.assertTrue(result['object_and_heap_guards_verified'])
        self.assertTrue(result['native_write_ranges_checked'])
        self.assertFalse(result['native_url_setters_stubbed'])
        self.assertFalse(result['native_xml_lookup_helpers_stubbed'])
        self.assertFalse(result['browser_or_network_invoked'])

    def test_serialized_reported_error_is_not_configuration_success(self):
        result = self.verify(urls=None, error_code='42', error_message='Synthetic <&> error')
        self.assertNotEqual(result['status'], 0)
        self.assertEqual(result['error_code'], '42')
        self.assertEqual(result['error_message'], 'Synthetic <&> error')
        self.assertEqual(result['urls'], {})

    def test_retail_zero_code_keeps_message_without_treating_it_as_a_reported_error(self):
        result = self.verify(error_code='0', error_message='Synthetic <&> information')
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['error_code'], '0')
        self.assertEqual(result['error_message'], 'Synthetic <&> information')
        self.assertEqual(result['urls'], {name: value.value for name, value in fixture_urls().items()})

    def test_serializer_keeps_exact_ecs_namespace_despite_native_status_quirk(self):
        response = serialize_get_ec_config_response(
            urls=fixture_urls(), error_code='0', status_source_ref='synthetic:status')
        self.assertIn(b'<GetECConfigResponse xmlns="'+ECS_NS.encode()+b'">', response)
        response = response.replace(ECS_NS.encode(), b'urn:cas.wsapi.broadon.com')
        result = verify_ec_config_response(url_fixture.NativeShopUrlTests.source(self), response)
        # The native mismatch branch logs without setting a nonzero error; it
        # skips ErrorCode but can still install URLs. Zero status is insufficient
        # to establish a correctly parsed configuration response.
        self.assertEqual(result['common_status'], 0)
        self.assertFalse(result['namespace_comparison_equal'])
        self.assertEqual(result['error_code'], '')
        self.assertEqual(result['urls'], {name: value.value for name, value in fixture_urls().items()})

    def test_explicit_percent_encoded_uri_is_stored_unchanged(self):
        mapping = fixture_urls()
        mapping['EcsURL'] = EvidencedURL('https://synthetic.invalid/a%26b', 'synthetic:escaped-uri')
        result = self.verify(urls=mapping)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['urls']['EcsURL'], mapping['EcsURL'].value)

    def test_explicit_empty_error_message_allows_configuration_extraction(self):
        result = self.verify(error_message='')
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['urls'], {name: value.value for name, value in fixture_urls().items()})


if __name__ == '__main__':
    unittest.main()
