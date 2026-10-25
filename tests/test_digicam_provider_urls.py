"""Native URL formatting only: no account, image upload or print order."""
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.verify_digicam_provider_urls import verify_provider_urls


class DigicamProviderUrlTests(unittest.TestCase):
    def source(self):
        path = Path('private/channel_coverage_20261026/hcdj-v1024/main.private.dol')
        if not path.is_file():
            self.skipTest('Private fingerprinted HCDJ v1024 application required')
        return path.read_bytes()

    def test_original_production_selector_uses_tls_and_both_provider_servlets(self):
        with patch('socket.socket', side_effect=AssertionError('Offline native check opened a socket')):
            result = verify_provider_urls(self.source())
        self.assertEqual(result['provider_urls'], [
            'https://wch.fdinet.fujifilm.co.jp/wii_svr/WPOperationServlet',
            'https://wch.fdinet.fujifilm.co.jp/wii_svr/WPFileOperationServlet'])
        self.assertTrue(result['native_formatter_executed'])
        self.assertTrue(result['native_tls_selector_executed'])
        self.assertTrue(result['synthetic_buffer_guards_verified'])
        self.assertTrue(result['native_write_ranges_checked'])
        self.assertFalse(result['native_formatter_or_selector_stubbed'])
        self.assertFalse(result['network_or_print_order_invoked'])
        self.assertFalse(result['settings_or_credentials_read_from_nand'])

    def test_unhandled_selectors_preserve_both_output_buffers(self):
        for selector in (7, 255):
            with self.subTest(selector=selector):
                result = verify_provider_urls(self.source(), selector=selector)
                self.assertEqual(result['provider_urls'], [])
                self.assertFalse(result['native_formatter_executed'])
                self.assertTrue(result['synthetic_buffer_guards_verified'])

    def test_source_and_selector_guards_prevent_other_program_paths(self):
        for source in (b'', b'not-the-retail-application'):
            with self.assertRaises(ValueError):
                verify_provider_urls(source)
        for selector in (True, -1, 1, 6, 256, '0'):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                verify_provider_urls(self.source(), selector=selector)


if __name__ == '__main__':
    unittest.main()
