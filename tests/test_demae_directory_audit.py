import unittest
from types import SimpleNamespace

from tools.audit_demae_directory import audit


class DirectoryAuditTests(unittest.TestCase):
    def test_every_source_row_is_reported_even_when_not_browsable(self):
        first = {'id': 'hotpepper:J000000001', 'name': 'Source name',
                 'address': 'Source address', 'genre': '居酒屋',
                 'catchphrase': '', 'logo_url': None}
        second = dict(first, id='hotpepper:J000000002', genre='unknown genre')
        third = dict(first, id='hotpepper:J000000003')
        directory = SimpleNamespace(restaurants={'10202': {'11': [first]}})
        report = audit([{'provider': 'hotpepper', 'prefecture_id': 'JP-10',
                         'restaurants': [first, second, third]}], directory,
                       [{'restaurant_ids': [first['id']]}])
        self.assertEqual(report['summary']['restaurants'], 3)
        self.assertEqual(report['summary']['not_staged'], 2)
        self.assertEqual(report['summary']['unmapped_genre'], 1)
        self.assertEqual(report['summary']['unresolved_municipality'], 1)
        self.assertEqual(report['summary']['missing_source_image'], 3)
        self.assertEqual(len(report['restaurants']), 3)
        self.assertFalse(report['native_render_verified'])
        self.assertFalse(report['nationwide_browsing_ready'])
        self.assertFalse(report['source_image_downloads_verified'])
        self.assertFalse(report['ordering_supported'])

    def test_large_groups_are_flagged_without_silent_truncation(self):
        rows = [{'id': f'hotpepper:J{number:09d}', 'name': 'Source name',
                 'address': 'Source address', 'genre': '和食', 'catchphrase': ''}
                for number in range(26)]
        report = audit([{'provider': 'hotpepper', 'prefecture_id': 'JP-10',
                         'restaurants': rows}],
                       SimpleNamespace(restaurants={'10202': {'04': rows}}), [])
        self.assertEqual(report['large_groups'], [{'municipality': '10202',
            'category': '04', 'restaurants': 26, 'needs_pagination': True}])
        self.assertEqual(len(report['restaurants']), 26)
