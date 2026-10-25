"""Original native predicates with synthetic PREPARSED browser callback fields."""
import unittest
from unittest.mock import patch

from tests import test_wii_shop_url as url_fixture
from tools import verify_wii_shop_origin as origin


class OriginFingerprintTests(unittest.TestCase):
    def test_original_fingerprint_is_required_before_execution(self):
        for source in (b'', b'synthetic non-retail executable', None):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'fingerprint'):
                origin.verify_origin_access(source, protocol=b'https', hostname=b'synthetic.invalid',
                                            port=443, current_url=None)


class NativeOriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = url_fixture.NativeShopUrlTests().source()

    def verify(self, **changes):
        values = dict(protocol=b'https', hostname=b'synthetic.shop.wii.com', port=443,
                      current_url=b'https://synthetic.shop.wii.com/oss/serv/W_03.jsp')
        values.update(changes)
        return origin.verify_origin_access(self.source, **values)

    def test_original_predicate_and_string_helpers_execute_with_override_off(self):
        result = self.verify()
        self.assertTrue(result['access_allowed'])
        self.assertTrue(result['page_https'])
        self.assertTrue(result['trusted_page'])
        self.assertTrue(result['native_hostname_predicate_executed'])
        self.assertTrue(result['native_strlen_executed'])
        self.assertTrue(result['native_strcmp_executed'])
        self.assertFalse(result['native_origin_or_string_helpers_stubbed'])
        self.assertTrue(result['native_test_mode_forced_off'])
        self.assertFalse(result['browser_url_parsing_or_canonicalization_verified'])
        self.assertFalse(result['global_or_method_access_verified'])
        self.assertFalse(result['browser_network_or_account_invoked'])

    def test_protocol_is_separate_from_admission_and_https_flag_is_case_sensitive(self):
        for protocol in (b'https', b'http', b'HTTPS', b'ftp', b'', b'synthetic'):
            result = self.verify(protocol=protocol)
            with self.subTest(protocol=protocol):
                self.assertTrue(result['access_allowed'])
                self.assertEqual(result['page_https'], protocol == b'https')

    def test_port_is_not_filtered_by_the_native_hostname_predicate(self):
        # Raw synthetic int fields are not claims about ports a browser supplies.
        for port in (-1, 0, 1, 80, 443, 65535, 2147483647):
            with self.subTest(port=port):
                self.assertTrue(self.verify(port=port)['access_allowed'])

    def test_exact_lowercase_suffix_and_its_leading_dot_are_required(self):
        cases = ((b'synthetic.shop.wii.com', True), (b'SYNTHETIC.shop.wii.com', True),
                 (b'.shop.wii.com', True), (b'shop.wii.com', False),
                 (b'synthetic.SHOP.WII.COM', False), (b'synthetic.shop.wii.com.', False),
                 (b'synthetic.shop.wii.com.invalid', False), (b'notshop.wii.com', False),
                 (b'127.0.0.1', False), (b'localhost', False), (b'', False))
        for hostname, allowed in cases:
            with self.subTest(hostname=hostname):
                self.assertEqual(self.verify(hostname=hostname)['access_allowed'], allowed)

    def test_hostname_255_byte_limit_is_distinct_from_harness_input_cap(self):
        suffix = b'.shop.wii.com'
        for length in (254, 255, 256, 257, origin.MAX_STRING_BYTES):
            hostname = b'x'*(length-len(suffix))+suffix
            with self.subTest(length=length):
                self.assertEqual(self.verify(hostname=hostname)['access_allowed'], length < 256)

    def test_raw_callback_substring_is_case_sensitive_and_not_a_path_parser(self):
        cases = ((b'https://synthetic.shop.wii.com/oss/serv/W_03.jsp', True),
                 (b'https://synthetic.shop.wii.com/oss/oss/ext/manual/index.html', False),
                 (b'https://synthetic.shop.wii.com/ext', True),
                 (b'https://synthetic.shop.wii.com/EXT/manual', True),
                 (b'https://synthetic.shop.wii.com/%65xt/manual', True),
                 (b'https://synthetic.shop.wii.com/normal?target=/ext/manual', False),
                 (b'https://synthetic.shop.wii.com/normal#fragment=/ext/manual', False))
        for current_url, trusted in cases:
            with self.subTest(current_url=current_url):
                result = self.verify(current_url=current_url)
                self.assertEqual(result['trusted_page'], trusted)
                self.assertTrue(result['access_allowed'])

    def test_raw_url_scan_checks_start_indices_zero_through_126_only(self):
        for start in (0, 125, 126, 127, 128, 500):
            # Deliberately raw padded callback strings, not complete browser URLs.
            result = self.verify(current_url=b'x'*start+b'/ext/')
            with self.subTest(start=start):
                self.assertEqual(result['trusted_page'], start >= 127)

    def test_missing_callback_and_null_callback_result_are_distinct(self):
        missing = self.verify(current_url=None, callback_present=False)
        null = self.verify(current_url=None)
        self.assertEqual(missing['current_url_callback_calls'], 0)
        self.assertFalse(missing['current_url_callback_present'])
        self.assertEqual(null['current_url_callback_calls'], 1)
        self.assertTrue(null['current_url_callback_returns_null'])
        for result in (missing, null):
            self.assertTrue(result['trusted_page'])
            self.assertTrue(result['access_allowed'])

    def test_independent_inconsistent_fields_do_not_prove_browser_canonicalization(self):
        # These intentional mismatches measure the boundary's separate arguments.
        result = self.verify(hostname=b'synthetic.invalid')
        self.assertFalse(result['access_allowed'])
        self.assertTrue(result['page_https'])
        self.assertTrue(result['trusted_page'])
        result = self.verify(current_url=b'http://synthetic.invalid/plain')
        self.assertTrue(result['access_allowed'])
        self.assertTrue(result['page_https'])
        self.assertTrue(result['trusted_page'])

    def test_input_stack_state_and_callback_guards_are_checked_without_echo(self):
        result = self.verify(hostname=b'synthetic-private-marker.shop.wii.com',
                             current_url=b'https://synthetic.invalid/private-query-marker')
        self.assertTrue(result['input_and_stack_guards_verified'])
        self.assertTrue(result['native_write_ranges_checked'])
        self.assertLess(result['native_instructions'], origin.MAX_INSTRUCTIONS)
        self.assertNotIn('private-marker', repr(result))
        self.assertNotIn('private-query-marker', repr(result))

    def test_invalid_synthetic_inputs_are_rejected_without_execution_or_echo(self):
        for changes in ({'hostname': b'x'*(origin.MAX_STRING_BYTES+1)},
                        {'hostname': b'private-marker\0.shop.wii.com'},
                        {'protocol': 'https'}, {'port': True}, {'port': 2147483648},
                        {'current_url': b'private-marker\0'}, {'callback_present': 1},
                        {'callback_present': False}):
            with self.subTest(changes=changes):
                try:
                    self.verify(**changes)
                except ValueError as error:
                    self.assertNotIn('private-marker', str(error))
                else:
                    self.fail('Invalid synthetic callback fields accepted')

    def test_instruction_budget_exhaustion_fails_closed(self):
        with patch.object(origin, 'MAX_INSTRUCTIONS', 1):
            with self.assertRaisesRegex(ValueError, 'instruction cap'):
                self.verify()


if __name__ == '__main__':
    unittest.main()
