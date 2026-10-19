from pathlib import Path
import unittest

from tools.verify_demae_size_fields import verify


class SizeFieldTests(unittest.TestCase):
    def source(self):
        path = Path(__file__).resolve().parents[1]/'private/demae/fixtures/HCHJ-local-api.dol'
        if not path.is_file():
            self.skipTest('Private native executable unavailable')
        return path.read_bytes()

    def values(self):
        # Synthetic harness inputs only; never published as restaurant data.
        return {'itemCode': 'VARIANT-TEST', 'size': '\u666e\u901a',
                'price': '1,280\u5186', 'isSoldout': 'unknown'}

    def test_owned_text_survives_source_overwrite(self):
        report = verify(self.source(), self.values())
        self.assertEqual(report['fields_verified'], 4)
        self.assertFalse(report['stock_semantics_verified'])
        self.assertFalse(report['native_rendering_verified'])

    def test_each_replacement_allocation_failure_clears_its_field(self):
        source = self.source()
        for key in self.values():
            with self.subTest(field=key):
                report = verify(source, self.values(), fail_field=key)
                self.assertTrue(report['replacement_failure_clears_field'])

    def test_invalid_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'wrong executable', self.values())
        source = self.source()
        with self.assertRaisesRegex(ValueError, 'all four'):
            verify(source, {})
        for value in ('', 'a\0b', 'a'*129, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'bounded'):
                    verify(source, {**self.values(), 'size': value})
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            verify(source, self.values(), fail_field='missing')
