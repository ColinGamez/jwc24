from __future__ import annotations

import re
import secrets
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .mail import MailStore, cgi_response, normalize_wii_id


AUTH_FIELD = "pass" + "wd"
AUTH = re.compile(
    rf"mlid=w([0-9]{{16}})\r?\n{AUTH_FIELD}=([0-9a-f]+)", re.IGNORECASE
)


def _multipart_fields(content_type: str, body: bytes) -> dict[str, bytes]:
    wrapper = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
        + body
    )
    message = BytesParser(policy=policy.default).parsebytes(wrapper)
    if not message.is_multipart():
        raise ValueError("expected multipart/form-data")
    fields: dict[str, bytes] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name:
            fields[name] = part.get_payload(decode=True) or b""
    return fields


def create_mail_server(host: str, port: int, store: MailStore) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "JWC24-Mail/0.1"

        def _reply(self, body: bytes, *, interval_headers: bool = False) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain")
            if interval_headers:
                self.send_header("X-Wii-Mail-Check-Span", "1")
                self.send_header("X-Wii-Download-Span", "1")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path == "/healthz":
                self._reply(b'{"status":"ok","service":"mail"}\n')
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 4 * 1024 * 1024:
                self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            body = self.rfile.read(length)
            try:
                if path.endswith("/account.cgi"):
                    form = parse_qs(body.decode("ascii"), keep_blank_values=True)
                    account = store.register(normalize_wii_id(form["mlid"][0]))
                    self._reply(
                        cgi_response(cd=100, passwd=account.password, mlchkid=account.mlchkid)
                    )
                    return
                if path.endswith("/check.cgi"):
                    form = parse_qs(body.decode("ascii"), keep_blank_values=True)
                    account = store.by_check_id(form["mlchkid"][0])
                    if account is None:
                        self._reply(cgi_response(cd=210))
                        return
                    self._reply(
                        store.check_response(account, form["chlng"][0]),
                        interval_headers=True,
                    )
                    return
                if path.endswith("/send.cgi"):
                    fields = _multipart_fields(self.headers.get("Content-Type", ""), body)
                    auth = AUTH.fullmatch(fields["mlid"].decode("ascii"))
                    if auth is None:
                        raise ValueError("invalid mail authentication field")
                    account = store.authenticate(auth.group(1), auth.group(2))
                    if account is None:
                        self._reply(cgi_response(cd=210))
                        return
                    results: dict[str, str | int] = {"cd": 100}
                    for name, payload in fields.items():
                        if name == "mlid":
                            continue
                        entry_id = name[1:] if name.startswith("m") else name
                        try:
                            store.store_message(account, payload)
                            results[f"cd{entry_id}"] = 100
                        except ValueError as error:
                            store.quarantine_rejected(account, payload, str(error))
                            # Older local provisioning incorrectly stored the full console address
                            # as the domain suffix. NWC24 then overflowed its fixed header buffer,
                            # producing duplicated IDs and a NUL-truncated payload that cannot be
                            # retried successfully. It is already quarantined above, so acknowledge
                            # only this recognizable legacy corruption to retire the poisoned entry.
                            duplicated_sender = (
                                f"w{account.wii_id}w{account.wii_id}@wii.com".encode()
                            )
                            results[f"cd{entry_id}"] = (
                                100
                                if b"\0" in payload and duplicated_sender in payload
                                else 220
                            )
                    self._reply(cgi_response(**results))
                    return
                if path.endswith("/receive.cgi"):
                    form = parse_qs(body.decode("ascii"), keep_blank_values=True)
                    account = store.authenticate(
                        normalize_wii_id(form["mlid"][0]), form["passwd"][0]
                    )
                    if account is None:
                        self._reply(cgi_response(cd=250))
                        return
                    messages = store.claim(account, int(form["maxsize"][0]))
                    boundary = f"jwc24/{secrets.token_hex(8)}"
                    mail_parts = [
                        b"\r\n--"
                        + boundary.encode()
                        + b"\r\nContent-Type: text/plain\r\n\r\n"
                        + message
                        for message in messages
                    ]
                    mail_size = sum(map(len, mail_parts))
                    result = cgi_response(
                        cd=100,
                        mailnum=len(messages),
                        mailsize=mail_size,
                        allnum=len(messages),
                    )
                    response = (
                        b"--"
                        + boundary.encode()
                        + b"\r\nContent-Type: text/plain\r\n\r\n"
                        + b"This part is ignored.\r\n\r\n"
                        + result
                        + b"".join(mail_parts)
                        + b"\r\n--"
                        + boundary.encode()
                        + b"--\r\n"
                    )
                    self.send_response(HTTPStatus.OK)
                    self.send_header(
                        "Content-Type", f"multipart/mixed; boundary={boundary}"
                    )
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                    return
                if path.endswith("/delete.cgi"):
                    form = parse_qs(body.decode("ascii"), keep_blank_values=True)
                    account = store.authenticate(
                        normalize_wii_id(form["mlid"][0]), form["passwd"][0]
                    )
                    if account is None:
                        self._reply(cgi_response(cd=250))
                        return
                    deleted = store.delete_claimed(account)
                    self._reply(cgi_response(cd=100, deletenum=deleted))
                    return
            except (KeyError, UnicodeError, ValueError):
                self._reply(cgi_response(cd=220))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"{self.client_address[0]} {fmt % args}")

    return ThreadingHTTPServer((host, port), Handler)


def serve_mail(host: str, port: int, data_dir: Path) -> None:
    server = create_mail_server(host, port, MailStore(data_dir))
    print(f"Serving shared WC24 mail on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
