from __future__ import annotations

import http.client
import os
import tempfile
import threading
import unittest
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from jwc24 import server
from jwc24.manifest import Asset, ChannelManifest, Task
from jwc24.wc24_delivery import envelope_key_paths


def manifest(root: Path, code: int, filename: str) -> ChannelManifest:
    payload = root / filename
    payload.write_bytes(b"synthetic payload " + filename.encode())
    return ChannelManifest(root / "manifest.json", 1, "SYNTHETIC", "Synthetic",
                           (0x10001 << 32) | code, "JPN", "http://127.0.0.1",
                           False, (Task(code, filename, "/fixture/" + filename,
                                        payload, 60, 5, False, "create", "none",
                                        "wc24-aes-ofb"),), ())


def make_key(root: Path, value: ChannelManifest, octet: int) -> Path:
    path = root / "title" / f"{value.title_type:08x}" / f"{value.title_code:08x}" / "data" / "wc24pubk.mod"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(512) + bytes([octet]) * 16 + bytes(16))
    return path


class WC24DeliveryTests(unittest.TestCase):
    def test_each_owner_and_asset_gets_its_own_key_without_reading_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = manifest(root, 1, "one.bin"), manifest(root, 2, "two.bin")
            second = replace(second, tasks=(), assets=(Asset("two.bin", root / "two.bin", "none", "wc24-aes-ofb"),))
            one, two = make_key(root, first, 1), make_key(root, second, 2)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read secrets")):
                self.assertEqual(envelope_key_paths((first, second), root), {"one.bin": one, "two.bin": two})

    def test_missing_wrong_size_keys_and_implicit_nand_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = manifest(root, 1, "one.bin")
            for nand in (None, root):
                with self.subTest(nand_present=nand is not None), self.assertRaises(ValueError):
                    envelope_key_paths((value,), nand)
            path = make_key(root, value, 1)
            for size in (0, 543, 545):
                path.write_bytes(bytes(size))
                with self.subTest(size=size), self.assertRaises(ValueError):
                    envelope_key_paths((value,), root)

    def test_unencrypted_payloads_do_not_require_nand(self):
        with tempfile.TemporaryDirectory() as directory:
            value = manifest(Path(directory), 1, "one.bin")
            value = replace(value, tasks=(replace(value.tasks[0], envelope="raw"),))
            self.assertEqual(envelope_key_paths((value,), None), {})

    def test_filename_alias_collision_is_rejected_across_owners(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = manifest(root, 1, "same.bin"), manifest(root, 2, "same.bin")
            with self.assertRaisesRegex(ValueError, "duplicate payload"):
                envelope_key_paths((first, second), root)

    def test_http_aliases_encrypt_with_payload_owner_and_preserve_raw_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = Path.cwd()
            first, second = manifest(root, 1, "one.bin"), manifest(root, 2, "two.bin")
            first = replace(first, tasks=(replace(first.tasks[0], compression="nintendo-lz10"),))
            raw = Asset("plain.bin", root / "plain.bin", "none", "raw")
            raw.payload.write_bytes(b"unencrypted fixture")
            second = replace(second, assets=(raw, Asset("second-asset.bin", root / "two.bin", "none", "wc24-aes-ofb")))
            make_key(root, first, 1)
            make_key(root, second, 2)
            ready, listeners, errors = threading.Event(), [], []

            def factory(address, handler):
                listener = ThreadingHTTPServer(address, handler)
                listeners.append(listener)
                ready.set()
                return listener

            def run():
                try:
                    server.serve((first, second), "127.0.0.1", 0, root)
                except BaseException as exc:
                    errors.append(exc)
                    ready.set()

            connection = None
            worker = None
            try:
                os.chdir(root)
                with patch.object(server, "ThreadingHTTPServer", side_effect=factory), patch("builtins.print"):
                    worker = threading.Thread(target=run, daemon=True)
                    worker.start()
                    self.assertTrue(ready.wait(5))
                    self.assertFalse(errors)
                    connection = http.client.HTTPConnection("127.0.0.1", listeners[0].server_port, timeout=5)
                    for route, octet, expected in (
                        ("/fixture/one.bin", 1, server._nintendo_lz10_literal(first.tasks[0].payload.read_bytes())),
                        ("/fixture/two.bin", 2, second.tasks[0].payload.read_bytes()),
                        ("/bin7/second-asset.bin", 2, second.tasks[0].payload.read_bytes()),
                        ("/unrelated/prefix/one.bin", 1, server._nintendo_lz10_literal(first.tasks[0].payload.read_bytes())),
                    ):
                        connection.request("GET", route)
                        response = connection.getresponse()
                        wire = response.read()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(int(response.getheader("Content-Length")), len(wire))
                        self.assertEqual(wire[:4], b"Wc24")
                        self.assertEqual(server._aes_ofb(wire[320:], bytes([octet]) * 16, wire[48:64], decrypt=True), expected)
                        self.assertNotEqual(server._aes_ofb(wire[320:], bytes([3-octet]) * 16, wire[48:64], decrypt=True), expected)
                    connection.request("GET", "/bin1/plain.bin")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), raw.payload.read_bytes())
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
