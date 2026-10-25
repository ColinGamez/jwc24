"""Synthetic offline ECS fixtures; no captured account/device or endpoint data."""
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from jwc24 import wii_shop_ec_config as config
from jwc24.wii_shop_ec_config import (
    ECS_NS, SOAP_NS, GET_EC_CONFIG_ACTION, URL_FIELDS, EvidencedURL,
    EcConfigContractError, parse_get_ec_config_request, serialize_get_ec_config_response,
)


def request(extra='', *, prefix='e', ec_version='synthetic-client-version', serial='synthetic-serial'):
    fields = ('<e:Version>2.0</e:Version><e:MessageId>synthetic-message</e:MessageId>'
              '<e:Region>JPN</e:Region><e:Country>JP</e:Country><e:Language>ja</e:Language>'
              f'<e:SerialNo>{serial}</e:SerialNo><e:ECVersion>{ec_version}</e:ECVersion>'+extra)
    return (f'<s:Envelope xmlns:s="{SOAP_NS}" xmlns:e="{ECS_NS}" '
            f'xmlns:x="{config.XSI_NS}"><s:Body>'
            '<e:GetECConfig x:type="e:GetECConfigRequestType">'+fields+
            '</e:GetECConfig></s:Body></s:Envelope>').replace('e:', prefix+':').replace(
                'xmlns:e=', 'xmlns:'+prefix+'=').encode('utf-8')


def urls():
    return {name: EvidencedURL('https://'+name.lower()+'.invalid/synthetic', 'synthetic:'+name)
            for name in URL_FIELDS}


def response(**changes):
    values = dict(urls=urls(), error_code='0', status_source_ref='synthetic:status')
    values.update(changes)
    return serialize_get_ec_config_response(**values)


