import unittest

from tests import test_wii_shop_url as url_tests
from tools.verify_wii_shop_navigation import verify_navigation


class NativeShopNavigationTests(unittest.TestCase):
    def source(self):
        return url_tests.NativeShopUrlTests.source(self)

    def test_constructor_and_import_loop_publish_native_pointers(self):
        report = verify_navigation(self.source(), 1)
        self.assertEqual(report['constructor_entries_dispatched'], 46)
        self.assertEqual(report['unrelated_constructors_stubbed'], 45)
        self.assertEqual(report['browser_symbols_resolved_with_stub'], 117)
        self.assertFalse(report['native_import_loop_mocked'])
        self.assertFalse(report['native_url_initializer_mocked'])
        self.assertEqual(report['open_url_symbol'], 'WWWOpenUrl')

    def test_accepted_prerequisite_preserves_base_and_requests_initialization(self):
        report = verify_navigation(self.source(), 1)
        self.assertFalse(report['eula_selected'])
        self.assertEqual(report['initializers_stubbed'], 2)
        self.assertEqual(report['published_url'], 'https://shop.example')
        self.assertFalse(report['browser_or_network_invoked'])
        self.assertFalse(report['complete_boot_sequence_verified'])

    def test_mode_zero_entry_keeps_bare_base_without_two_arguments(self):
        source = self.source()
        for count in (0, 1):
            report = verify_navigation(source, 1, launch_argument_count=count)
            self.assertEqual(report['launch_mode'], 0)
            self.assertEqual(report['launch_argument_count'], count)
            self.assertEqual(report['published_url'], 'https://shop.example')
            self.assertFalse(report['native_entry_url_branch_mocked'])
        for count in (-1, 2, True):
            with self.assertRaisesRegex(ValueError, 'zero/one-argument'):
                verify_navigation(source, 1, launch_argument_count=count)

    def test_other_prerequisite_values_select_local_eula(self):
        source = self.source()
        for result in (0, 2, 0xffffffff):
            with self.subTest(result=result):
                report = verify_navigation(source, result)
                self.assertTrue(report['eula_selected'])
                self.assertEqual(report['initializers_stubbed'], 0)
                self.assertEqual(report['published_url'], 'file:/synthetic/eula.html')

    def test_dispatch_forwards_handle_url_and_unsigned_callback_result(self):
        source = self.source()
        for prerequisite in (0, 1):
            for result in (0, 1, 0xffffffff):
                with self.subTest(prerequisite=prerequisite, result=result):
                    report = verify_navigation(source, prerequisite, callback_result=result)
                    self.assertEqual(report['open_url_calls'], 1)
                    self.assertTrue(report['callback_return_forwarded'])
                    self.assertFalse(report['native_dispatch_thunk_mocked'])
                    self.assertEqual(report['callback_result'], result)

    def test_fingerprint_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_navigation(b'', 1)

    def test_external_stub_results_must_be_u32(self):
        source = self.source()
        for value in (-1, 0x100000000, True, '1'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'U32'):
                verify_navigation(source, value)
            with self.subTest(callback=value), self.assertRaisesRegex(ValueError, 'U32'):
                verify_navigation(source, 1, callback_result=value)
