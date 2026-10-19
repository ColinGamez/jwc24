import io
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from jwc24.demae_regions import prefectures, match_provider_areas
from jwc24.hotpepper import fetch_catalog, HotPepperError


class RegionTests(unittest.TestCase):
    def test_all_prefectures_unique_and_no_native_support_inferred(self):
        rows = prefectures()
        self.assertEqual([r['id'] for r in rows], [f'JP-{i:02d}' for i in range(1, 48)])
        self.assertEqual(rows[9]['name'], '群馬県')
        self.assertEqual(rows[-1]['name'], '沖縄県')
        self.assertTrue(all(r['native_area_code'] is None and not r['ordering_supported'] for r in rows))

    def test_master_exact_matching_missing_and_duplicates_rejected(self):
        master = [{'name': r['name'], 'code': f'Z{i:03d}'} for i, r in enumerate(prefectures())]
        self.assertEqual(len(match_provider_areas(master)), 47)
        for bad in (master[:-1], master + [master[0]], master + [{'name': '群馬', 'code': 'Z999'}]):
            with self.assertRaises(ValueError):
                match_provider_areas(bad)

    def test_area_query_does_not_require_keyword_or_expose_key(self):
        with patch('jwc24.hotpepper.urlopen', return_value=io.BytesIO(b'{"results":{"shop":[]}}')) as opener:
            result = fetch_catalog(large_area='Z011', api_key='secret')
        query = parse_qs(urlsplit(opener.call_args.args[0].full_url).query)
        self.assertEqual(query['large_area'], ['Z011'])
        self.assertNotIn('keyword', query)
        self.assertNotIn('secret', str(result))
        with self.assertRaises(HotPepperError):
            fetch_catalog(large_area='JP-10', api_key='secret')
