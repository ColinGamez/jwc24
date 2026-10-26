"""Immutable HBNJ routes through actual LZ10/WC24 transport with generated keys."""
from dataclasses import replace
import contextlib
from http.server import ThreadingHTTPServer
import http.client
import io
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from jwc24 import __main__ as cli, server
from jwc24.forecast import decode_lz10
from jwc24.hbnj_publication import HBNJRouteSnapshot, load_hbnj_snapshot, publish_hbnj_snapshot
from jwc24.manifest import ChannelManifest, Task
from tests.test_hbnj_publication import fixture, write_fixture
from tests.test_wc24_delivery import make_key, manifest


def hbnj_manifest(root):
    tasks = tuple(Task(10 + index, filename, route, root / 'missing-legacy' / filename,
                       60, 5, False, 'create', 'nintendo-lz10', 'wc24-aes-ofb')
                  for index, (filename, route) in enumerate((('epg.bin', '/1016/epg.bin'),
                                                             ('str.bin', '/1016/str.bin'),
                                                             ('header.bin', '/header.bin'))))
    return ChannelManifest(root / 'hbnj.json', 1, 'HBNJ', 'Synthetic transport manifest',
                           0x0001000148424E4A, 'JPN', 'http://127.0.0.1', False, tasks, ())


class HBNJSharedServerTests(unittest.TestCase):
    def test_all_109_routes_use_snapshot_owner_transport_and_expire_without_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = int(time.time())
            guide, payloads = write_fixture(root / 'input', fixture(now))
            publish_hbnj_snapshot(guide, payloads, root / 'publication', now=now,
                                  rights_ref='synthetic-test-only', max_collection_age_seconds=3600)
            snapshot = load_hbnj_snapshot(root / 'publication', now=now)
            value = hbnj_manifest(root)
            make_key(root, value, 7)
            other = manifest(root, 1, 'other.bin')
            other = replace(other, tasks=(replace(other.tasks[0], envelope='raw'),))
            ready, listeners, errors = threading.Event(), [], []
            clock = [now]
            def factory(address, handler):
                listener = ThreadingHTTPServer(address, handler)
                listeners.append(listener)
                ready.set()
                return listener
            def run():
                try:
                    server.serve((value, other), '127.0.0.1', 0, root, hbnj_snapshot=snapshot)
                except BaseException as error:
                    errors.append(error)
                    ready.set()
            previous, connection, worker = Path.cwd(), None, None
            try:
                os.chdir(root)
                with patch.object(server, 'ThreadingHTTPServer', side_effect=factory), \
                     patch('jwc24.hbnj_publication.time.time', side_effect=lambda: clock[0]), \
                     patch('builtins.print'):
                    worker = threading.Thread(target=run, daemon=True)
                    worker.start()
                    self.assertTrue(ready.wait(5))
                    self.assertFalse(errors)
                    # A new/corrupt pointer cannot change this captured runtime generation.
                    (root / 'publication/current.json').write_bytes(b'not-current-generation')
                    connection = http.client.HTTPConnection('127.0.0.1', listeners[0].server_port, timeout=5)
                    routes = ['/header.bin'] + [f'/{area}/{name}.bin' for area in range(1001, 1055)
                                                 for name in ('epg', 'str')]
                    for route in routes:
                        connection.request('GET', route)
                        response = connection.getresponse()
                        wire = response.read()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(wire[:4], b'Wc24')
                        self.assertEqual(int(response.getheader('Content-Length')), len(wire))
                        compressed = server._aes_ofb(wire[320:], bytes([7]) * 16, wire[48:64], decrypt=True)
                        self.assertEqual(decode_lz10(compressed), snapshot.raw_payload(route, now=now))
                    for route in ('/1055/epg.bin', '/0/str.bin', '/other/header.bin', '/epg.bin'):
                        connection.request('GET', route)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 404)
                        response.read()
                    clock[0] = snapshot.expires_unix
                    connection.request('GET', '/1016/epg.bin')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 503)
                    response.read()
                    connection.request('GET', '/fixture/other.bin')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), other.tasks[0].payload.read_bytes())
            finally:
                if connection:
                    connection.close()
                if listeners:
                    listeners[0].shutdown()
                    listeners[0].server_close()
                if worker:
                    worker.join(5)
                os.chdir(previous)
            self.assertFalse(worker.is_alive())
            self.assertFalse(errors)
            with patch('jwc24.hbnj_publication.time.time', return_value=now):
                bad_owner = replace(value, title_id=1)
                with self.assertRaisesRegex(ValueError, 'verified title'):
                    server.serve((bad_owner,), '127.0.0.1', 0, root, hbnj_snapshot=snapshot)
                raw = replace(value, tasks=(replace(value.tasks[0], envelope='raw'), *value.tasks[1:]))
                with self.assertRaisesRegex(ValueError, 'transport modes'):
                    server.serve((raw,), '127.0.0.1', 0, root, hbnj_snapshot=snapshot)
                conflict = replace(other, tasks=(replace(other.tasks[0], route='/wrong/header.bin'),))
                with self.assertRaisesRegex(ValueError, 'conflicts'):
                    server.serve((value, conflict), '127.0.0.1', 0, root, hbnj_snapshot=snapshot)

    def test_cli_loads_explicit_snapshot_before_listening(self):
        with patch('sys.argv', ['jwc24', 'serve', 'manifest.json', '--hbnj-root', 'selected-publication']), \
             patch.object(cli, 'load_manifest', return_value=hbnj_manifest(Path('unused'))), \
             patch('jwc24.hbnj_publication.load_hbnj_snapshot', side_effect=ValueError('invalid snapshot')) as load, \
             patch.object(cli, 'serve') as serving, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(), 2)
            load.assert_called_once_with(Path('selected-publication'))
            serving.assert_not_called()
        with self.assertRaises(ValueError):
            server.serve([], '127.0.0.1', 0, None, hbnj_snapshot=object())
        unprepared = HBNJRouteSnapshot()
        with self.assertRaises(ValueError):
            server.serve([hbnj_manifest(Path('unused'))], '127.0.0.1', 0, None,
                         hbnj_snapshot=unprepared)


if __name__ == '__main__':
    unittest.main()
