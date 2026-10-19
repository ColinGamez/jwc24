import json
import tempfile
import unittest
from pathlib import Path
from jwc24.rakuten import normalize, write_catalog
from jwc24.shop_catalog import indexed_shop_products

class ShopIdentityTests(unittest.TestCase):
    def products(self, codes):
        return normalize({'items': [{'itemCode': code, 'itemName': code, 'itemPrice': 100, 'itemUrl': 'https://example.com/'+code} for code in codes]})

    def test_legacy_refresh_reorder_insert_remove_and_return_preserve_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'catalog.json'
            path.write_text(json.dumps({'products': [{'item_code': 'a'}, {'item_code': 'b'}]}))
            write_catalog(path, 'refresh', self.products(['b', 'c', 'a']))
            first = json.loads(path.read_text())
            self.assertEqual([(p['item_code'], p['movie_id']) for p in first['products']], [('b',2),('c',3),('a',1)])
            write_catalog(path, 'removed', self.products(['a']))
            write_catalog(path, 'new', self.products(['d','b']))
            latest = json.loads(path.read_text())
            self.assertEqual([(p['item_code'], p['movie_id']) for p in latest['products']], [('d',4),('b',2)])
            self.assertEqual(latest['movie_id_high_water'], 4)
            self.assertEqual(latest['identity_registry']['c'], 3)

    def test_shared_filter_rejects_malformed_cached_numbers_without_renumbering(self):
        rows = [{'movie_id': 20, 'price_yen': 'bad'}, {'movie_id': 11, 'price_yen': None}, {'movie_id': 9, 'price_yen': True}, {'movie_id': 7, 'price_yen': '100', 'review_count': '2'}]
        self.assertEqual([identity for identity, _ in indexed_shop_products(rows)], [7])
        self.assertEqual([identity for identity, _ in indexed_shop_products([None, {'price_yen': 20000}, {'price_yen': 1}])], [2])

    def test_corrupt_previous_identity_state_preserves_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'catalog.json'
            original=json.dumps({'identity_registry': {'a': 1, 'b': 1}, 'products': []})
            path.write_text(original)
            with self.assertRaises(ValueError):
                write_catalog(path, 'refresh', self.products(['c']))
            self.assertEqual(path.read_text(), original)

    def test_concurrent_refreshes_retain_both_reserved_identities(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'catalog.json'
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda code: write_catalog(path, code, self.products([code])), ['a', 'b']))
            document = json.loads(path.read_text())
            self.assertEqual(set(document['identity_registry']), {'a','b'})
            self.assertEqual(set(document['identity_registry'].values()), {1,2})
            self.assertEqual(document['movie_id_high_water'], 2)

    def test_wrong_previous_document_shapes_raise_controlled_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'catalog.json'
            for previous in ([], None, {'products': None}, {'identity_registry': []}):
                with self.subTest(previous=previous):
                    original = json.dumps(previous)
                    path.write_text(original)
                    with self.assertRaises(ValueError):
                        write_catalog(path, 'refresh', self.products(['a']))
                    self.assertEqual(path.read_text(), original)

    def test_catalog_writer_works_without_tools_package(self):
        import shutil
        import subprocess
        import sys
        import jwc24
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(Path(jwc24.__file__).parent, root/'jwc24', ignore=shutil.ignore_patterns('__pycache__'))
            code = """import sys, builtins
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def packaged_import(name, *args, **kwargs):
    if name == 'tools' or name.startswith('tools.'):
        raise ModuleNotFoundError('tools package unavailable')
    return original_import(name, *args, **kwargs)
builtins.__import__ = packaged_import
from pathlib import Path
from jwc24.rakuten import write_catalog
write_catalog(Path(sys.argv[1])/'catalog.json', 'test', [])
"""
            result = subprocess.run([sys.executable, '-c', code, str(root)], cwd=root, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root/'catalog.json').exists())
