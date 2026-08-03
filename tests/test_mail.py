from __future__ import annotations

import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path

from jwc24.mail import MailStore


SENDER = "1111222233334444"
RECIPIENT = "8419982858718746"


class MailStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = MailStore(Path(self.temporary.name))
        self.sender = self.store.register(SENDER)
        self.store.register(RECIPIENT)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_stores_smtp_wrapped_wii_mail(self) -> None:
        payload = (
            f"MAIL FROM: w{SENDER}@wii.com\r\n"
            f"RCPT TO: w{RECIPIENT}@wii.com\r\n"
            "DATA\r\n"
            f"From: w{SENDER}@wii.com\r\n"
            f"To: w{RECIPIENT}@wii.com\r\n"
            "Subject: Reply test\r\n\r\n"
            "Hello from the Wii.\r\n"
        ).encode("ascii")

        self.assertEqual(self.store.store_message(self.sender, payload), [RECIPIENT])
        stored = self.store.pending(RECIPIENT)[0].read_bytes()
        self.assertTrue(stored.startswith(f"From: w{SENDER}@wii.com".encode()))
        self.assertNotIn(b"MAIL FROM:", stored)

    def test_accepts_native_numeric_wii_address(self) -> None:
        payload = (
            f"MAIL FROM: {SENDER}@wii.com\r\n"
            f"RCPT TO: {RECIPIENT}@wii.com\r\n"
            "DATA\r\n"
            f"From: {SENDER}@wii.com\r\n"
            f"To: {RECIPIENT}@wii.com\r\n"
            "Subject: Native address\r\n\r\nHello\r\n"
        ).encode("ascii")

        self.assertEqual(self.store.store_message(self.sender, payload), [RECIPIENT])

    def test_preserves_multipart_attachment(self) -> None:
        payload = (
            f"To: w{RECIPIENT}@wii.com\r\n"
            "MIME-Version: 1.0\r\n"
            "Content-Type: multipart/mixed; boundary=jwc24-test\r\n\r\n"
            "--jwc24-test\r\nContent-Type: text/plain\r\n\r\nBody\r\n"
            "--jwc24-test\r\nContent-Type: image/jpeg\r\n"
            "Content-Transfer-Encoding: base64\r\n"
            "Content-Disposition: attachment; filename=photo.jpg\r\n\r\n"
            "/9j/2Q==\r\n--jwc24-test--\r\n"
        ).encode("ascii")

        self.store.store_message(self.sender, payload)
        message = BytesParser(policy=policy.default).parsebytes(
            self.store.pending(RECIPIENT)[0].read_bytes()
        )
        attachments = list(message.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "photo.jpg")
        self.assertEqual(attachments[0].get_payload(decode=True), b"\xff\xd8\xff\xd9")

    def test_rejects_unknown_recipient(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown Wii mail recipient"):
            self.store.store_message(
                self.sender, b"To: w9999000011112222@wii.com\r\n\r\nUnknown"
            )

    def test_registration_retries_are_idempotent(self) -> None:
        template = (
            f"From: w{SENDER}@wii.com\r\n"
            f"To: w{RECIPIENT}@wii.com\r\n"
            "Date: {date}\r\n"
            "X-Wii-Cmd: 80010001\r\n\r\nRegistration"
        )
        self.store.store_message(self.sender, template.format(date="first").encode())
        self.store.store_message(self.sender, template.format(date="retry").encode())

        self.assertEqual(len(self.store.pending(RECIPIENT)), 1)


if __name__ == "__main__":
    unittest.main()
