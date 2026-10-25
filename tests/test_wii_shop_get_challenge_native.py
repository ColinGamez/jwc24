"""Original IAS operation on synthetic fixtures; private executable required."""
import unittest

from tests import test_wii_shop_url as native_fixture
from tools.verify_wii_shop_get_challenge import verify_get_challenge, SyntheticRequestEnvironment
from jwc24 import wii_shop_ias_challenge as ias
from tests.test_wii_shop_ias_challenge import response


class NativeChallengeTests(unittest.TestCase):
    def source(self):
        return native_fixture.NativeShopUrlTests.source(self)

    def test_native_request_goes_directly_into_offline_parser(self):
        result = verify_get_challenge(self.source(), response())
        parsed = ias.parse_get_challenge_request(result['request_bytes'], soap_action=ias.GET_CHALLENGE_ACTION)
        self.assertEqual(dict(parsed.common_fields)['Version'], '2.0')
        self.assertEqual(result['challenge_bytes'], b'synthetic')
        self.assertEqual(result['status'], 0)
        self.assertIn((b'SOAPAction', ias.GET_CHALLENGE_ACTION.encode()), result['headers'])
        for key in ('native_request_builder_executed', 'native_common_response_parser_executed',
                    'native_challenge_reader_executed', 'object_heap_stack_and_write_bounds_verified'):
            self.assertTrue(result[key])
        self.assertFalse(result['native_xml_helpers_stubbed'])
        self.assertFalse(result['transport_executed'])
        self.assertFalse(result['account_or_device_authorized'])

    def test_optional_common_identity_and_postal_fields_match_native_wire(self):
        environment = SyntheticRequestEnvironment(key_pair_confirmed=True, token='synthetic-trigger',
            weak_token='weak:synthetic', strong_token='strong:synthetic', account_id='synthetic-account',
            application_id='synthetic-app', tin='synthetic-tin', postal_code='synthetic-postal')
        result = verify_get_challenge(self.source(), response(), environment=environment)
        parsed = ias.parse_get_challenge_request(result['request_bytes'], soap_action=ias.GET_CHALLENGE_ACTION)
        self.assertEqual(parsed.postal_code, 'synthetic-postal')
        fields = dict(parsed.common_fields)
        self.assertEqual(fields['DeviceToken'], 'weak:synthetic')
        for unsupported in ('SerialNo', 'ECVersion', 'Age', 'ApplicationId', 'TIN'):
            self.assertNotIn(unsupported, fields)

    def test_explicit_serializer_values_reach_native_reader_unchanged(self):
        for value in ('', 'x'*11, '\u5408'*3, 'A%26B'):
            with self.subTest(value=value):
                result = verify_get_challenge(self.source(), response(
                    challenge=ias.EvidencedChallenge(value, 'synthetic:challenge')))
                self.assertEqual(result['status'], 0)
                self.assertEqual(result['challenge_bytes'], value.encode())

    def test_native_overcapacity_and_missing_challenge_clear_the_old_value(self):
        baseline = response(challenge=ias.EvidencedChallenge('x', 'synthetic:challenge'))
        for value in (b'x'*12, ('\u5408'*4).encode()):
            raw = baseline.replace(b'<Challenge>x</Challenge>', b'<Challenge>'+value+b'</Challenge>')
            result = verify_get_challenge(self.source(), raw)
            self.assertEqual(result['status'], -4034)
            self.assertEqual(result['challenge_bytes'], b'')
        result = verify_get_challenge(self.source(), baseline.replace(b'<Challenge>x</Challenge>\n', b''))
        self.assertEqual(result['status'], -4006)
        self.assertEqual(result['challenge_bytes'], b'')

    def test_common_error_and_transport_failure_preserve_old_challenge(self):
        result = verify_get_challenge(self.source(), response(challenge=None, error_code='42'))
        self.assertEqual(result['status'], -4015)
        self.assertEqual(result['challenge_bytes'], b'old-proof')
        self.assertFalse(result['native_challenge_reader_executed'])
        result = verify_get_challenge(self.source(), response(), transport_status=-4007)
        self.assertEqual(result['status'], -4007)
        self.assertEqual(result['challenge_bytes'], b'old-proof')
        self.assertFalse(result['native_common_response_parser_executed'])

    def test_common_namespace_quirk_is_not_mistaken_for_namespace_validation(self):
        result = verify_get_challenge(self.source(), response().replace(
            b'<GetChallengeResponse xmlns="urn:ias.wsapi.broadon.com">',
            b'<GetChallengeResponse xmlns="urn:synthetic:wrong">'))
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['challenge_bytes'], b'synthetic')

    def test_zero_code_informational_message_and_raw_entity_copy_match_retail(self):
        result = verify_get_challenge(self.source(), response(error_message='synthetic informational text'))
        self.assertEqual(result['status'], 0)
        raw = response().replace(b'<Challenge>synthetic</Challenge>', b'<Challenge>A&amp;B</Challenge>')
        result = verify_get_challenge(self.source(), raw)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['challenge_bytes'], b'A&amp;B')

    def test_native_wire_common_text_can_be_malformed_but_parser_rejects_it(self):
        result = verify_get_challenge(self.source(), response(),
            environment=SyntheticRequestEnvironment(region='A&B'))
        with self.assertRaises(ias.ChallengeContractError):
            ias.parse_get_challenge_request(result['request_bytes'], soap_action=ias.GET_CHALLENGE_ACTION)

    def test_executable_and_fixture_bounds_are_checked_before_emulation(self):
        source = self.source()
        for data in (b'not-the-original', bytearray(source)):
            with self.assertRaises(ValueError):
                verify_get_challenge(data, response())
        for data in (b'', b'x'*16385, b'x\0'):
            with self.assertRaises(ValueError):
                verify_get_challenge(source, data)
        with self.assertRaises(ValueError):
            verify_get_challenge(source, response(), environment=SyntheticRequestEnvironment(region='\ud800'))


if __name__ == '__main__':
    unittest.main()