class EcConfigRequestTests(unittest.TestCase):
    def test_ecs_serial_number_and_explicit_product_version_are_opaque(self):
        parsed = parse_get_ec_config_request(request(ec_version='合成&amp;版'), soap_action=GET_EC_CONFIG_ACTION)
        self.assertEqual(parsed.ec_version, '合成&版')
        self.assertEqual(dict(parsed.common_fields)['SerialNo'], 'synthetic-serial')
        self.assertNotIn('AccountId', dict(parsed.common_fields))
        # An empty, structurally present serial is not authenticated or invented.
        parsed = parse_get_ec_config_request(request(serial=''), soap_action=GET_EC_CONFIG_ACTION)
        self.assertEqual(dict(parsed.common_fields)['SerialNo'], '')

    def test_prefixes_quoted_action_and_optional_correct_type(self):
        for prefix in ('ecs', 'arbitrary'):
            parsed = parse_get_ec_config_request(request(prefix=prefix), soap_action='"'+GET_EC_CONFIG_ACTION+'"')
            self.assertEqual(parsed.ec_version, 'synthetic-client-version')
        raw = request().replace(b' x:type="e:GetECConfigRequestType"', b'')
        self.assertEqual(parse_get_ec_config_request(raw, soap_action=GET_EC_CONFIG_ACTION).ec_version,
                         'synthetic-client-version')

    def test_common_and_product_values_are_excluded_from_repr_and_errors(self):
        raw = request('<e:DeviceId>synthetic-device</e:DeviceId>'
                      '<e:DeviceToken>synthetic-secret</e:DeviceToken>'
                      '<e:AccountId>synthetic-account</e:AccountId>')
        parsed = parse_get_ec_config_request(raw, soap_action=GET_EC_CONFIG_ACTION)
        self.assertIn(('DeviceToken', 'synthetic-secret'), parsed.common_fields)
        for token in ('synthetic-secret', 'synthetic-device', 'synthetic-account',
                      'synthetic-serial', 'synthetic-client-version'):
            self.assertNotIn(token, repr(parsed))
        try:
            parse_get_ec_config_request(raw.replace(b'</e:GetECConfig>',
                b'<e:AccountId>synthetic-account</e:AccountId></e:GetECConfig>'), soap_action=GET_EC_CONFIG_ACTION)
        except EcConfigContractError as error:
            self.assertNotIn('synthetic-account', str(error))
        else:
            self.fail('Duplicate account field accepted')

    def test_cas_namespace_age_and_other_actions_are_rejected(self):
        for raw in (request().replace(ECS_NS.encode(), b'urn:cas.wsapi.broadon.com'),
                    request('<e:Age>99</e:Age>'),
                    request().replace(b'GetECConfigRequestType', b'ListTitlesRequestType'),
                    request().replace(b'e:GetECConfig', b'e:ListTitles')):
            with self.subTest(raw=raw), self.assertRaises(EcConfigContractError):
                parse_get_ec_config_request(raw, soap_action=GET_EC_CONFIG_ACTION)
        with self.assertRaises(EcConfigContractError):
            parse_get_ec_config_request(request(), soap_action='urn:cas.wsapi.broadon.com/GetECConfig')

    def test_duplicates_missing_and_wrong_version_are_rejected(self):
        for raw in (request('<e:ECVersion>another</e:ECVersion>'), request('<e:Unknown/>'),
                    request().replace(b'<e:SerialNo>synthetic-serial</e:SerialNo>', b''),
                    request().replace(b'<e:Version>2.0</e:Version>', b'<e:Version>1.0</e:Version>'),
                    request(ec_version=''), request('<e:DeviceId extra="synthetic"/>')):
            with self.subTest(raw=raw), self.assertRaises(EcConfigContractError):
                parse_get_ec_config_request(raw, soap_action=GET_EC_CONFIG_ACTION)

    def test_mixed_content_multiple_operations_and_soap_header_are_rejected(self):
        for raw in (request().replace(b'<s:Body>', b'<s:Header/><s:Body>'),
                    request().replace(b'</s:Body>', b'<e:GetECConfig/></s:Body>'),
                    request().replace(b'</e:Country>', b'</e:Country>unexpected'),
                    request('<e:DeviceId><e:Nested/></e:DeviceId>'),
                    request('<e:DeviceId xmlns:e="urn:other">synthetic</e:DeviceId>')):
            with self.subTest(raw=raw), self.assertRaises(EcConfigContractError):
                parse_get_ec_config_request(raw, soap_action=GET_EC_CONFIG_ACTION)

    def test_entities_non_utf8_malformed_and_input_bounds_are_rejected(self):
        for raw in (b'<!DOCTYPE x [<!ENTITY x "synthetic">]>'+request(), b'\xff'+request(),
                    request()[:-4], b' '*config.MAX_XML_BYTES+b'x',
                    request(ec_version='x'*(config.MAX_TEXT+1)),
                    request('<e:A><e:B><e:C/></e:B></e:A>'),
                    request('<e:Unknown/>'*config.MAX_ELEMENTS)):
            with self.subTest(size=len(raw)), self.assertRaises(EcConfigContractError):
                parse_get_ec_config_request(raw, soap_action=GET_EC_CONFIG_ACTION)
        raw = request().replace(b'<s:Body>',
            ('<s:Body '+''.join(f'xmlns:q{i}="urn:synthetic:{i}" ' for i in range(config.MAX_NAMESPACES))+'>').encode())
        with self.assertRaisesRegex(EcConfigContractError, 'namespace count'):
            parse_get_ec_config_request(raw, soap_action=GET_EC_CONFIG_ACTION)


