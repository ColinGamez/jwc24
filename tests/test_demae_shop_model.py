import importlib.util
from pathlib import Path
import unittest


@unittest.skipUnless(importlib.util.find_spec('unicorn'), 'Optional Unicorn dependency')
class ShopModelTests(unittest.TestCase):
    def test_native_list_preserves_all_162_rows_and_selection(self):
        from tools.verify_demae_shop_model import verify
        source = Path(__file__).resolve().parents[1] / 'private/demae/fixtures/HCHJ-local-api.dol'
        if not source.exists():
            self.skipTest('Private native executable unavailable')
        report = verify(source.read_bytes(), 162)
        self.assertEqual(report['native_rows_inserted'], 162)
        self.assertEqual(report['native_rows_selected'], 162)
        self.assertFalse(report['native_render_verified'])
