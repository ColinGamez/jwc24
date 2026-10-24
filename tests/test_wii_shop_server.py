from http.client import HTTPConnection
import json
import threading
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs

from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_server import Application, create_server
from tests.test_wii_shop_browse import record
from tests import test_wii_shop_title_metadata as metadata_fixture
from jwc24.wii_shop_title_metadata import TitleMetadata


class DataRenderer:
    """Expose controller inputs to tests without proprietary page fixtures."""
    page_size = 4

    def home(self, count):
        return str(count).encode()

    def browse(self, result, options):
        return json.dumps({'result': result, 'options': options}).encode()

    def detail(self, item, options):
        return json.dumps({'item': item, 'options': options}).encode()

    def about(self):
        return b'about'


class ShopPreviewServerTests(unittest.TestCase):
    def setUp(self):
        self.rows = [record(f'00010001{i:08X}', f'Game {i:02}', is_demo=i % 2 == 0)
                     for i in range(13)]
        self.app = Application(Catalog(self.rows), artwork=DataRenderer())

    def test_catalog_pagination_reaches_every_title_once(self):
        target, seen = '/catalog', []
        while target:
            status, _, body = self.app.get(target)
            self.assertEqual(status, 200)
            result = json.loads(body)['result']
            seen.extend(item['title_id'] for item in result['items'])
            target = '/catalog?offset='+str(result['next_offset']) if result['next_offset'] is not None else None
        self.assertEqual(len(seen), 13)
        self.assertEqual(set(seen), {row['title_id'] for row in self.rows})

    def test_filters_and_detail_back_link_preserve_query(self):
        status, _, body = self.app.get('/catalog?demos=only&q=Game&offset=4')
        self.assertEqual(status, 200)
        item = json.loads(body)['result']['items'][0]
        target = '/title/'+item['title_id']+'?demos=only&q=Game&offset=4'
        status, _, detail = self.app.get(target)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(detail)['options'], {'q': 'Game', 'category': None, 'demos': 'only', 'offset': 4})
        self.assertNotIn(b'.wad', detail)
        self.assertNotIn(b'onBuyButtonPressed', detail)

    def test_unknown_title_is_not_invented_and_artwork_is_required(self):
        self.assertEqual(self.app.get('/title/00010001FFFFFFFF')[0], 404)
        with self.assertRaisesRegex(ValueError, 'artwork'):
            Application(Catalog(self.rows))

    def test_ready_report_does_not_accept_unbounded_or_repeated_fields(self):
        self.assertEqual(self.app.get('/ready?w=640&h=480&bridge=1&music=1', 'opera')[0], 204)
        status = json.loads(self.app.get('/healthz')[2])
        self.assertEqual(status['last_ready'], {'w': 640, 'h': 480, 'bridge': 1, 'music': 1, 'agent': 'opera'})
        self.app.get('/ready?w=608&h=456&bridge=1&music=1&keyboard=1', 'opera')
        self.assertEqual(json.loads(self.app.get('/healthz')[2])['last_ready']['keyboard'], 1)
        for target in ('/ready?w=0&h=480&bridge=1&music=1', '/catalog?offset=-1',
                       '/catalog?q=a&q=b', '/catalog?offset=4294967296',
                       '/catalog?category=Invalid', '/catalog?q='+'a'*121,
                       '/ready?w=608&h=456&bridge=1&music=1&keyboard=2'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.app.get(target)

    def test_http_framing_head_and_rejected_post_on_live_listener(self):
        server = create_server(('127.0.0.1', 0), self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection(*server.server_address, timeout=3)
        try:
            for method, target, expected in (('GET', '/', 200), ('GET', '/catalog', 200),
                                             ('HEAD', '/catalog', 200), ('GET', '/missing', 404),
                                             ('POST', '/catalog', 405)):
                connection.request(method, target)
                response = connection.getresponse()
                data = response.read()
                self.assertEqual(response.status, expected)
                if method != 'POST':
                    self.assertFalse(response.will_close)
                self.assertEqual(len(data), 0 if method == 'HEAD' else int(response.getheader('Content-Length')))
            self.assertEqual(len(self.app.events), 4)
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(3)

    def test_listener_rejects_non_loopback_binding(self):
        with self.assertRaises(ValueError):
            create_server(('0.0.0.0', 0), self.app)

    def test_historical_group_filters_preserve_detail_context_and_reject_unmapped_genre_codes(self):
        fixture = metadata_fixture.HistoricalTitleMetadataTests()
        with tempfile.TemporaryDirectory() as directory:
            metadata = TitleMetadata(fixture.metadata(Path(directory)), 'a'*64)
            app = Application(Catalog([record(category_label='Virtual Console')], title_metadata=metadata), artwork=DataRenderer())
            filters = {'publisher':'Example & Co', 'platform':'VCA', 'display_genre':'Action',
                       'category':'Virtual Console'}
            from urllib.parse import urlencode
            query = urlencode(filters)
            result = json.loads(app.get('/catalog?'+query)[2])
            self.assertEqual(result['result']['total'], 1)
            identifier = result['result']['items'][0]['title_id']
            detail = json.loads(app.get('/title/'+identifier+'?'+query)[2])
            for key, value in filters.items():
                self.assertEqual(detail['options'][key], value)
            self.assertEqual(json.loads(app.get('/catalog?publisher=Missing')[2])['result']['total'], 0)
            for target in ('/catalog?genre=ACTION','/catalog?publisher=a&publisher=b','/catalog?display_genre='):
                with self.assertRaises(ValueError):
                    app.get(target)
