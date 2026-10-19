from datetime import datetime, timezone
from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest

from jwc24.demae_handoff import HandoffStore
from jwc24.demae_menu import menu_for
from tools.demae_phone_server import create_server


class BasketHandoffTests(unittest.TestCase):
    def menu(self):
        now = datetime.now(timezone.utc).isoformat()
        restaurant = {'id': 'hotpepper:J000000001', 'name': 'Source branch', 'address': 'Source address'}
        review = {'restaurant_id': restaurant['id'], 'provider_name': restaurant['name'],
                  'provider_address': restaurant['address'], 'verified_at': now,
                  'provider_url': 'https://demae-can.com/shop/menu/123'}
        observation = {'restaurant_id': restaurant['id'], 'source_url': review['provider_url'],
            'observed_at': now, 'items': [{'name': 'Item <A&B> 〗', 'category': 'Source category',
                 'listed_price_yen': 850, 'options_observed': False}]}
        return menu_for(restaurant, review, observation)

    def test_phone_page_keeps_branch_basket_and_does_not_confirm_or_dispatch(self):
        menu = self.menu()
        selections = [{'item_id': menu['items'][0]['id'], 'quantity': 2}]
        with tempfile.TemporaryDirectory() as temporary:
            store = HandoffStore(Path(temporary)/'handoff.sqlite')
            token = store.create('1234567890123456', restaurant=menu['restaurant'],
                                 menu=menu, selections=selections)
            reopened = HandoffStore(store.database)
            self.assertEqual(reopened.status(token)['basket_plan']['listed_items_subtotal_yen'], 1700)
            # A mail object with no methods proves GET never attempts dispatch.
            server = create_server('127.0.0.1', 0, reopened, object())
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/h/'+token)
                response = connection.getresponse()
                text = response.read().decode('utf-8')
                self.assertEqual(response.status, 200)
                self.assertIn('Item &lt;A&amp;B&gt;', text)
                self.assertIn('〗', text)
                self.assertIn('¥1,700', text)
                self.assertIn('Select these items again', text)
                self.assertIn('https://demae-can.com/shop/menu/123', text)
                self.assertFalse(reopened.status(token)['confirmed'])
                self.assertFalse(reopened.status(token)['notice_queued'])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_different_branch_and_selections_without_menu_rejected(self):
        menu = self.menu()
        selections = [{'item_id': menu['items'][0]['id'], 'quantity': 1}]
        with tempfile.TemporaryDirectory() as temporary:
            store = HandoffStore(Path(temporary)/'handoff.sqlite')
            other = dict(menu['restaurant'], provider_url='https://demae-can.com/shop/menu/456')
            with self.assertRaises(ValueError):
                store.create('1234567890123456', restaurant=other, menu=menu, selections=selections)
            with self.assertRaises(ValueError):
                store.create('1234567890123456', restaurant=menu['restaurant'], selections=selections)
