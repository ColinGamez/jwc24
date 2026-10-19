from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
import threading
import unittest
from urllib.parse import urlencode

from jwc24.demae_menu_directory import MenuDirectory
from tools.demae_fixture_server import create_server


class MenuHTTPTests(unittest.TestCase):
    def test_read_only_pages_branch_binding_and_expiry(self):
        now = datetime.now(timezone.utc)
        identifier = 'hotpepper:J000000001'
        missing = 'hotpepper:J000000002'
        catalog = {'provider': 'hotpepper', 'prefecture_id': 'JP-01', 'restaurants': [
            {'id': identifier, 'name': 'Branch', 'address': 'Address'},
            {'id': missing, 'name': 'Other', 'address': 'Other address'}]}
        review = {'restaurant_id': identifier, 'provider_name': 'Branch',
                  'provider_address': 'Address', 'provider_url': 'https://demae-can.com/shop/menu/1',
                  'verified_at': now.isoformat()}
        observation = {'restaurant_id': identifier, 'source_url': review['provider_url'],
            'observed_at': now.isoformat(), 'items': [
                {'name': f'Item {n}', 'category': 'A' if n % 2 else '\u3017B',
                 'listed_price_yen': 100+n, 'options_observed': False} for n in range(1, 14)]}
        directory = MenuDirectory([catalog], [review], [observation])
        server = create_server(menu_directory=directory)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()

        def request(parameters, method='GET', *, path='/preview/menu', body=None, headers=None):
            connection = HTTPConnection(*server.server_address, timeout=3)
            try:
                connection.request(method, path+('?' + urlencode(parameters) if parameters else ''),
                                   body=body, headers=headers or {})
                response = connection.getresponse()
                return response.status, response.read(), dict(response.getheaders())
            finally:
                connection.close()

        try:
            original = directory.menu(identifier)['items']
            received = []
            for page in (1, 2, 3):
                status, data, headers = request({'restaurant_id': identifier, 'page': page})
                self.assertEqual(status, 200)
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertIn('application/json', headers['Content-Type'])
                result = json.loads(data)
                received.extend(result['items'])
                self.assertEqual(result['restaurant']['restaurant_id'], identifier)
                self.assertFalse(result['ordering_supported'])
                self.assertFalse(result['native_menu_integrated'])
            self.assertEqual(received, original)
            status, data, _ = request({'restaurant_id': identifier, 'category': '\u3017B'})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(data)['items'], [i for i in original if i['category'] == '\u3017B'])
            for parameters, expected in (
                ({}, 400), ({'restaurant_id': 'bad'}, 400),
                ({'restaurant_id': identifier, 'page': 0}, 400),
                ([('restaurant_id', identifier), ('page', 1), ('page', 2)], 400),
                ({'restaurant_id': identifier, 'extra': ''}, 400),
                ({'restaurant_id': 'hotpepper:J000000099'}, 404),
                ({'restaurant_id': missing}, 409),
                ({'restaurant_id': identifier, 'page': 4}, 409),
                ({'restaurant_id': identifier, 'page_size': 21}, 409),
                ({'restaurant_id': identifier, 'category': 'unknown'}, 409)):
                with self.subTest(parameters=parameters):
                    self.assertEqual(request(parameters)[0], expected)
            self.assertEqual(request({'restaurant_id': identifier}, 'POST')[0], 405)
            def basket(value, **kwargs):
                return request({}, 'POST', path='/preview/basket', body=json.dumps(value),
                               headers={'Content-Type': 'application/json', **kwargs})

            selection = {'restaurant_id': identifier,
                         'selections': [{'item_id': original[6]['id'], 'quantity': 3}]}
            status, data, headers = basket(selection)
            self.assertEqual(status, 200)
            plan = json.loads(data)
            self.assertEqual(plan['listed_items_subtotal_yen'], 3*original[6]['listed_price_yen'])
            self.assertEqual(plan['lines'][0]['item_id'], original[6]['id'])
            self.assertIsNone(plan['checkout_total_yen'])
            self.assertFalse(plan['provider_basket_transferred'])
            self.assertFalse(plan['ordering_supported'])
            self.assertNotIn('token', plan)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            for selections in ([], [{'item_id': 'observed:another-branch', 'quantity': 1}],
                               [{'item_id': original[0]['id'], 'quantity': True}],
                               [selection['selections'][0]]*2):
                self.assertEqual(basket(dict(selection, selections=selections))[0], 409)
            self.assertEqual(basket(dict(selection, restaurant_id='hotpepper:J000000099'))[0], 404)
            self.assertEqual(basket(dict(selection, extra='unexpected'))[0], 400)
            self.assertEqual(basket(selection, Origin='http://other.invalid')[0], 403)
            self.assertEqual(request({}, 'POST', path='/preview/basket', body='{}',
                                     headers={'Content-Type': 'text/plain'})[0], 400)
            self.assertEqual(request({}, 'POST', path='/preview/basket',
                body='{"restaurant_id":"x","restaurant_id":"y","selections":[]}',
                headers={'Content-Type': 'application/json'})[0], 400)
            directory.observations[identifier]['observed_at'] = (now-timedelta(days=2)).isoformat()
            self.assertEqual(request({'restaurant_id': identifier})[0], 409)
            self.assertEqual(basket(selection)[0], 409)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
