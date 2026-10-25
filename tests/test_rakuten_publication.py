"""Catalog publication regressions without provider calls or private assets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import jwc24
from jwc24 import rakuten


class RakutenPublicationTests(unittest.TestCase):
    def product(self, code='synthetic:a', *, review_average=0):
        return rakuten.Product(code, 'Synthetic product', 100, '',
                               'https://example.invalid/product', '', '', '',
                               0, review_average, True)

    def test_failed_replace_preserves_previous_catalog_and_removes_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            original = b'{"products": []}'
            path.write_bytes(original)
            with patch.object(rakuten.os, 'replace', side_effect=OSError('synthetic disk failure')):
                with self.assertRaises(OSError):
                    rakuten.write_catalog(path, 'synthetic', [self.product()])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob('.rakuten-*')), [])

    def test_unserializable_nonfinite_values_do_not_publish_partial_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            original = b'{"products": []}'
            path.write_bytes(original)
            for value in (float('nan'), float('inf'), float('-inf')):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    rakuten.write_catalog(path, 'synthetic', [self.product(review_average=value)])
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(list(path.parent.glob('.rakuten-*')), [])

    def test_transient_windows_reader_conflict_retries_the_same_complete_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            original_replace = os.replace
            attempts = []

            def replace(source, destination):
                attempts.append(source)
                document = json.loads(Path(source).read_text(encoding='utf-8'))
                self.assertEqual(document['products'][0]['movie_id'], 1)
                if len(attempts) < 3:
                    error = PermissionError('synthetic sharing violation')
                    error.winerror = 32
                    raise error
                original_replace(source, destination)

            with patch.object(rakuten.os, 'replace', side_effect=replace), \
                    patch.object(rakuten.time, 'sleep') as sleep:
                rakuten.write_catalog(path, 'synthetic', [self.product()])
            self.assertEqual(len(attempts), 3)
            self.assertEqual(len(set(attempts)), 1)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(list(path.parent.glob('.rakuten-*')), [])
            self.assertEqual(json.loads(path.read_text())['identity_registry'], {'synthetic:a': 1})

    def test_separate_publishers_preserve_both_reserved_identities(self):
        package_root = str(Path(jwc24.__file__).resolve().parent.parent)
        script = """import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from jwc24.rakuten import Product, write_catalog
code = sys.argv[3]
product = Product(code, 'Synthetic product', 100, '', 'https://example.invalid/item', '', '', '', 0, 0, True)
for _ in range(12):
    write_catalog(Path(sys.argv[2]), 'synthetic', [product])
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            children = []
            try:
                for code in ('synthetic:a', 'synthetic:b'):
                    children.append(subprocess.Popen(
                        [sys.executable, '-c', script, package_root, str(path), code],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    ))
                for child in children:
                    _stdout, stderr = child.communicate(timeout=20)
                    self.assertEqual(child.returncode, 0, stderr)
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                        child.communicate(timeout=5)
            document = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(set(document['identity_registry']), {'synthetic:a', 'synthetic:b'})
            self.assertEqual(set(document['identity_registry'].values()), {1, 2})
            self.assertEqual(document['movie_id_high_water'], 2)
            self.assertEqual(list(path.parent.glob('.rakuten-*')), [])


if __name__ == '__main__':
    unittest.main()
