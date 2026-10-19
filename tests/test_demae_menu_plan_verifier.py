from datetime import datetime, timezone
import unittest

from jwc24.demae_menu import menu_for
from tools.verify_demae_menu_plan import verify_menu


class MenuPlanVerifierTests(unittest.TestCase):
    def test_every_item_is_checked_across_phone_basket_limit(self):
        now = datetime.now(timezone.utc).isoformat()
        restaurant = {'id': 'hotpepper:J000000001', 'name': 'Source branch', 'address': 'Source address'}
        review = {'restaurant_id': restaurant['id'], 'provider_name': restaurant['name'],
            'provider_address': restaurant['address'], 'provider_url': 'https://demae-can.com/shop/menu/123',
            'verified_at': now}
        observation = {'restaurant_id': restaurant['id'], 'source_url': review['provider_url'],
            'observed_at': now, 'items': [{'name': f'Source item <{index}> 〗',
            'category': 'Source category', 'listed_price_yen': 100, 'options_observed': False}
            for index in range(51)]}
        result = verify_menu(menu_for(restaurant, review, observation))
        self.assertEqual(result['phone_basket_items_verified'], 51)
        self.assertEqual(result['phone_basket_pages_verified'], 2)
        self.assertEqual(result['listed_items_subtotal_yen'], 5100)
        self.assertIsNone(result['checkout_total_yen'])
        self.assertEqual(result['orders_submitted'], 0)
        self.assertEqual(result['notices_created'], 0)
