import unittest

from tests import test_wii_shop_url as url_tests
from tools.verify_wii_shop_transition import verify_transition


class NativeShopTransitionTests(unittest.TestCase):
    def source(self):
        return url_tests.NativeShopUrlTests.source(self)

    def test_japanese_eula_method_resolves_queues_and_requests_original_title(self):
        report = verify_transition(self.source(), 'jumpToEULAViewer')
        self.assertEqual(report['getter_result'], 7)
        self.assertEqual(report['callback_result'], 0x11)
        self.assertEqual(report['pending_after'], 7)
        self.assertEqual(report['title_id_requested'], '0001000848414B4A')
        self.assertEqual(report['cleanup_calls_stubbed'], 4)
        self.assertEqual(report['title_launch_calls_intercepted'], 1)
        self.assertTrue(report['result_and_object_guards_verified'])
        self.assertFalse(report['title_launch_executed'])
        self.assertFalse(report['eula_acceptance_verified'])

    def test_manual_method_uses_separate_request_and_title(self):
        report = verify_transition(self.source(), 'jumpToManualChannel')
        self.assertEqual(report['pending_after'], 9)
        self.assertEqual(report['title_id_requested'], '000100024843554A')

    def test_native_area_decoder_and_mapper_select_all_supported_suffixes(self):
        source = self.source()
        groups = {'J': ('JPN', 'TWN', 'ROC'), 'P': ('EUR', 'AUS'), 'K': ('KOR',),
                  'E': ('USA', 'BRA', 'HKG', 'ASI', 'LTN', 'SAF', 'CHN', 'ZZZ', None)}
        for method, prefix in (('jumpToEULAViewer', '0001000848414B'),
                               ('jumpToManualChannel', '00010002484355')):
            for suffix, areas in groups.items():
                for area in areas:
                    with self.subTest(method=method, area=area):
                        report = verify_transition(source, method, area=area)
                        self.assertEqual(report['title_id_requested'], prefix+f'{ord(suffix):02X}')
                        self.assertTrue(report['native_area_decoder_executed'])
                        self.assertEqual(report['area_lookup_calls_stubbed'], 1)

    def test_busy_request_is_preserved_even_when_callback_reports_0x11(self):
        source = self.source()
        for method in ('jumpToEULAViewer', 'jumpToManualChannel'):
            for pending in (1, 7, 9, 0xffffffff):
                with self.subTest(method=method, pending=pending):
                    report = verify_transition(source, method, pending_request=pending)
                    self.assertEqual(report['pending_after'], pending)
                    self.assertEqual(report['callback_result'], 0x11)
                    self.assertTrue(report['existing_pending_request_preserved'])
                    self.assertFalse(report['native_dispatcher_executed'])
                    self.assertIsNone(report['title_id_requested'])

    def test_browser_factory_failure_leaves_output_and_pending_state_untouched(self):
        source = self.source()
        for method in ('jumpToEULAViewer', 'jumpToManualChannel'):
            for result in (-1, -0x80000000):
                with self.subTest(method=method, result=result):
                    report = verify_transition(source, method, factory_result=result)
                    self.assertEqual(report['getter_result'], 10)
                    self.assertIsNone(report['callback_result'])
                    self.assertEqual(report['pending_after'], 0)
                    self.assertTrue(report['result_and_object_guards_verified'])

    def test_nonnegative_factory_results_create_callable(self):
        source = self.source()
        for result in (0, 1, 0x7fffffff):
            report = verify_transition(source, 'jumpToEULAViewer', factory_result=result)
            self.assertEqual(report['getter_result'], 7)
            self.assertEqual(report['pending_after'], 7)

    def test_unknown_or_changed_property_name_does_not_create_browser_function(self):
        source = self.source()
        for name in ('unknownMethod', 'JumpToEULAViewer', 'jumpToEULAViewer ', 'jumpToManualChannelX'):
            with self.subTest(name=name):
                report = verify_transition(source, name)
                self.assertEqual(report['getter_result'], 8)
                self.assertEqual(report['function_factory_calls_stubbed'], 0)
                self.assertEqual(report['pending_after'], 0)

    def test_fingerprint_and_bounded_inputs_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify_transition(b'', 'jumpToEULAViewer')
        source = self.source()
        for name in ('', 'a'*65, 'bad\0name', '\u3042'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'property'):
                verify_transition(source, name)
        for kwargs in ({'area': 'JP'}, {'area': 'jpn'}, {'pending_request': -1},
                       {'pending_request': True}, {'factory_result': 0x80000000},
                       {'factory_result': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                verify_transition(source, 'jumpToEULAViewer', **kwargs)
