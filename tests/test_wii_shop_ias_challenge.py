"""Synthetic IAS fixtures; no live challenge or registration service."""
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from jwc24 import wii_shop_ias_challenge as ias


def request(extra='', *, prefix='ias'):
    fields = ('<ias:Version>2.0</ias:Version><ias:MessageId>synthetic-message</ias:MessageId>'
              '<ias:Region>SYN</ias:Region><ias:Country>ZZ</ias:Country><ias:Language>zz</ias:Language>')
    return (f'<s:Envelope xmlns:s="{ias.SOAP_NS}" xmlns:ias="{ias.IAS_NS}" '
            f'xmlns:x="{ias.XSI_NS}"><s:Body><ias:GetChallenge x:type="ias:GetChallengeRequestType">'+
            fields+extra+'</ias:GetChallenge></s:Body></s:Envelope>').replace(
                'ias:', prefix+':').replace('xmlns:ias=', 'xmlns:'+prefix+'=').encode()


def response(**changes):
    values = dict(challenge=ias.EvidencedChallenge('synthetic', 'synthetic:challenge'),
                  error_code='0', status_source_ref='synthetic:status')
    values.update(changes)
    return ias.serialize_get_challenge_response(**values)


class ChallengeCodecTests(unittest.TestCase):
    def test_ias_prefix_action_and_common_fields_are_opaque(self):
        for prefix in ('ias', 'arbitrary'):
            result = ias.parse_get_challenge_request(request(prefix=prefix),
                soap_action='"'+ias.GET_CHALLENGE_ACTION+'"')
            self.assertEqual(dict(result.common_fields)['Version'], '2.0')
            self.assertIsNone(result.postal_code)
        self.assertNotIn('SerialNo', dict(result.common_fields))
        self.assertNotIn('ECVersion', dict(result.common_fields))

    def test_native_optional_identity_and_postal_values_are_private(self):
        raw = request('<ias:DeviceId>synthetic-device</ias:DeviceId>'
                      '<ias:DeviceToken>synthetic-token</ias:DeviceToken>'
                      '<ias:AccountId>synthetic-account</ias:AccountId>'
                      '<ias:Attributes><ias:Name>PostalCode</ias:Name>'
                      '<ias:Value>synthetic-postal</ias:Value></ias:Attributes>')
        result = ias.parse_get_challenge_request(raw, soap_action=ias.GET_CHALLENGE_ACTION)
        self.assertEqual(result.postal_code, 'synthetic-postal')
        self.assertEqual(dict(result.common_fields)['DeviceToken'], 'synthetic-token')
        for value in ('synthetic-device', 'synthetic-token', 'synthetic-account', 'synthetic-postal'):
            self.assertNotIn(value, repr(result))
        fixture = ias.EvidencedChallenge('secret', 'private-reference')
        self.assertNotIn('secret', repr(fixture))
        self.assertNotIn('private-reference', repr(fixture))

    def test_ecs_cas_fields_and_other_actions_are_not_mixed_into_ias(self):
        for raw in (request('<ias:SerialNo>x</ias:SerialNo>'), request('<ias:Age>1</ias:Age>'),
                    request('<ias:ECVersion>x</ias:ECVersion>'),
                    request('<ias:ApplicationId>x</ias:ApplicationId>'), request('<ias:TIN>x</ias:TIN>'),
                    request().replace(ias.IAS_NS.encode(), b'urn:ecs.wsapi.broadon.com')):
            with self.subTest(raw=raw), self.assertRaises(ias.ChallengeContractError):
                ias.parse_get_challenge_request(raw, soap_action=ias.GET_CHALLENGE_ACTION)
        with self.assertRaises(ias.ChallengeContractError):
            ias.parse_get_challenge_request(request(), soap_action='urn:ecs.wsapi.broadon.com/GetChallenge')

    def test_wrong_type_duplicates_headers_nested_and_mixed_fields_are_rejected(self):
        for raw in (request().replace(b'GetChallengeRequestType', b'WrongType'),
                    request('<ias:Country>duplicate</ias:Country>'),
                    request().replace(b'<s:Body>', b'<s:Header/><s:Body>'),
                    request('<ias:DeviceId><ias:Nested/></ias:DeviceId>'),
                    request().replace(b'</ias:Country>', b'</ias:Country>mixed'),
                    request().replace(b'<ias:Version>2.0', b'<ias:Version>1.0'),
                    request().replace(b'<ias:Language>zz</ias:Language>', b'')):
            with self.subTest(raw=raw), self.assertRaises(ias.ChallengeContractError):
                ias.parse_get_challenge_request(raw, soap_action=ias.GET_CHALLENGE_ACTION)

    def test_only_one_native_postal_name_value_pair_is_supported(self):
        valid = '<ias:Attributes><ias:Name>PostalCode</ias:Name><ias:Value>x</ias:Value></ias:Attributes>'
        for extra in (valid+valid, valid.replace('PostalCode', 'Unknown'),
                      valid.replace('<ias:Value>', '<ias:Value attr="x">'),
                      valid.replace('</ias:Name>', '</ias:Name>mixed'),
                      valid.replace('<ias:Value>x</ias:Value>', '<ias:Value><ias:Nested/></ias:Value>')):
            with self.subTest(extra=extra), self.assertRaises(ias.ChallengeContractError):
                ias.parse_get_challenge_request(request(extra), soap_action=ias.GET_CHALLENGE_ACTION)

    def test_xml_byte_structure_namespace_and_text_bounds(self):
        cases = [b'\xff'+request(), b'<!DOCTYPE x [<!ENTITY y "z">]>'+request(),
                 request()[:-2], b' '*(ias.MAX_XML_BYTES+1),
                 request('<ias:DeviceId>'+'x'*(ias.MAX_TEXT+1)+'</ias:DeviceId>')]
        declarations = ''.join(f' xmlns:n{i}="urn:{i}"' for i in range(33)).encode()
        cases.append(request().replace(b'<s:Envelope ', b'<s:Envelope '+declarations+b' '))
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(ias.ChallengeContractError):
                ias.parse_get_challenge_request(raw, soap_action=ias.GET_CHALLENGE_ACTION)

    def test_response_has_literal_native_shape_and_does_not_generate_challenge(self):
        raw = response(timestamp='123', error_message='synthetic & info')
        self.assertTrue(raw.startswith(b'<?xml version="1.0" encoding="UTF-8"?>'))
        self.assertIn(b'<GetChallengeResponse xmlns="urn:ias.wsapi.broadon.com">', raw)
        root = ET.fromstring(raw)
        fields = {node.tag.split('}')[-1]: node.text for node in root[0][0]}
        self.assertEqual(fields['Challenge'], 'synthetic')
        self.assertEqual(fields['ErrorMessage'], 'synthetic & info')
        self.assertNotIn(b'synthetic:challenge', raw)
        with self.assertRaises(ias.ChallengeContractError):
            response(challenge=None)

    def test_capacity_is_utf8_bytes_not_characters_and_empty_is_native_accepted(self):
        for text in ('', 'x'*11, '\u5408'*3):
            self.assertIn(('<Challenge>'+text+'</Challenge>').encode(),
                response(challenge=ias.EvidencedChallenge(text, 'synthetic:challenge')))
        for text in ('x'*12, '\u5408'*4, '\ud800', '\x00'):
            with self.subTest(text=repr(text)), self.assertRaises(ias.ChallengeContractError):
                response(challenge=ias.EvidencedChallenge(text, 'synthetic:challenge'))

    def test_raw_text_policy_rejects_entity_changing_characters_without_echo(self):
        for text in ('A&B', '<secret>', 'A>B'):
            with self.subTest(text=text), self.assertRaises(ias.ChallengeContractError) as caught:
                response(challenge=ias.EvidencedChallenge(text, 'synthetic:challenge'))
            self.assertNotIn(text, str(caught.exception))
        self.assertIn(b'<Challenge>A%26B</Challenge>',
                      response(challenge=ias.EvidencedChallenge('A%26B', 'synthetic:challenge')))

    def test_reported_error_forbids_challenge_and_status_is_explicit(self):
        raw = response(challenge=None, error_code='42', error_message='synthetic failure')
        self.assertNotIn(b'<Challenge>', raw)
        self.assertIn(b'<ErrorCode>42</ErrorCode>', raw)
        for changes in ({'error_code': '42'}, {'error_code': '00'}, {'error_code': '-1'},
                        {'error_code': '4294967296'}, {'status_source_ref': ''},
                        {'timestamp': 'not-decimal'}, {'challenge': ias.EvidencedChallenge('x', '')}):
            with self.subTest(changes=changes), self.assertRaises(ias.ChallengeContractError):
                response(**changes)

    def test_serializer_checks_output_bound_before_buffer_growth(self):
        with patch.object(ias, 'MAX_XML_BYTES', 128), self.assertRaises(ias.ChallengeContractError):
            response()


if __name__ == '__main__':
    unittest.main()
