"""News binary routing alongside manifests; signatures verified in publication tests."""
import contextlib
from dataclasses import replace
import http.client
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from jwc24 import server
from jwc24 import __main__ as cli
from jwc24.forecast import encode_lz10, WII_EPOCH_UNIX
from jwc24.news_publication import prepare_news_publication
from jwc24.news_server import NewsApplication
from tests.test_news import synthetic_news
from tests.test_wc24_delivery import manifest


class SharedNewsServerTests(unittest.TestCase):
    def test_signed_bytes_bypass_transforms_and_expired_routes_do_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "test-public.pem"
            key.write_bytes(b"signature verification is independently tested")
            now = WII_EPOCH_UNIX + 10000 * 60
            payload = bytes(320) + encode_lz10(synthetic_news())
            # This integration test isolates routing. Publication signature tests use real keys.
            with patch("jwc24.news_publication._verify_signatures"):
                publication = prepare_news_publication(
                    [payload] * 24, public_key=key, route_prefix="/v2/0/001",
                    source_refs=["urn:synthetic:routing-test"] * 24,
                    rights_ref="urn:synthetic:no-publisher-data", current_unix_timestamp=now)
            value = manifest(root, 1, "plain.bin")
            value = replace(value, tasks=(replace(value.tasks[0], envelope="raw"),))
            ready, listeners, errors = threading.Event(), [], []
            clock = [now]
            def factory(address, handler):
                listener = ThreadingHTTPServer(address, handler)
                listeners.append(listener)
                ready.set()
                return listener
            def run():
                try:
                    server.serve((value,), "127.0.0.1", 0, None, news_publication=publication)
                except BaseException as error:
                    errors.append(error)
                    ready.set()
            previous, connection, worker = Path.cwd(), None, None
            try:
                os.chdir(root)
                with patch.object(server, "ThreadingHTTPServer", side_effect=factory), \
                     patch.object(server, "NewsApplication", side_effect=lambda p: NewsApplication(p, clock=lambda: clock[0])), \
                     patch("builtins.print"):
                    worker = threading.Thread(target=run, daemon=True)
                    worker.start()
                    self.assertTrue(ready.wait(5))
                    self.assertFalse(errors)
                    connection = http.client.HTTPConnection("127.0.0.1", listeners[0].server_port, timeout=5)
                    for slot in range(24):
                        connection.request("GET", f"/v2/0/001/news.bin.{slot:02d}")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.getheader("Content-Type"), "application/octet-stream")
                        self.assertEqual(int(response.getheader("Content-Length")), len(payload))
                        self.assertEqual(response.read(), payload)
                    for path in ("/v2/0/001/news.bin.24", "/v2/0/001/news.bin.00?x=1"):
                        connection.request("GET", path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 404)
                        self.assertEqual(response.read(), b"")
                    clock[0] += 100000 * 60
                    connection.request("GET", "/v2/0/001/news.bin.00")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 503)
                    self.assertEqual(response.read(), b"")
                    connection.request("GET", "/fixture/plain.bin")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), value.tasks[0].payload.read_bytes())
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
            conflict = replace(value, tasks=(replace(value.tasks[0], route="/v2/0/001/news.bin.00"),))
            with self.assertRaisesRegex(ValueError, "conflict"):
                server.serve((conflict,), "127.0.0.1", 0, None, news_publication=publication)
            alias_conflict = replace(value, tasks=(replace(value.tasks[0], filename="news.bin.00"),))
            with self.assertRaisesRegex(ValueError, "conflict"):
                server.serve((alias_conflict,), "127.0.0.1", 0, None, news_publication=publication)

    def test_cli_requires_explicit_pair_and_loads_before_serving(self):
        for option in ("--news-root", "--news-public-key"):
            with patch("sys.argv", ["jwc24", "serve", "unused.json", option, "private-input"]), \
                 patch.object(cli, "serve") as serving, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(), 2)
                serving.assert_not_called()
        with patch("sys.argv", ["jwc24", "serve", "unused.json", "--news-root", "explicit-root", "--news-public-key", "explicit-key"]), \
             patch("jwc24.news_publication.load_news_publication", side_effect=ValueError("validation failed")) as load, \
             patch.object(cli, "serve") as serving, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(), 2)
            load.assert_called_once_with(Path("explicit-root"), public_key=Path("explicit-key"))
            serving.assert_not_called()


if __name__ == "__main__":
    unittest.main()
