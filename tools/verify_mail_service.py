from __future__ import annotations

import hashlib
import hmac
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jwc24.mail import MAIL_CHECK_KEY, NO_MAIL_FLAG, MailStore
from jwc24.mail_server import create_mail_server


SENDER = "8419982858718746"
RECIPIENT = "1234567890123456"


def post(url: str, body: bytes, content_type: str) -> bytes:
    request = Request(url, body, headers={"Content-Type": content_type}, method="POST")
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise ValueError(f"{url}: HTTP {response.status}")
        return response.read()


def fields(payload: bytes) -> dict[str, str]:
    return dict(
        line.decode("ascii").split("=", 1)
        for line in payload.splitlines()
        if b"=" in line
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jwc24-mail-test-") as temporary:
        store = MailStore(Path(temporary))
        server = create_mail_server("127.0.0.1", 0, store)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}/cgi-bin"
        try:
            sender = fields(
                post(
                    f"{base}/account.cgi",
                    urlencode({"mlid": f"w{SENDER}", "hdid": "1", "rgncd": "JPN"}).encode(),
                    "application/x-www-form-urlencoded",
                )
            )
            recipient = store.register(RECIPIENT)
            challenge = "987654321"
            checked = fields(
                post(
                    f"{base}/check.cgi",
                    urlencode({"mlchkid": sender["mlchkid"], "chlng": challenge}).encode(),
                    "application/x-www-form-urlencoded",
                )
            )
            mime_message = (
                f"From: w{SENDER}@wii.com\r\n"
                f"To: w{RECIPIENT}@wii.com\r\n"
                "Subject: JWC24 self-test\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n\r\n"
                "Reusable Wii Mail test.\r\n"
            ).encode()
            message = (
                f"MAIL FROM: w{SENDER}@wii.com\r\n"
                f"RCPT TO: w{RECIPIENT}@wii.com\r\n"
                "DATA\r\n\r\n"
            ).encode() + mime_message
            boundary = "jwc24-test-boundary"
            auth = f"mlid=w{SENDER}\r\npasswd={sender['passwd']}".encode()
            multipart = bytearray()
            for name, value in (("mlid", auth), ("m7", message)):
                multipart.extend(f"--{boundary}\r\n".encode())
                multipart.extend(
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
                )
                multipart.extend(value)
                multipart.extend(b"\r\n")
            multipart.extend(f"--{boundary}--\r\n".encode())
            sent = fields(
                post(
                    f"{base}/send.cgi",
                    bytes(multipart),
                    f"multipart/form-data; boundary={boundary}",
                )
            )
            pending = store.pending(recipient.wii_id)
            if sender.get("cd") != "100" or checked.get("cd") != "100":
                raise ValueError("account/check CGI did not return success")
            expected_hmac = hmac.new(
                MAIL_CHECK_KEY,
                f"{challenge}\nw{SENDER}\n{NO_MAIL_FLAG}\n1".encode(),
                hashlib.sha1,
            ).hexdigest()
            if checked.get("res") != expected_hmac:
                raise ValueError("mail-check HMAC differs from Dolphin's contract")
            if sent.get("cd") != "100" or sent.get("cd7") != "100":
                raise ValueError("send CGI did not accept message")
            if len(pending) != 1 or pending[0].read_bytes() != mime_message:
                raise ValueError("recipient mailbox did not preserve the MIME message")
            refreshed = store.register(RECIPIENT)
            if refreshed.mail_flag == NO_MAIL_FLAG:
                raise ValueError("recipient mail flag did not advance")
            received = post(
                f"{base}/receive.cgi",
                urlencode(
                    {
                        "mlid": f"w{RECIPIENT}",
                        "passwd": recipient.password,
                        "maxsize": "1048576",
                    }
                ).encode(),
                "application/x-www-form-urlencoded",
            )
            if mime_message not in received:
                raise ValueError("receive CGI omitted the queued MIME message")
            deleted = fields(
                post(
                    f"{base}/delete.cgi",
                    urlencode(
                        {
                            "mlid": f"w{RECIPIENT}",
                            "passwd": recipient.password,
                            "delnum": "1",
                        }
                    ).encode(),
                    "application/x-www-form-urlencoded",
                )
            )
            if deleted.get("cd") != "100" or store.pending(RECIPIENT):
                raise ValueError("delete CGI did not clear delivered mail")
            print(
                "valid shared WC24 mail service: "
                "account=100 check=100 hmac=ok send=100 receive=1 delete=1"
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
