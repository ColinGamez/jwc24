from datetime import datetime, timedelta, timezone
import unittest

from jwc24.demae_menu_directory import MenuDirectory


class MenuDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 18, tzinfo=timezone.utc)
        self.catalogs, self.reviews, self.observations = [], [], []
        for number in range(1, 48):
            identifier = f'hotpepper:J{number:09d}'
            self.catalogs.append({'provider': 'hotpepper', 'prefecture_id': f'JP-{number:02d}',
                'restaurants': [{'id': identifier, 'name': 'Source branch', 'address': f'Source address {number}'}]})
            if number in (1, 10, 13):
                self.reviews.append({'restaurant_id': identifier, 'provider_name': 'Source branch',
                    'provider_address': f'Source address {number}', 'verified_at': self.now.isoformat(),
                    'provider_url': f'https://demae-can.com/shop/menu/{number}'})
                self.observations.append({'restaurant_id': identifier,
                    'source_url': f'https://demae-can.com/shop/menu/{number}',
                    'observed_at': self.now.isoformat(), 'items': [{'name': 'Source item',
                    'category': 'Source category', 'listed_price_yen': 850+number,
                    'options_observed': False}]})

    def directory(self):
        return MenuDirectory(self.catalogs, self.reviews, self.observations)

    def test_all_47_prefectures_preserve_menu_gaps_and_branch_specific_prices(self):
        directory = self.directory()
        report = directory.coverage(now=self.now)
        self.assertEqual(len(report['prefectures']), 47)
        self.assertEqual(len(report['restaurants']), 47)
        self.assertEqual(report['menu_plan_restaurants'], 3)
        self.assertEqual(report['observed_menu_items'], 3)
        self.assertFalse(report['ordering_supported'])
        for number in (1, 10, 13):
            identifier = f'hotpepper:J{number:09d}'
            menu = directory.menu(identifier, now=self.now)
            plan = directory.plan(identifier, [{'item_id': menu['items'][0]['id'], 'quantity': 2}], now=self.now)
            self.assertEqual(plan['listed_items_subtotal_yen'], 2*(850+number))
        with self.assertRaisesRegex(ValueError, 'Missing reviewed provider branch'):
            directory.menu('hotpepper:J000000047', now=self.now)

    def test_expiry_is_rechecked_without_restarting_directory(self):
        directory = self.directory()
        self.assertEqual(directory.coverage(now=self.now)['menu_plan_restaurants'], 3)
        later = self.now+timedelta(days=2)
        self.assertEqual(directory.coverage(now=later)['menu_plan_restaurants'], 0)
        with self.assertRaises(ValueError):
            directory.menu('hotpepper:J000000001', now=later)

    def test_no_branch_cloning_or_unknown_source_records(self):
        self.reviews[1]['provider_url'] = self.reviews[0]['provider_url']
        with self.assertRaises(ValueError):
            self.directory()
        self.setUp()
        self.observations.append(dict(self.observations[0], restaurant_id='hotpepper:J999999999'))
        with self.assertRaises(ValueError):
            self.directory()
        self.setUp()
        self.observations[0]['source_url'] = self.observations[1]['source_url']
        report = self.directory().coverage(now=self.now)
        self.assertEqual(report['menu_plan_restaurants'], 2)
        self.assertIn('different provider branch', report['restaurants'][0]['issues'][0])

    def test_source_snapshots_cannot_be_changed_after_indexing(self):
        directory = self.directory()
        self.observations[0]['items'][0]['listed_price_yen'] = 1
        self.assertEqual(directory.menu('hotpepper:J000000001', now=self.now)['items'][0]['listed_price_yen'], 851)

    def test_menu_pages_replay_all_items_and_filter_without_changing_identity(self):
        self.observations[0]['items'] = [
            {'name': f'Item {n}', 'category': 'A' if n % 2 else 'B',
             'listed_price_yen': 100+n, 'options_observed': False}
            for n in range(1, 24)]
        directory = self.directory()
        identifier = 'hotpepper:J000000001'
        original = directory.menu(identifier, now=self.now)['items']
        pages = [directory.menu_page(identifier, page=n, now=self.now) for n in range(1, 5)]
        self.assertEqual([item for p in pages for item in p['items']], original)
        self.assertEqual([len(p['items']) for p in pages], [6, 6, 6, 5])
        self.assertIsNone(pages[0]['previous_page'])
        self.assertIsNone(pages[-1]['next_page'])
        self.assertEqual(pages[0]['next_page'], 2)
        self.assertEqual(pages[-1]['previous_page'], 3)
        filtered = [directory.menu_page(identifier, page=n, category='A', now=self.now)
                    for n in (1, 2)]
        self.assertEqual([item for p in filtered for item in p['items']],
                         [item for item in original if item['category'] == 'A'])
        self.assertEqual(filtered[0]['categories'], ['A', 'B'])
        self.assertEqual(filtered[0]['total_items'], 12)
        self.assertFalse(filtered[0]['complete_menu'])
        self.assertFalse(filtered[0]['ordering_supported'])
        for kwargs in ({'page': 5}, {'page': True}, {'page': 0}, {'page_size': 21},
                       {'page_size': False}, {'category': 'unknown'}, {'category': []}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                directory.menu_page(identifier, now=self.now, **kwargs)
        with self.assertRaisesRegex(ValueError, '24 hours'):
            directory.menu_page(identifier, page=2, now=self.now+timedelta(days=2))
        with self.assertRaisesRegex(ValueError, 'Missing reviewed'):
            directory.menu_page('hotpepper:J000000047', now=self.now)
