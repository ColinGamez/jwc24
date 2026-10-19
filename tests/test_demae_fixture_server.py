from http.client import HTTPConnection
import threading
import json
import unittest
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from test_japan_post import source
from jwc24.japan_post import build_database
from jwc24.demae_area_registry import AreaRegistry, area_identity, assign_area_codes

from tools.demae_fixture_server import create_server
from jwc24.demae_response import inspect_area_response


class FixtureServerTests(unittest.TestCase):
    def test_native_diagnostic_is_acknowledged_without_forwarding_report(self):
        from urllib.parse import urlencode
        from contextlib import redirect_stdout
        import io
        server = create_server()
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            output = io.StringIO()
            body = urlencode({'action': 'webApi_inquiry_done', 'platform': 'wii',
                              'message': 'エラーコード：336195\nPRIVATE REPORT DATA'})
            connection = HTTPConnection(*server.server_address, timeout=3)
            with redirect_stdout(output):
                connection.request('POST', '/nwapi.php', body,
                                   {'Content-Type': 'application/x-www-form-urlencoded'})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(ET.fromstring(response.read()).findtext('apiStatus/code'), '0')
            self.assertIn('code=336195', output.getvalue())
            self.assertNotIn('PRIVATE REPORT DATA', output.getvalue())
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def test_read_only_area_form_post_and_rejected_order_forms(self):
        server = create_server()
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for body, expected in (
                ('action=webApi_area_list&platform=wii&areaCode=0', 200),
                ('action=webApi_order_done&platform=wii&areaCode=0', 405),
                ('action=webApi_area_list&platform=wii&areaCode=unknown', 405),
                ('action=webApi_area_list&platform=wii&areaCode=0&areaCode=0', 405)):
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('POST', '/nwapi.php', body,
                                   {'Content-Type': 'application/x-www-form-urlencoded'})
                response = connection.getresponse()
                self.assertEqual(response.status, expected)
                data = response.read()
                if expected == 200:
                    self.assertEqual(inspect_area_response(data, variant='root')['row_count'], 47)
                connection.close()
            for path, body, expected in (
                ('/nwapi.php?action=webApi_area_list&platform=wii', 'areaCode=0', 200),
                ('/nwapi.php?action=webApi_area_list&platform=wii&areaCode=0', '', 200),
                ('/nwapi.php?action=webApi_area_list&platform=wii&areaCode=0', 'areaCode=0', 405)):
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('POST', path, body)
                response = connection.getresponse()
                self.assertEqual(response.status, expected)
                response.read()
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def test_opt_in_decimal_town_http_route(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'postal.sqlite'
            rows = [(f'{n:02d}001', f'{n:02d}00001', f'Prefecture {n}', f'City {n}', 'Town') for n in range(1, 48)]
            build_database(source(*rows), database)
            registry = AreaRegistry(assign_area_codes({}, [area_identity(row[0], row[1], row[4]) for row in rows]))
            server = create_server(postal_database=database, town_registry=registry)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/nwapi.php?action=webApi_area_list&platform=wii&areaCode=M10001')
                response = connection.getresponse()
                data = response.read()
                self.assertEqual(response.status, 200)
                self.assertEqual(inspect_area_response(data, variant='list')['row_count'], 1)
                self.assertIn(registry.code_for('10001', '1000001', 'Town').encode(), data)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_municipality_navigation_uses_bounded_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'postal.sqlite'
            build_database(source(*[(f'{n:02d}001', f'{n:02d}00001', f'Prefecture {n}',
                                     f'City {n}', 'Town') for n in range(1, 48)]), database)
            server = create_server(postal_database=database)
            # The response snapshot must not retain SQLite file handles.
            database.unlink()
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/health')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn('application/json', response.getheader('Content-Type'))
                health = json.loads(response.read())
                self.assertEqual(health['municipality_prefectures'], 47)
                self.assertFalse(health['ordering_supported'])
                self.assertFalse(health['town_navigation'])
                connection.close()
                for code, expected in [('TEST-JP-10', 200), ('TEST-JP-48', 400),
                                       ('TEST-JP-10&areaCode=TEST-JP-11', 400)]:
                    connection = HTTPConnection(*server.server_address, timeout=3)
                    connection.request('GET', '/nwapi.php?action=webApi_area_list&platform=wii&areaCode=' + code)
                    response = connection.getresponse()
                    data = response.read()
                    self.assertEqual(response.status, expected)
                    if expected == 200:
                        self.assertEqual(inspect_area_response(data, variant='list')['row_count'], 1)
                        self.assertIn(b'M10001', data)
                    connection.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_root_response_and_reject_unsupported_queries(self):
        server = create_server()
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            self.assertEqual(server.server_address[0], '127.0.0.1')
            for suffix, status in [('action=webApi_area_list&platform=wii&areaCode=0', 200),
                                   ('action=webApi_order_done&platform=wii&areaCode=0', 400),
                                   ('action=webApi_area_list&platform=wii&areaCode=0&areaCode=1', 400),
                                   ('action=webApi_area_list&platform=wii&zipCode=123456', 400),
                                   ('action=webApi_area_list&platform=wii&zipCode=1234567&zipCode=7654321', 400)]:
                connection = HTTPConnection(*server.server_address, timeout=3)
                connection.request('GET', '/nwapi.php?' + suffix)
                response = connection.getresponse()
                data = response.read()
                self.assertEqual(response.status, status)
                self.assertEqual(response.getheader('X-JWC24-Scope'), 'synthetic-offline-fixture')
                if status == 200:
                    self.assertEqual(inspect_area_response(data, variant='root')['row_count'], 47)
                connection.close()
            connection = HTTPConnection(*server.server_address, timeout=3)
            connection.request('POST', '/nwapi.php', b'action=webApi_order_done')
            response = connection.getresponse()
            self.assertEqual(response.status, 405)
            response.read()
            connection.close()
            connection = HTTPConnection(*server.server_address, timeout=3)
            connection.request('GET', '/nwapi.php?action=webApi_document_template&platform=wii&version=00000')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(inspect_area_response(response.read(), variant='documents')['document_count'], 3)
            connection.close()
            connection = HTTPConnection(*server.server_address, timeout=3)
            connection.request('GET', '/nwapi.php?action=webApi_Authkey&platform=wii')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(inspect_area_response(response.read(), variant='auth')['variant'], 'auth')
            connection.close()
            connection = HTTPConnection(*server.server_address, timeout=3)
            connection.request('GET', '/nwapi.php?action=webApi_area_list&platform=wii&zipCode=3770813')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(inspect_area_response(response.read(), variant='postal-fallback')['api_code'], 13)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