class EcConfigResponseTests(unittest.TestCase):
    def test_exact_ecs_lexical_envelope_and_five_fields_in_source_order(self):
        data = response(timestamp='123456')
        self.assertTrue(data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn(b'<soapenv:Envelope ', data)
        self.assertIn(b'<soapenv:Body>', data)
        self.assertIn(b'<GetECConfigResponse xmlns="urn:ecs.wsapi.broadon.com">', data)
        self.assertLess(data.index(b'<TimeStamp>'), data.index(b'<ErrorCode>'))
        positions = [data.index(('<'+name+'>').encode()) for name in URL_FIELDS]
        self.assertEqual(positions, sorted(positions))
        parsed = ET.fromstring(data)[0][0]
        self.assertEqual(parsed.tag, '{'+ECS_NS+'}GetECConfigResponse')
        for name in URL_FIELDS:
            self.assertEqual(parsed.find('{'+ECS_NS+'}'+name).text, urls()[name].value)
        for unsupported in (b'AccountId', b'DeviceToken', b'SerialNo', b'MessageId',
                            b'synthetic:status', b'<Prices>', b'<Owned>'):
            self.assertNotIn(unsupported, data)

    def test_no_endpoint_defaults_and_evidence_is_not_serialized(self):
        for mapping in (None, {}, {k: v for k, v in urls().items() if k != 'CasURL'},
                        dict(urls(), Unexpected=EvidencedURL('https://extra.invalid/', 'synthetic'))):
            with self.subTest(mapping=mapping), self.assertRaises(EcConfigContractError):
                response(urls=mapping)
        for name in URL_FIELDS:
            self.assertNotIn(('synthetic:'+name).encode(), response())
        with self.assertRaises(EcConfigContractError):
            response(status_source_ref='')
        mapping = urls()
        mapping['CasURL'] = EvidencedURL('https://cas.invalid/', '')
        with self.assertRaises(EcConfigContractError):
            response(urls=mapping)

    def test_reported_error_has_no_urls_and_does_not_require_account_success(self):
        data = response(urls=None, error_code='123', error_message='synthetic & <error>')
        self.assertIn(b'<ErrorCode>123</ErrorCode>', data)
        self.assertIn(b'<ErrorMessage>synthetic &amp; &lt;error&gt;</ErrorMessage>', data)
        self.assertTrue(all(('<'+name+'>').encode() not in data for name in URL_FIELDS))
        with self.assertRaises(EcConfigContractError):
            response(error_code='123')
        self.assertNotIn(b'ErrorMessage', response(urls=None, error_code='123'))

    def test_nonempty_message_with_literal_zero_keeps_retail_success_url_shape(self):
        data = response(error_message='synthetic-information & <details>')
        self.assertIn(b'<ErrorCode>0</ErrorCode>', data)
        self.assertIn(b'<ErrorMessage>synthetic-information &amp; &lt;details&gt;</ErrorMessage>', data)
        self.assertTrue(all(('<'+name+'>').encode() in data for name in URL_FIELDS))
        with self.assertRaises(EcConfigContractError):
            response(urls=None, error_message='synthetic-information')
        # Matched retail status depends on ErrorCode, including with empty text.
        self.assertIn(b'<EcsURL>', response(error_message=''))
        # Canonical local status policy avoids lexical-vs-numeric ambiguity.
        with self.assertRaises(EcConfigContractError):
            response(urls=None, error_code='00')

    def test_url_values_are_escaped_but_refs_and_values_are_private_in_repr(self):
        mapping = urls()
        mapping['EcsURL'] = EvidencedURL('https://ecs.invalid/path%26synthetic', 'synthetic:private-reference')
        self.assertIn(b'https://ecs.invalid/path%26synthetic', response(urls=mapping))
        self.assertNotIn('ecs.invalid', repr(mapping['EcsURL']))
        self.assertNotIn('private-reference', repr(mapping['EcsURL']))

    def test_uri_checks_are_explicit_local_policy_and_do_not_echo_values(self):
        for value in ('https://synthetic-user:synthetic-secret@host.invalid/',
                      'https://host.invalid/path?synthetic-secret=value', 'https://host.invalid/#secret',
                      'https://host.invalid/path&synthetic', 'https://host.invalid/?', 'https://host.invalid/#',
                      '/relative', 'ftp://host.invalid/', 'https://host.invalid:bad/',
                      'https://host.invalid:0/', 'https://host.invalid:65536/',
                      'https:///missing-host', 'https://host.invalid/with space',
                      'https://host.invalid/\x00', 'https://host.invalid/\x7f',
                      'https://host.invalid/\\synthetic'):
            mapping = urls()
            mapping['EcsURL'] = EvidencedURL(value, 'synthetic:uri-policy')
            try:
                response(urls=mapping)
            except EcConfigContractError as error:
                self.assertNotIn(value, str(error))
                self.assertNotIn('synthetic-secret', str(error))
            else:
                self.fail('Unsupported synthetic URI accepted')

    def test_invalid_status_timestamp_text_and_url_types_reject(self):
        for changes in ({'error_code': 0}, {'error_code': '-1'}, {'error_code': ''},
                        {'error_code': '00'}, {'error_code': '000123'}, {'error_code': '4294967296'},
                        {'timestamp': True}, {'timestamp': 'synthetic'},
                        {'error_message': '\x00'}, {'error_message': 'x'*(config.MAX_TEXT+1)},
                        {'urls': {k: 'https://synthetic.invalid/' for k in URL_FIELDS}}):
            with self.subTest(changes=changes), self.assertRaises(EcConfigContractError):
                response(**changes)

    def test_utf8_byte_expansion_hits_byte_limit_before_later_urls(self):
        prefix = 'https://synthetic.invalid/'
        endpoint = EvidencedURL(prefix+'\U00020000'*(config.MAX_TEXT-len(prefix)), 'synthetic:large-url')
        mapping = {name: endpoint for name in URL_FIELDS}
        with patch.object(config, '_url', wraps=config._url) as checked:
            with self.assertRaisesRegex(EcConfigContractError, 'Response exceeds local byte bound'):
                response(urls=mapping)
        self.assertLess(checked.call_count, len(URL_FIELDS))


if __name__ == '__main__':
    unittest.main()
