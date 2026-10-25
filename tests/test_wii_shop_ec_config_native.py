"""Run fingerprinted original v21 parser on synthetic data; no real responses."""
import os
from pathlib import Path
import unittest

from tools.verify_wii_shop_ec_config import FIELDS, MAX_RESPONSE, verify_ec_config_response


def fixture(*, code='0', message=None, timestamp=None, omit=(), order=FIELDS,
            namespace='urn:ecs.wsapi.broadon.com', values=None):
    body = ''
    if timestamp is not None:
        body += '<TimeStamp>' + timestamp + '</TimeStamp>'
    body += '<ErrorCode>' + code + '</ErrorCode>'
    if message is not None:
        body += '<ErrorMessage>' + message + '</ErrorMessage>'
    values = values or {}
    for name in order:
        if name not in omit:
            body += '<' + name + '>' + values.get(name, 'https://synthetic.invalid/' + name) + '</' + name + '>'
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soapenv:Body><GetECConfigResponse xmlns="' + namespace + '">' + body +
            '</GetECConfigResponse></soapenv:Body></soapenv:Envelope>').encode('utf-8')


class NativeECConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = os.environ.get('APPDATA')
        path = Path(root) / 'Dolphin Emulator/Wii/title/00010002/48414241/content/0000005e.app' if root else Path('private/wii_shop/main.dol')
        cls.source = path.read_bytes() if path.is_file() else None

    def verify(self, response):
        if self.source is None:
            self.skipTest('Private original v21 executable unavailable')
        return verify_ec_config_response(self.source, response)

    def test_native_common_parser_and_all_five_unstubbed_url_stores(self):
        result = self.verify(fixture(timestamp='1234567890'))
        self.assertEqual((result['common_status'], result['status']), (0, 0))
        self.assertEqual(result['timestamp'], '1234567890')
        self.assertEqual(result['server_timestamp'], '1234567890')
        self.assertEqual(result['native_url_setter_calls'], 2)
        self.assertEqual(result['field_attempts'], list(FIELDS))
        self.assertEqual(result['urls'], {f: 'https://synthetic.invalid/' + f for f in FIELDS})
        self.assertEqual(result['extracted_urls'], result['urls'])
        self.assertFalse(result['native_xml_lookup_helpers_stubbed'])
        self.assertFalse(result['native_url_setters_stubbed'])
        self.assertTrue(result['object_and_heap_guards_verified'])
        self.assertTrue(result['native_write_ranges_checked'])

    def test_nonzero_error_and_entity_decoding_skip_all_url_extraction(self):
        result = self.verify(fixture(code='42', message='Synthetic &amp; &lt;error&gt;'))
        self.assertEqual(result['status'], -4015)
        self.assertEqual(result['error_code'], '42')
        self.assertEqual(result['error_message'], 'Synthetic & <error>')
        self.assertTrue(result['native_error_setter_executed'])
        self.assertEqual(result['reported_error_record_code'], 42)
        self.assertEqual(result['field_attempts'], [])
        self.assertEqual(result['urls'], {})

    def test_zero_code_nonempty_message_is_informational_in_retail(self):
        result = self.verify(fixture(message='Synthetic &amp; information'))
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['error_message'], 'Synthetic & information')
        self.assertEqual(len(result['urls']), 5)
        self.assertFalse(result['native_error_setter_executed'])

    def test_zero_message_without_urls_passes_common_then_missing_field(self):
        result = self.verify(fixture(message='Synthetic information', omit=FIELDS))
        self.assertEqual((result['common_status'], result['status']), (0, -4006))
        self.assertEqual(result['field_attempts'], ['ContentPrefixURL'])
        self.assertEqual(result['urls'], {})

    def test_noncanonical_zero_error_codes_are_not_numeric_zero(self):
        for code in ('00', '000'):
            with self.subTest(code=code):
                result = self.verify(fixture(code=code))
                self.assertEqual(result['status'], -4015)
                self.assertEqual(result['error_code'], code)
                self.assertEqual(result['urls'], {})

    def test_namespace_mismatch_leaves_zero_but_skips_status_fields(self):
        result = self.verify(fixture(code='42', namespace='urn:cas.wsapi.broadon.com'))
        self.assertFalse(result['namespace_comparison_equal'])
        self.assertEqual(result['common_status'], 0)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['error_code'], '')
        self.assertEqual(result['common_simple_fields'], [])
        self.assertEqual(len(result['urls']), 5)

    def test_different_soap_prefix_and_absent_declaration_fail(self):
        for data in (fixture().replace(b'soapenv:', b'SOAP-ENV:'),
                     fixture().split(b'?>', 1)[1]):
            with self.subTest(size=len(data)):
                result = self.verify(data)
                self.assertEqual(result['status'], -4034)
                self.assertEqual(result['urls'], {})

    def test_missing_required_error_code_fails_common(self):
        result = self.verify(fixture().replace(b'<ErrorCode>0</ErrorCode>', b''))
        self.assertEqual(result['common_status'], -4034)
        self.assertEqual(result['field_attempts'], [])

    def test_response_version_is_not_a_native_validation_field(self):
        data = fixture().replace(b'<ErrorCode>', b'<Version>synthetic-999</Version><ErrorCode>')
        result = self.verify(data)
        self.assertEqual(result['status'], 0)
        self.assertNotIn('Version', result['common_simple_fields'])
        self.assertFalse(result['request_builder_executed'])

    def test_missing_each_field_exposes_partial_locals_without_installation(self):
        for index, name in enumerate(FIELDS):
            with self.subTest(name=name):
                result = self.verify(fixture(omit=(name,)))
                self.assertEqual((result['common_status'], result['status']), (0, -4006))
                self.assertEqual(result['field_attempts'], list(FIELDS[:index + 1]))
                self.assertEqual(result['native_url_setter_calls'], 0)
                self.assertEqual(result['urls'], {})
                for previous in FIELDS[:index]:
                    self.assertEqual(result['extracted_urls'][previous], 'https://synthetic.invalid/' + previous)

    def test_field_order_and_full_closing_tags_matter(self):
        reordered = (FIELDS[-1],) + FIELDS[:-1]
        result = self.verify(fixture(order=reordered))
        self.assertEqual(result['status'], -4006)
        self.assertEqual(result['urls'], {})
        result = self.verify(fixture().replace(b'<CasURL>https://synthetic.invalid/CasURL</CasURL>', b'<CasURL/>'))
        self.assertEqual(result['status'], -4006)

    def test_urls_are_raw_strings_without_native_uri_validation_or_fixed_truncation(self):
        values = {'CasURL': 'not-a-uri-' + 'x' * 1024, 'EcsURL': 'https://synthetic.invalid/a&amp;b'}
        result = self.verify(fixture(values=values))
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['urls']['CasURL'], values['CasURL'])
        self.assertEqual(result['urls']['EcsURL'], values['EcsURL'])
        empty = self.verify(fixture(values={'CasURL': ''}))
        self.assertEqual(empty['status'], 0)
        self.assertEqual(empty['urls']['CasURL'], '')

    def test_fingerprint_and_synthetic_input_bounds_fail_before_execution(self):
        with self.assertRaises(ValueError):
            verify_ec_config_response(b'synthetic-wrong-program', fixture())
        if self.source is None:
            self.skipTest('Private original v21 executable unavailable')
        for value in (b'', b'x' * (MAX_RESPONSE + 1), b'synthetic\0input', 'synthetic'):
            with self.subTest(type=type(value)), self.assertRaises(ValueError):
                verify_ec_config_response(self.source, value)


if __name__ == '__main__':
    unittest.main()
