import json
from pathlib import Path
import tempfile
import unittest
from tools.build_demae_catalog_categories import build_catalog_categories


class CategoryPublicationTests(unittest.TestCase):
    def test_manifest_retires_stale_fixtures_and_bad_region_preserves_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'hotpepper'
            cache.mkdir()
            for n in range(1, 48):
                identity = f'JP-{n:02d}'
                (cache / (identity + '-catalog.json')).write_text(json.dumps({
                    'prefecture_id': identity, 'restaurants': [{'id': str(n), 'genre': '和食'}]}), encoding='utf-8')
            self.assertEqual(build_catalog_categories(root)['exact_label_matches'], 47)
            manifest_path = root / 'fixtures/catalog-categories/manifest.json'
            changed = cache / 'JP-01-catalog.json'
            changed.write_text(json.dumps({'prefecture_id': 'JP-01',
                                           'restaurants': [{'id': '1', 'genre': 'unknown'}]}), encoding='utf-8')
            build_catalog_categories(root)
            manifest = json.loads(manifest_path.read_text())
            self.assertNotIn('JP-01', manifest['active_fixtures'])
            before = manifest_path.read_bytes()
            changed.write_text(json.dumps({'prefecture_id': 'JP-99', 'restaurants': []}), encoding='utf-8')
            with self.assertRaises(ValueError):
                build_catalog_categories(root)
            self.assertEqual(manifest_path.read_bytes(), before)
