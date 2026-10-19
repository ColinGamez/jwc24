from datetime import datetime, timedelta, timezone
import unittest

from jwc24.demae_menu import menu_for, basket_plan


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 18, tzinfo=timezone.utc)
        self.restaurant = {'id': 'hotpepper:J000000001', 'name': 'Source branch', 'address': 'Source address'}
        self.review = {'restaurant_id': self.restaurant['id'], 'provider_name': 'Source branch',
            'provider_address': 'Source address', 'provider_url': 'https://demae-can.com/shop/menu/123',
            'verified_at': self.now.isoformat()}
        self.observation = {'restaurant_id': self.restaurant['id'], 'source_url': self.review['provider_url'],
            'observed_at': self.now.isoformat(), 'items': [
                {'name': 'Source item', 'category': 'Source category', 'listed_price_yen': 850,
                 'options_observed': False}]}

    def menu(self, observation=None):
        return menu_for(self.restaurant, self.review, observation or self.observation, now=self.now)

    def test_observed_menu_and_basket_do_not_claim_checkout_or_delivery(self):
        menu = self.menu()
        self.assertIsNone(menu['items'][0]['provider_item_id'])
        plan = basket_plan(menu, [{'item_id': menu['items'][0]['id'], 'quantity': 3}], now=self.now)
        self.assertEqual(plan['listed_items_subtotal_yen'], 2550)
        self.assertIsNone(plan['checkout_total_yen'])
        self.assertIsNone(plan['delivery_available'])
        self.assertFalse(plan['provider_basket_transferred'])
        self.assertFalse(plan['ordering_supported'])

    def test_wrong_branch_stale_future_and_unreviewed_identity_rejected(self):
        for change in ({'restaurant_id': 'hotpepper:J000000002'},
                       {'source_url': 'https://demae-can.com/shop/menu/456'},
                       {'observed_at': (self.now-timedelta(days=2)).isoformat()},
                       {'observed_at': (self.now+timedelta(seconds=1)).isoformat()},
                       {'observed_at': '2026-10-18T00:00:00'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.menu(dict(self.observation, **change))
        with self.assertRaises(ValueError):
            menu_for(dict(self.restaurant, address='Another address'), self.review,
                     self.observation, now=self.now)

    def test_ambiguous_price_options_and_duplicate_items_rejected(self):
        row = self.observation['items'][0]
        for changes in ({'listed_price_yen': True}, {'listed_price_yen': '850'},
                        {'listed_price_yen': 0}, {'options_observed': None}, {'name': 'bad\nname'},
                        {'name': '\ud800'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.menu(dict(self.observation, items=[dict(row, **changes)]))
        with self.assertRaises(ValueError):
            self.menu(dict(self.observation, items=[row, row]))

    def test_unicode_source_names_are_preserved_and_native_encoding_gap_is_explicit(self):
        source = '458〗並にぎり'
        observation = dict(self.observation, items=[dict(self.observation['items'][0], name=source)])
        menu = self.menu(observation)
        self.assertEqual(menu['items'][0]['name'], source)
        self.assertFalse(menu['items'][0]['cp932_labels'])
        self.assertFalse(menu['cp932_labels'])
        plan = basket_plan(menu, [{'item_id': menu['items'][0]['id'], 'quantity': 1}], now=self.now)
        self.assertEqual(plan['lines'][0]['name'], source)
        self.assertFalse(plan['ordering_supported'])

    def test_basket_rejects_unknown_duplicates_quantities_and_expired_menu(self):
        menu = self.menu()
        choice = {'item_id': menu['items'][0]['id'], 'quantity': 1}
        for selections in ([], [dict(choice, item_id='unknown')], [choice, choice],
                           [dict(choice, quantity=True)], [dict(choice, quantity=21)],
                           [dict(choice, quantity=0)], [dict(choice, price=1)]):
            with self.subTest(selections=selections), self.assertRaises(ValueError):
                basket_plan(menu, selections, now=self.now)
        with self.assertRaises(ValueError):
            basket_plan(menu, [choice], now=self.now+timedelta(days=2))
