from datetime import datetime, timedelta, timezone
import unittest
from jwc24.demae_restaurant_links import resolve_reviewed_link, provider_shop_url
from tools.build_demae_restaurant_links import build

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)


class RestaurantLinkTests(unittest.TestCase):
    def records(self):
        restaurant = {'id': 'hotpepper:J000000001', 'name': 'Branch A',
                      'address': 'City 4\u4e01\u76ee1-2 Building B1'}
        review = {'restaurant_id': restaurant['id'], 'provider_name': 'Branch\u3000A',
                  'provider_address': 'City 4-1-2 Building B1',
                  'provider_url': 'https://demae-can.com/shop/menu/1234567',
                  'verified_at': NOW.isoformat()}
        return restaurant, review

    def test_same_branch_uses_reviewed_shop_page(self):
        restaurant, review = self.records()
        result = resolve_reviewed_link(restaurant, review, now=NOW)
        self.assertEqual(result['provider_url'], review['provider_url'])
        self.assertEqual(result['restaurant_id'], restaurant['id'])

    def test_same_chain_wrong_branch_is_rejected(self):
        restaurant, review = self.records()
        for field, value in [('provider_address', 'City 4-1-3 Building B1'),
                             ('provider_name', 'Branch B'), ('restaurant_id', 'hotpepper:J000000002')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                resolve_reviewed_link(restaurant, dict(review, **{field: value}), now=NOW)

    def test_reviewed_lot_label_and_floor_formatting_preserve_location_numbers(self):
        restaurant, review = self.records()
        for left, right in [('City 849 Building 3階', 'City 849番地 Building 3階'),
                            ('City 2-3-7 Building III 1Ｆ', 'City 2丁目3-7 Building Ⅲ 1階')]:
            result = resolve_reviewed_link(dict(restaurant, address=left),
                                          dict(review, provider_address=right), now=NOW)
            self.assertEqual(result['restaurant_id'], restaurant['id'])
        for right in ('City 850番地 Building 3階', 'City 849番地 Building 4階',
                      'City 849番地2 Building 3階'):
            with self.assertRaises(ValueError):
                resolve_reviewed_link(dict(restaurant, address='City 849 Building 3階'),
                                      dict(review, provider_address=right), now=NOW)

    def test_reviews_need_recent_timezone_aware_dates(self):
        restaurant, review = self.records()
        for date in [(NOW-timedelta(days=31)).isoformat(),
                     (NOW+timedelta(seconds=1)).isoformat(), '2026-10-15', None]:
            with self.subTest(date=date), self.assertRaises(ValueError):
                resolve_reviewed_link(restaurant, dict(review, verified_at=date), now=NOW)

    def test_reviewed_katakana_vowel_mark_preserves_lot_and_building_identity(self):
        restaurant, review = self.records()
        restaurant['address'] = 'City 2-53 セントラルアークビル 5F'
        review['provider_address'] = 'City 2-53 セントラルア－クビル 5階'
        self.assertEqual(resolve_reviewed_link(restaurant, review, now=NOW)['restaurant_id'], restaurant['id'])
        for address in ('City 2-54 セントラルア－クビル 5階',
                        'City 2-53 セントラルア－クビル別館 5階',
                        'City 2-53 セントラルア－クビル 6階'):
            with self.assertRaises(ValueError):
                resolve_reviewed_link(restaurant, dict(review, provider_address=address), now=NOW)

    def test_only_direct_official_shop_pages_allowed(self):
        for url in ['http://demae-can.com/shop/menu/1', 'https://demae-can.com.evil/shop/menu/1',
                    'https://user@demae-can.com/shop/menu/1', 'https://demae-can.com:443/shop/menu/1',
                    'https://demae-can.com/shop/menu/1?next=evil', 'https://demae-can.com/',
                    'https://demae-can.com/shop/menu/1#x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                provider_shop_url(url)

    def test_curated_index_cannot_reuse_one_branch_for_multiple_entries(self):
        restaurant, review = self.records()
        review['verified_at'] = datetime.now(timezone.utc).isoformat()
        other = dict(restaurant, id='hotpepper:J000000002')
        catalogs = [{'provider': 'hotpepper', 'restaurants': [restaurant, other]}]
        with self.assertRaises(ValueError):
            build(catalogs, [review, dict(review, restaurant_id=other['id'])])
        with self.assertRaises(ValueError):
            build(catalogs, [dict(review, restaurant_id='hotpepper:J000000003')])
        result = build(catalogs, [review])
        self.assertEqual(len(result['reviewed_links']), 1)
        self.assertFalse(result['native_navigation_integrated'])


if __name__ == '__main__':
    unittest.main()
