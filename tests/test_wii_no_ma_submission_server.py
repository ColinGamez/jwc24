"""Real loopback receipt binding; no native vote or provider acceptance claim."""
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import http.client
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from jwc24 import server
from jwc24.wii_no_ma import get_response
from jwc24.wii_no_ma_interactions import INTERACTION_ROUTES, InteractionStore


@contextmanager
def receipt_server():
    with tempfile.TemporaryDirectory() as directory:
        previous = Path.cwd()
        root = Path(directory)
        ready, listeners, errors = threading.Event(), [], []
        manifest = SimpleNamespace(channel_id='TEST', base_url='http://127.0.0.1', tasks=(), assets=())
        def factory(address, handler):
            listener = ThreadingHTTPServer(address, handler)
            listeners.append(listener)
            ready.set()
            return listener
        def run():
            try:
                server.serve([manifest], '127.0.0.1', 0, None)
            except BaseException as error:
                errors.append(error)
                ready.set()
        worker, connection = None, None
        try:
            os.chdir(root)
            with patch.object(server, 'ThreadingHTTPServer', side_effect=factory), patch('builtins.print'):
                worker = threading.Thread(target=run, daemon=True)
                worker.start()
                if not ready.wait(5) or errors:
                    raise AssertionError('Synthetic receipt listener failed')
                connection = http.client.HTTPConnection('127.0.0.1', listeners[0].server_port, timeout=5)
                yield connection, InteractionStore(root / 'private/wii_no_ma/interactions')
        finally:
            if connection:
                connection.close()
            if listeners:
                listeners[0].shutdown()
                listeners[0].server_close()
            if worker:
                worker.join(5)
            os.chdir(previous)
        if worker.is_alive() or errors:
            raise AssertionError('Synthetic receipt listener did not stop cleanly')


class WiiNoMaSubmissionHTTPTests(unittest.TestCase):
    def test_each_existing_xml_acknowledgment_has_a_committed_unicode_receipt(self):
        with receipt_server() as (connection, store):
            form = {'synthetic': ['\u65e5\u672c\u8a9e', '\u4e8c\u756a'], 'choice': ['1']}
            body = urlencode(form, doseq=True).encode()
            for route in sorted(INTERACTION_ROUTES):
                connection.request('POST', route, body, {'Content-Type': 'application/x-www-form-urlencoded'})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader('X-RESULT'), '0100')
                self.assertEqual(response.read(), get_response(route))
                row, = store.receipts(route)
                self.assertEqual(row['form'], form)
            connection.request('POST', '/url2/evaluate.cgi', body)
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            self.assertEqual(store.receipts('/url2/evaluate.cgi')[0]['attempts'], 2)

    def test_storage_failure_and_invalid_forms_never_return_static_acknowledgment(self):
        with receipt_server() as (connection, store):
            with patch.object(InteractionStore, 'record', side_effect=sqlite3.OperationalError('private-path-marker')):
                connection.request('POST', '/url2/evaluate.cgi', b'synthetic=1')
                response = connection.getresponse()
                self.assertEqual(response.status, 503)
                failure = response.read()
                self.assertNotIn(b'<Evaluate', failure)
                self.assertNotIn(b'private-path-marker', failure)
            self.assertEqual(store.receipts(), [])
            for body in (b'', b'bad=%ZZ', b'bad=%FF', b'\xff'):
                connection.request('POST', '/url2/enquete.cgi', body)
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                response.read()
            self.assertEqual(store.receipts(), [])

    def test_bounded_framing_rejects_before_receipt_and_get_consumes_its_own_body(self):
        with receipt_server() as (connection, store):
            connection.request('GET', '/healthz', b'not-a-second-request')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            connection.request('POST', '/url2/evaluate.cgi', b'synthetic=1')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            self.assertEqual(len(store.receipts()), 1)
            for headers, status in (
                ([('Content-Length', str(server.MAX_CGI_BODY_BYTES + 1))], 413),
                ([('Content-Length', '0'), ('Content-Length', '0')], 400),
                ([('Transfer-Encoding', 'chunked')], 501),
            ):
                connection.putrequest('POST', '/url2/enquete.cgi')
                for name, value in headers:
                    connection.putheader(name, value)
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, status)
                response.read()
            self.assertEqual(len(store.receipts()), 1)


if __name__ == '__main__':
    unittest.main()
