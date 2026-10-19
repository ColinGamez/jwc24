import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jwc24.demae_regions import prefectures
from tools import import_hotpepper_regions as importer


class NationwideImportTests(unittest.TestCase):
    def test_all_regions_resume_without_refetch_and_keep_key_out_of_cache(self):
        master = {'results': {'large_area': [{'name': r['name'], 'code': f'Z{i:03d}'}
                   for i, r in enumerate(prefectures())]}}
        with tempfile.TemporaryDirectory() as directory:
            fake_script = Path(directory) / 'tools/script.py'
            cache = Path(directory) / 'private/demae/hotpepper'
            def fetch(**kwargs):
                return {'query': {'large_area': kwargs['large_area'], 'start': kwargs['start'], 'count': 100}, 'restaurants': []}
            with patch.object(importer, '__file__', str(fake_script)), \
                 patch.dict('os.environ', {importer.KEY_ENV: 'private-test-key'}), \
                 patch.object(importer, 'urlopen', side_effect=lambda *a, **k: io.BytesIO(json.dumps(master).encode())), \
                 patch.object(importer, 'fetch_catalog', side_effect=fetch) as provider, \
                 patch.object(importer.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(importer.main(['--pages', '1']), 0)
                self.assertEqual(provider.call_count, 47)
                self.assertEqual(importer.main(['--pages', '1']), 0)
                self.assertEqual(provider.call_count, 47)
            result = json.loads((cache / 'regions.json').read_text(encoding='utf-8'))
            self.assertEqual(len(result['regions']), 47)
            self.assertFalse(result['native_coverage_verified'])
            self.assertNotIn('private-test-key', (cache / 'regions.json').read_text(encoding='utf-8'))

    def test_pagination_stops_at_total_and_deduplicates_overlapping_pages(self):
        region = {'id': 'JP-10', 'provider_area_code': 'Z024'}
        with tempfile.TemporaryDirectory() as directory:
            def fetch(**kwargs):
                start = kwargs['start']
                return {'schema_version': 2, 'query': {'large_area': 'Z024', 'start': start, 'count': 100},
                        'restaurants': [{'id': 'same'}, {'id': str(start)}],
                        'pagination': {'results_available': 102, 'results_returned': 2 if start == 101 else 100}}
            with patch.object(importer, '__file__', str(Path(directory) / 'tools/script.py')), \
                 patch.dict('os.environ', {importer.KEY_ENV: 'key'}), \
                 patch.object(importer, 'urlopen', side_effect=lambda *a, **k: io.BytesIO(b'{"results":{"large_area":[]}}')), \
                 patch.object(importer, 'match_provider_areas', return_value=[region]), \
                 patch.object(importer, 'fetch_catalog', side_effect=fetch) as provider, \
                 patch.object(importer.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(importer.main(['--pages', '5']), 0)
                self.assertEqual(importer.main([]), 0)
                self.assertEqual(provider.call_count, 2)
                cache = Path(directory) / 'private/demae/hotpepper'
                nationwide_before = (cache / 'regions.json').read_bytes()
                for page_path in cache.glob('JP-10-page*.json'):
                    page_document = json.loads(page_path.read_text(encoding='utf-8'))
                    page_document['schema_version'] = 1
                    page_path.write_text(json.dumps(page_document), encoding='utf-8')
                self.assertEqual(importer.main(['--prefecture', 'JP-10', '--upgrade-schema']), 0)
                self.assertEqual((cache / 'regions.json').read_bytes(), nationwide_before)
            self.assertEqual(provider.call_count, 4)
            self.assertEqual(region['cached_restaurants'], 3)
            self.assertEqual(region['catalog_status'], 'provider_pages_complete')

    def test_cache_identity_requires_matching_offset_and_shape(self):
        page = {'query': {'large_area': 'Z024', 'start': 101, 'count': 100},
                'restaurants': [{'id': 'hotpepper:J000000001'}]}
        self.assertTrue(importer.reusable_page(page, 'Z024', 101))
        self.assertFalse(importer.reusable_page(page, 'Z024', 1))
        self.assertFalse(importer.reusable_page(page, 'Z025', 101))
        for invalid in (None, {}, {'query': []}, {**page, 'restaurants': [None]},
                        {**page, 'restaurants': [{'name': 'missing ID'}]}):
            self.assertFalse(importer.reusable_page(invalid, 'Z024', 101))
        for metadata in ([], {'results_returned': True}, {'results_returned': -1},
                         {'results_returned': 101}, {'results_start': 1},
                         {'results_returned': 0}, {'results_available': '200'}):
            self.assertFalse(importer.reusable_page({**page, 'pagination': metadata}, 'Z024', 101))
