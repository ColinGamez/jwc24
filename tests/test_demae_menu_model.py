from pathlib import Path
import unittest

from tools.verify_demae_menu_model import verify


class NativeMenuModelTests(unittest.TestCase):
    def test_native_deep_copy_selection_and_order_for_32_rows(self):
        source = Path(__file__).resolve().parents[1]/'private/demae/fixtures/HCHJ-local-api.dol'
        if not source.is_file():
            self.skipTest('Private executable unavailable')
        entries = [{'menuCode': f'M{n:012d}', 'linkTitle': '\u6d77\u9bae'+str(n),
                    'name': '\u540d'*128 if n == 31 else 'Category '+str(n),
                    'info': 'https://demae-can.com/shop/menu/123', 'setNum': '0',
                    'enabledLink': n % 2} for n in range(32)]
        result = verify(source.read_bytes(), entries)
        self.assertEqual(result['rows_verified'], 32)
        self.assertFalse(result['native_model_mocked'])
        self.assertFalse(result['native_rendering_verified'])
        self.assertFalse(result['lunch_verified'])

    def test_wrong_executable_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'unexpected', [])

    def test_every_native_allocation_failure_preserves_linked_rows(self):
        source = Path(__file__).resolve().parents[1]/'private/demae/fixtures/HCHJ-local-api.dol'
        if not source.is_file():
            self.skipTest('Private executable unavailable')
        entries = [{'menuCode': f'M{n}', 'linkTitle': 'Title', 'name': '\u6d77\u9bae',
                    'info': 'Source', 'setNum': '0', 'enabledLink': 0} for n in range(2)]
        data = source.read_bytes()
        # Each row allocates five setter strings, one node and five copies.
        for failure in range(1, 23):
            with self.subTest(failure=failure):
                result = verify(data, entries, fail_allocation=failure)
                self.assertTrue(result['allocation_failure_handled'])
                self.assertEqual(result['rows_retained'], (failure-1)//11)
        with self.assertRaisesRegex(ValueError, 'not reached'):
            verify(data, entries, fail_allocation=23)
