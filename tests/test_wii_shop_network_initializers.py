"""Bounded original caller tests with synthetic network/thread return stubs."""
from dataclasses import replace
import unittest

from tests import test_wii_shop_url as url_fixture
from tools.verify_wii_shop_network_initializers import (
    ERROR_MARKER, SyntheticNetworkResults, verify_network_initializers,
)


class NetworkInitializerTests(unittest.TestCase):
    def source(self):
        return url_fixture.NativeShopUrlTests.source(self)

    def verify(self, **changes):
        return verify_network_initializers(self.source(), SyntheticNetworkResults(**changes))

    def test_original_prepare_launch_worker_and_poll_contract(self):
        result = self.verify()
        self.assertEqual((result['prepare_return'], result['state_after_prepare'], result['launch_return']), (1, 1, 1))
        self.assertEqual((result['state_before_poll'], result['worker_state'], result['state_after_poll']), (2, 3, 3))
        self.assertEqual(result['preparation_value_after_poll'], 0x1234)
        self.assertTrue(result['guards_verified'])
        self.assertTrue(result['write_ranges_checked'])
        self.assertFalse(result['browser_or_network_invoked'])
        self.assertFalse(result['native_thread_scheduler_invoked'])
        self.assertFalse(result['EC_init_connect_or_plugin_registration_verified'])

    def test_callback_pairs_stack_sizes_and_priorities_are_captured(self):
        calls = {c['boundary']: c for c in self.verify()['boundary_calls']}
        self.assertEqual(calls['SOInit_diagnostic_associated']['allocator_callbacks'], ['0x8002faa0', '0x8002fac0'])
        self.assertEqual(calls['NHTTPStartup_diagnostic_associated']['allocator_callbacks'], ['0x8002fae0', '0x8002fb00'])
        self.assertEqual(calls['heap_allocation']['bytes'], 0x18000)
        self.assertEqual(calls['worker_stack_allocation']['bytes'], 0x4000)
        self.assertEqual(calls['thread_creation']['entry'], '0x8002f710')
        self.assertEqual(calls['thread_creation']['stack_bytes'], 0x4000)
        self.assertEqual(calls['thread_creation']['priority'], 14)
        self.assertEqual(calls['thread_creation']['attributes'], 1)
        self.assertEqual(calls['NHTTPStartup_diagnostic_associated']['priority'], 15)

    def test_so_init_requires_literal_zero_before_stack_and_launch(self):
        for status in (-1, 1):
            with self.subTest(status=status):
                result = self.verify(so_init_result=status)
                self.assertEqual(result['prepare_return'], 0)
                self.assertEqual(result['state_after_prepare'], 0)
                self.assertIsNone(result['launch_return'])
                self.assertFalse(result['worker_invoked_directly'])
                self.assertNotIn('worker_stack_allocation', [c['boundary'] for c in result['boundary_calls']])

    def test_failed_stack_allocation_prevents_thread_launch(self):
        result = self.verify(worker_stack_available=False)
        self.assertEqual(result['prepare_return'], 0)
        self.assertIsNone(result['launch_return'])
        self.assertFalse(result['worker_invoked_directly'])

    def test_failed_thread_creation_keeps_native_failure_marker(self):
        result = self.verify(create_thread_result=0)
        self.assertEqual(result['launch_return'], 0)
        self.assertEqual(result['state_before_poll'], 4)
        self.assertEqual(result['error_after_poll'], ERROR_MARKER)
        self.assertFalse(result['worker_invoked_directly'])
        self.assertNotIn('thread_resume', [c['boundary'] for c in result['boundary_calls']])

    def test_negative_socket_startup_copies_converted_error_and_skips_http(self):
        result = self.verify(so_startup_result=-7, socket_error_result=-0x12345678)
        self.assertEqual((result['worker_state'], result['worker_error']), (4, 0x12345678))
        self.assertEqual((result['state_after_poll'], result['error_after_poll']), (4, 0x12345678))
        self.assertNotIn('NHTTPStartup_diagnostic_associated', [c['boundary'] for c in result['boundary_calls']])

    def test_nonnegative_socket_startup_continues_to_http(self):
        result = self.verify(so_startup_result=1)
        self.assertEqual(result['worker_state'], 3)
        self.assertIn('NHTTPStartup_diagnostic_associated', [c['boundary'] for c in result['boundary_calls']])

    def test_any_nonzero_http_result_keeps_failure_state(self):
        for status in (-1, 1):
            with self.subTest(status=status):
                result = self.verify(nhttp_startup_result=status)
                self.assertEqual((result['worker_state'], result['worker_error']), (4, ERROR_MARKER))
                self.assertEqual((result['state_after_poll'], result['error_after_poll']), (4, ERROR_MARKER))

    def test_poll_waits_for_completion_query_before_copying_worker_result(self):
        result = self.verify(thread_terminated=0)
        self.assertEqual(result['worker_state'], 3)
        self.assertEqual(result['state_after_poll'], 2)
        self.assertEqual(result['preparation_value_after_poll'], 0)
        self.assertEqual(result['poll_stop_address'], '0x8002f968')

    def test_other_poll_states_do_not_query_or_copy_worker(self):
        for state in (0, 1, 3, 4):
            with self.subTest(state=state):
                result = self.verify(poll_state=state)
                self.assertEqual(result['state_after_poll'], state)
                self.assertEqual(result['preparation_value_after_poll'], 0)
                self.assertNotIn('thread_completion_query', [c['boundary'] for c in result['boundary_calls']])
                self.assertEqual(result['poll_stop_address'], '0x8002f884' if state == 3 else '0x8002f968')

    def test_fingerprint_mismatch_rejects_before_emulation(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_network_initializers(b'not an original executable')

    def test_result_bounds_reject_before_emulation(self):
        source = self.source()
        for changes in ({'so_init_result': True}, {'so_startup_result': 1 << 31},
                        {'nhttp_startup_result': -(1 << 31)-1}, {'worker_stack_available': 1},
                        {'create_thread_result': 2}, {'thread_terminated': -1},
                        {'preparation_value': -1}, {'socket_error_result': 1 << 31}, {'poll_state': 5}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                verify_network_initializers(source, replace(SyntheticNetworkResults(), **changes))
        with self.assertRaisesRegex(ValueError, 'explicit synthetic'):
            verify_network_initializers(source, {})


if __name__ == '__main__':
    unittest.main()
