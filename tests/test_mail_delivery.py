"""Durable local mail state and wire budgeting; no device credentials used."""
from __future__ import annotations

import contextlib
import hashlib
import http.client
import io
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from jwc24.mail import MailStore, NO_MAIL_FLAG, normalize_wii_id
from jwc24.mail_server import create_mail_server

SENDER = "1111222233334444"
RECIPIENT = "1234567890123456"


def message(label):
    return f"From: w{SENDER}@wii.com\nTo: w{RECIPIENT}@wii.com\nSubject: {label}\n\nSynthetic notice\n".encode()


def fields(body):
    return dict(line.split("=", 1) for line in body.decode("ascii").splitlines() if "=" in line)


class DurableMailTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = MailStore(self.root)
        self.sender = self.store.register(SENDER)
        self.recipient = self.store.register(RECIPIENT)

    def tearDown(self):
        self.temporary.cleanup()

    def test_receive_retry_after_restart_replays_same_batch_before_new_mail(self):
        self.store.store_message(self.sender, message("first"))
        first = self.store.claim(self.recipient, 10000)
        self.store.store_message(self.sender, message("second"))
        restarted = MailStore(self.root)
        self.assertEqual(restarted.claim(self.recipient, 10000), first)
        self.assertEqual(len(restarted.pending(RECIPIENT)), 2)
        self.assertEqual(restarted.delete_claimed(self.recipient, expected_count=1), 1)
        second = restarted.claim(self.recipient, 10000)
        self.assertEqual(len(second), 1)
        self.assertIn(b"Subject: second", second[0])
        self.assertEqual(restarted.delete_claimed(self.recipient, expected_count=1), 1)
        self.assertFalse(restarted.pending(RECIPIENT))

    def test_unacknowledged_mail_is_advertised_and_send_retry_does_not_duplicate(self):
        self.store.store_message(self.sender, message("same"))
        before = fields(self.store.check_response(self.recipient, "123"))["mail.flag"]
        self.assertNotEqual(before, NO_MAIL_FLAG)
        self.store.claim(self.recipient, 10000)
        self.store.store_message(self.sender, message("same"))
        self.assertEqual(len(self.store.pending(RECIPIENT)), 1)
        self.assertEqual(fields(self.store.check_response(self.recipient, "123"))["mail.flag"], before)
        self.store.delete_claimed(self.recipient)
        self.assertEqual(fields(self.store.check_response(self.recipient, "123"))["mail.flag"], NO_MAIL_FLAG)

    def test_account_flag_failure_prevents_message_commit_and_legacy_entries_remain_discoverable(self):
        with patch.object(self.store, "_advance_flag", side_effect=OSError("synthetic storage failure")):
            with self.assertRaises(OSError):
                self.store.store_message(self.sender, message("recover"))
        self.assertFalse(self.store.pending(RECIPIENT))
        # Preserve discoverability of an entry committed by the older service
        # during its message-before-generation crash window.
        payload = message("legacy")
        inbox = self.store.messages / RECIPIENT
        inbox.mkdir(exist_ok=True)
        (inbox / (hashlib.sha256(payload).hexdigest() + ".eml")).write_bytes(payload)
        restarted = MailStore(self.root)
        account = restarted.register(RECIPIENT)
        self.assertEqual(account.mail_flag, NO_MAIL_FLAG)
        self.assertNotEqual(fields(restarted.check_response(account, "123"))["mail.flag"], NO_MAIL_FLAG)
        self.assertEqual(len(restarted.claim(account, 10000)), 1)

    def test_failed_atomic_publish_leaves_no_partial_message_or_temp_file(self):
        import os
        replace = os.replace
        def fail_message(source, destination):
            if Path(destination).suffix == ".eml":
                raise OSError("synthetic disk failure")
            return replace(source, destination)
        with patch("jwc24.mail.os.replace", side_effect=fail_message):
            with self.assertRaises(OSError):
                self.store.store_message(self.sender, message("never partial"))
        self.assertFalse(self.store.pending(RECIPIENT))
        self.assertFalse(list(self.store.messages.rglob("*.tmp")))

    def test_acknowledgment_recovery_after_partial_file_deletion(self):
        for label in ("one", "two"):
            self.store.store_message(self.sender, message(label))
        self.store.claim(self.recipient, 10000)
        unlink = Path.unlink
        deleted = []
        def fail_second(path, *args, **kwargs):
            if path.suffix == ".sent":
                if deleted:
                    raise OSError("synthetic interrupted retirement")
                deleted.append(path.name)
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_second), self.assertRaises(OSError):
            self.store.delete_claimed(self.recipient, expected_count=2)
        self.assertEqual(len(list(self.store.messages.rglob("*.sent"))), 1)
        restarted = MailStore(self.root)
        self.assertFalse(restarted.pending(RECIPIENT))
        self.assertEqual(restarted.delete_claimed(self.recipient, expected_count=2), 2)
        self.assertFalse(list(self.store.messages.rglob("*.sent")))
        self.assertFalse(list(self.store.messages.rglob("acknowledgment.json")))

    def test_same_content_submission_after_interrupted_ack_is_new_mail(self):
        for label in ("one", "two"):
            self.store.store_message(self.sender, message(label))
        self.store.claim(self.recipient, 10000)
        unlink = Path.unlink
        retired = []
        def fail_second(path, *args, **kwargs):
            if path.suffix == ".sent":
                if retired:
                    raise OSError("synthetic interrupted retirement")
                retired.append(path.name)
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_second), self.assertRaises(OSError):
            self.store.delete_claimed(self.recipient, expected_count=2)
        remaining = next(self.store.messages.rglob("*.sent")).read_bytes()
        restarted = MailStore(self.root)
        restarted.store_message(self.sender, remaining)
        self.assertFalse(list(self.store.messages.rglob("*.sent")))
        self.assertEqual(len(restarted.pending(RECIPIENT)), 1)
        self.assertEqual(restarted.pending(RECIPIENT)[0].read_bytes(), remaining)

    def test_oversized_front_entries_do_not_hide_a_later_fitting_message(self):
        inbox = self.store.messages / RECIPIENT
        inbox.mkdir()
        for index in range(10):
            (inbox / (f"{index:064x}" + ".eml")).write_bytes(b"x" * 100)
        (inbox / ("f" * 64 + ".eml")).write_bytes(b"fits")
        self.assertEqual(self.store.claim(self.recipient, 10), [b"fits"])
        self.assertEqual(len(self.store.pending(RECIPIENT)), 11)

    def test_identical_content_after_acknowledgment_has_a_new_check_flag(self):
        payload = message("same again")
        self.store.store_message(self.sender, payload)
        first = fields(self.store.check_response(self.recipient, "123"))["mail.flag"]
        self.store.claim(self.recipient, 10000)
        self.store.delete_claimed(self.recipient, expected_count=1)
        self.store.store_message(self.sender, payload)
        second = fields(self.store.check_response(self.recipient, "123"))["mail.flag"]
        self.assertNotEqual(first[:22], second[:22])

    def test_replay_budget_and_partial_acknowledgment_never_discard_batch(self):
        for label in ("one", "two"):
            self.store.store_message(self.sender, message(label))
        first = self.store.claim(self.recipient, 10000)
        with self.assertRaises(ValueError):
            self.store.claim(self.recipient, 1)
        with self.assertRaises(ValueError):
            self.store.delete_claimed(self.recipient, expected_count=1)
        self.assertEqual(self.store.claim(self.recipient, 10000), first)
        self.assertEqual(self.store.delete_claimed(self.recipient, expected_count=2), 2)
        self.assertEqual(self.store.delete_claimed(self.recipient, expected_count=2), 0)

    def test_private_representations_and_non_ascii_identifiers(self):
        representation = repr(self.recipient)
        for value in (RECIPIENT, self.recipient.password, self.recipient.mlchkid):
            self.assertNotIn(value, representation)
        for value in ("\uff11" * 16, "\u0661" * 16, True, "123"):
            with self.assertRaises(ValueError):
                normalize_wii_id(value)
        for challenge in ("\uff11", "\u0661", "1" * 65):
            with self.assertRaises(ValueError):
                self.store.check_response(self.recipient, challenge)


class MailWireTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = MailStore(Path(self.temporary.name))
        self.sender = self.store.register(SENDER)
        self.recipient = self.store.register(RECIPIENT)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.server = create_mail_server("127.0.0.1", 0, self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.output.__exit__(None, None, None)
        self.temporary.cleanup()

    def post(self, route, data):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("POST", "/cgi-bin/" + route, urlencode(data),
                               {"Content-Type": "application/x-www-form-urlencoded"})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def auth(self, **extra):
        return {"mlid": "w" + RECIPIENT, "passwd": self.recipient.password, **extra}

    def test_multipart_budget_includes_every_mail_part_prefix_and_retries(self):
        payload = message("budget")
        self.store.store_message(self.sender, payload)
        wire_length = len(payload.replace(b"\n", b"\r\n"))
        # Receive boundary has a stable length; its actual value remains random.
        overhead = len(b"\r\n--jwc24/" + b"0" * 16 + b"\r\nContent-Type: text/plain\r\n\r\n")
        status, body = self.post("receive.cgi", self.auth(maxsize=wire_length + overhead - 1))
        self.assertEqual(status, 200)
        self.assertIn(b"mailnum=0\n", body)
        self.assertEqual(len(list(self.store.messages.rglob("*.sent"))), 0)
        limit = wire_length + overhead
        for _ in range(2):
            status, body = self.post("receive.cgi", self.auth(maxsize=limit))
            self.assertEqual(status, 200)
            self.assertIn(b"mailnum=1\n", body)
            self.assertIn(f"mailsize={limit}\n".encode(), body)
        _, rejected = self.post("delete.cgi", self.auth(delnum=0))
        self.assertEqual(fields(rejected)["cd"], "220")
        self.assertEqual(len(self.store.pending(RECIPIENT)), 1)
        _, deleted = self.post("delete.cgi", self.auth(delnum=1))
        self.assertEqual(fields(deleted)["deletenum"], "1")
        self.assertFalse(self.store.pending(RECIPIENT))

    def raw_post(self, headers, body=b"", shutdown=True):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=5) as client:
            client.sendall(b"POST /cgi-bin/account.cgi HTTP/1.0\r\n" + headers + b"\r\n" + body)
            if shutdown:
                client.shutdown(socket.SHUT_WR)
            return client.recv(65536).split(b"\r\n", 1)[0]

    def test_invalid_or_ambiguous_lengths_and_truncation_do_not_register_accounts(self):
        before = self.store.accounts_path.read_bytes()
        for headers, body, expected in (
            (b"Content-Length: -1\r\n", b"", b"400"),
            (b"Content-Length: x\r\n", b"", b"400"),
            (b"Content-Length: 1\r\nContent-Length: 1\r\n", b"x", b"400"),
            (b"Transfer-Encoding: chunked\r\n", b"", b"400"),
            (b"Content-Length: 5000000\r\n", b"", b"413"),
            (b"Content-Length: 10\r\n", b"short", b"400"),
        ):
            with self.subTest(headers=headers):
                self.assertIn(expected, self.raw_post(headers, body))
        self.assertEqual(self.store.accounts_path.read_bytes(), before)

    def test_stalled_request_has_bounded_timeout(self):
        with patch("jwc24.mail_server.REQUEST_TIMEOUT_SECONDS", 0.1):
            self.assertIn(b"408", self.raw_post(b"Content-Length: 10\r\n", shutdown=False))

    def test_storage_failure_is_unavailable_and_keeps_queued_mail(self):
        self.store.store_message(self.sender, message("retained"))
        with patch.object(self.store, "claim", side_effect=OSError("private-path-marker")):
            status, body = self.post("receive.cgi", self.auth(maxsize=10000))
        self.assertEqual(status, 503)
        self.assertNotIn(b"private-path-marker", body)
        self.assertEqual(len(self.store.pending(RECIPIENT)), 1)
