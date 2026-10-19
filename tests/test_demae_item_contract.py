from pathlib import Path
import unittest

from tools.inspect_demae_item_contract import inspect


class ItemContractTests(unittest.TestCase):
    def test_native_item_lookup_and_nonempty_size_gates(self):
        source = Path(__file__).resolve().parents[1]/'private/demae/fixtures/HCHJ-local-api.dol'
        if not source.is_file():
            self.skipTest('Private native executable unavailable')
        report = inspect(source.read_bytes())
        self.assertEqual(report['row_pattern'], 'List/container%d')
        self.assertTrue(report['size_count_must_be_positive_before_insertion'])
        self.assertTrue(report['static_trace_only'])

    def test_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            inspect(b'wrong executable')
