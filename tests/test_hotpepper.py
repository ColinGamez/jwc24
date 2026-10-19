import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from jwc24.hotpepper import HotPepperError, MAX_RESPONSE_BYTES, fetch_catalog, normalize_response
from tools.import_hotpepper_catalog import main


def response_bytes(shops=None):
    if shops is None:
        shops = [{'id': 'J123456789', 'name': '高崎 テスト店', 'address': '群馬県高崎市',
                  'genre': {'name': '和食'}, 'budget': {'name': '3001～4000円'},
                  'photo': {'pc': {'l': 'https://example.com/photo.jpg'}},
                  'urls': {'pc': 'https://example.com/shop'}, 'lat': '36.32', 'lng': '139.01'}]
    return json.dumps({'results': {'shop': shops}}, ensure_ascii=False).encode('utf-8')


class HotPepperTests(unittest.TestCase):
    def test_preserves_provider_genre_identity_and_real_promotion_fields(self):
        catalog = normalize_response(response_bytes([{'id': 'J123456789', 'name': 'Test',
            'genre': {'code': 'G001', 'name': 'Genre', 'catch': 'Genre description'},
            'sub_genre': {'code': 'G002'}, 'catch': 'Actual provider text',
            'logo_image': 'https://example.com/logo.jpg'}]))
        row = catalog['restaurants'][0]
        self.assertEqual(catalog['schema_version'], 2)
        self.assertEqual(row['genre_code'], 'G001')
        self.assertEqual(row['catchphrase'], 'Actual provider text')
        self.assertEqual(row['genre_catchphrase'], 'Genre description')
        self.assertEqual(row['sub_genre_code'], 'G002')
        self.assertFalse(row['ordering_supported'])
        missing = normalize_response(response_bytes([{'id': 'J123456789', 'name': 'Test',
            'genre': {'code': 'invented'}, 'logo_image': 'javascript:bad'}]))['restaurants'][0]
        self.assertIsNone(missing['genre_code'])
        self.assertIsNone(missing['catchphrase'])
        self.assertIsNone(missing['logo_url'])

    def test_directory_fields_budget_text_and_unknown_ordering(self):
        catalog = normalize_response(response_bytes())
        row = catalog['restaurants'][0]
        self.assertEqual(row['id'], 'hotpepper:J123456789')
        self.assertEqual(row['latitude'], 36.32)
        self.assertEqual(row['budget_description'], '3001～4000円')
        self.assertIsNone(row['minimum_order_yen'])
        self.assertIsNone(row['menu_items'])
        self.assertIsNone(row['delivery_available'])
        self.assertFalse(row['ordering_supported'])
        self.assertIn('image_credit', catalog['attribution'])

    def test_duplicate_ids_first_wins_and_invalid_coordinates_urls_are_omitted(self):
        shops = [{'id': 'J123456789', 'name': 'first', 'lat': 'NaN', 'lng': 181,
                  'urls': {'pc': 'javascript:alert(1)'}},
                 {'id': 'J123456789', 'name': 'second'}]
        rows = normalize_response(response_bytes(shops))['restaurants']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'first')
        for key in ('latitude', 'longitude', 'source_url'):
            self.assertIsNone(rows[0][key])

    def test_malformed_oversize_and_api_errors_rejected_without_server_message(self):
        bad = [b'bad', b'[]', b'{}', response_bytes([{'id': 'bad', 'name': 'x'}]),
               json.dumps({'results': {'error': [{'message': 'secret-key'}]}}).encode(),
               b'x' * (MAX_RESPONSE_BYTES + 1)]
        for data in bad:
            with self.subTest(length=len(data)), self.assertRaises(HotPepperError) as caught:
                normalize_response(data)
            self.assertNotIn('secret-key', str(caught.exception))

    def test_fetch_utf8_keyword_one_page_and_bounded_response(self):
        stream = io.BytesIO(response_bytes())
        with patch('jwc24.hotpepper.urlopen', return_value=stream) as opener, \
                patch.object(stream, 'read', wraps=stream.read) as read:
            result = fetch_catalog('高崎 和食', count=100, start=101, api_key='test-key')
            read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
            query = parse_qs(urlsplit(opener.call_args.args[0].full_url).query)
            self.assertEqual(query['keyword'], ['高崎 和食'])
            self.assertEqual(query['count'], ['100'])
            self.assertEqual(query['start'], ['101'])
            self.assertEqual(query['format'], ['json'])
        self.assertNotIn('test-key', json.dumps(result))

    def test_input_limits_missing_key_and_transport_error_redact_credentials(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(HotPepperError):
            fetch_catalog('高崎')
        for kwargs in ({'count': 101}, {'count': 0}, {'count': True}, {'start': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(HotPepperError):
                fetch_catalog('高崎', api_key='secret-key', **kwargs)
        with patch('jwc24.hotpepper.urlopen', side_effect=OSError('https://url/?key=secret-key')):
            with self.assertRaises(HotPepperError) as caught:
                fetch_catalog('高崎', api_key='secret-key')
            self.assertNotIn('secret-key', str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)

    def test_cli_failure_preserves_cache_and_success_uses_atomic_publication(self):
        # Private workspace location is required by the importer.
        root = Path(__file__).resolve().parents[1] / 'private'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            path = Path(directory) / 'catalog.json'
            path.write_bytes(b'old-cache')
            with patch('tools.import_hotpepper_catalog.fetch_catalog', side_effect=HotPepperError('bad')), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--keyword', '高崎', '--output', str(path)]), 1)
            self.assertEqual(path.read_bytes(), b'old-cache')
            with patch('tools.import_hotpepper_catalog.fetch_catalog', return_value=normalize_response(response_bytes())), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--keyword', '高崎', '--output', str(path)]), 0)
            self.assertEqual(json.loads(path.read_bytes())['provider'], 'hotpepper')


if __name__ == '__main__':
    unittest.main()
