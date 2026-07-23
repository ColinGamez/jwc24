from __future__ import annotations

import hashlib
import os
import shutil
import ssl
import subprocess
from urllib.parse import parse_qs, urlparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .manifest import ChannelManifest


def _nintendo_lz10_literal(payload: bytes) -> bytes:
    """Encode an LZ10 stream using literal groups only.

    Literal-only output is slightly larger than an optimized stream, but it is
    deterministic and exercises the exact decoder used by the original title.
    """
    if not 0 < len(payload) <= 0xFFFFFF:
        raise ValueError("Nintendo LZ10 payload size must fit in 24 bits")
    output = bytearray((0x10,))
    output.extend(len(payload).to_bytes(3, "little"))
    for offset in range(0, len(payload), 8):
        output.append(0)
        output.extend(payload[offset : offset + 8])
    return bytes(output)


def _aes_ofb(payload: bytes, key: bytes, iv: bytes, decrypt: bool = False) -> bytes:
    try:
        from Crypto.Cipher import AES
    except ModuleNotFoundError:
        openssl = shutil.which("openssl")
        if not openssl:
            raise RuntimeError("AES-OFB requires pycryptodome or an OpenSSL executable")
        command = [
            openssl,
            "enc",
            "-aes-128-ofb",
            "-K",
            key.hex(),
            "-iv",
            iv.hex(),
            "-nosalt",
        ]
        if decrypt:
            command.append("-d")
        result = subprocess.run(command, input=payload, capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError(f"OpenSSL AES-OFB failed: {result.stderr.decode(errors='replace')}")
        return result.stdout
    return AES.new(key, AES.MODE_OFB, iv=iv).decrypt(payload) if decrypt else AES.new(
        key, AES.MODE_OFB, iv=iv
    ).encrypt(payload)


def _wc24_envelope(payload: bytes, key_file: Path) -> bytes:
    key_blob = key_file.read_bytes()
    if len(key_blob) != 544:
        raise ValueError(f"unexpected wc24pubk.mod size: {len(key_blob)}")
    key = key_blob[512:528]
    iv = os.urandom(16)
    header = bytearray(320)
    header[0:4] = b"Wc24"
    header[4:8] = (1).to_bytes(4, "big")
    header[12] = 1
    header[48:64] = iv
    encrypted = _aes_ofb(payload, key, iv)
    return bytes(header) + encrypted


def serve(
    manifest: ChannelManifest,
    host: str,
    port: int,
    nand_root: Path | None,
    tls_cert: Path | None = None,
    tls_key: Path | None = None,
) -> None:
    if (tls_cert is None) != (tls_key is None):
        raise ValueError("TLS requires both a certificate and private key")
    routes = {task.route: task for task in manifest.tasks}
    asset_routes = {}
    items_by_filename = {
        item.filename: item for item in (*manifest.tasks, *manifest.assets)
    }
    for asset in manifest.assets:
        asset_routes[f"/{asset.filename}"] = asset
        for server_number in range(1, 11):
            asset_routes[f"/bin{server_number}/{asset.filename}"] = asset
    missing = [
        str(item.payload)
        for item in (*manifest.tasks, *manifest.assets)
        if not item.payload.is_file()
    ]
    if missing:
        raise FileNotFoundError("missing declared payloads:\n" + "\n".join(missing))
    key_file = None
    if any(
        item.envelope == "wc24-aes-ofb"
        for item in (*manifest.tasks, *manifest.assets)
    ):
        if nand_root is None:
            raise ValueError("manifest requires wc24-aes-ofb; pass --nand-root")
        key_file = (
            nand_root
            / "title"
            / f"{manifest.title_type:08x}"
            / f"{manifest.title_code:08x}"
            / "data"
            / "wc24pubk.mod"
        )
        if not key_file.is_file():
            raise FileNotFoundError(f"missing channel WC24 key: {key_file}")

    class Handler(BaseHTTPRequestHandler):
        server_version = "JWC24/0.1"

        def do_GET(self) -> None:  # noqa: N802
            route = self.path.split("?", 1)[0]
            route_filename = route.rsplit("/", 1)[-1]
            suffix_asset = items_by_filename.get(route_filename)
            if route == "/healthz":
                body = b'{"status":"ok"}\n'
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
            elif route in routes or route in asset_routes or suffix_asset is not None:
                item = routes.get(route) or asset_routes.get(route) or suffix_asset
                payload_path = item.payload
                route_parts = route.strip("/").split("/")
                if len(route_parts) == 2 and route_parts[0].isdigit():
                    area_payload = (
                        item.payload.parent
                        / "areas"
                        / route_parts[0]
                        / item.payload.name
                    )
                    if area_payload.is_file():
                        payload_path = area_payload
                body = payload_path.read_bytes()
                if item.compression == "nintendo-lz10":
                    body = _nintendo_lz10_literal(body)
                if item.envelope == "wc24-aes-ofb":
                    assert key_file is not None
                    body = _wc24_envelope(body, key_file)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("ETag", hashlib.sha256(body).hexdigest())
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else b""
            path = urlparse(self.path).path
            form = parse_qs(body.decode("ascii", errors="replace"), keep_blank_values=True)
            print(
                f"{self.client_address[0]} POST {path} bytes={len(body)} "
                f"fields={sorted(form)}"
            )

            endpoint = path.rsplit("/", 1)[-1]
            endpoint = endpoint.replace("activate", "activate", 1)
            if endpoint.startswith("activate") and endpoint.endswith(".cgi"):
                response = b""
                result = "0100"
                content_type = "text/plain"
            elif endpoint.startswith("query") and endpoint.endswith(".cgi"):
                response = b""
                result = "0100"
                content_type = "text/plain"
            elif endpoint.startswith("popularity") and endpoint.endswith(".cgi"):
                submitted = form.get("wiino", [""])[0]
                program_count = len([value for value in submitted.split(",") if value])
                response = b"0" * program_count
                result = "0200"
                content_type = "text/plain"
            elif path.startswith("/bin") and path.endswith("/"):
                response = b""
                result = "0300"
                content_type = "application/octet-stream"
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("X-RESULT", result)
            self.send_header("Content-Length", str(len(response)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"{self.client_address[0]} {fmt % args}")

    httpd = ThreadingHTTPServer((host, port), Handler)
    scheme = "https" if tls_cert else "http"
    if tls_cert and tls_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # Wii NHTTP negotiates TLS 1.0/1.1. OpenSSL 3 requires the compatibility
        # security level for those legacy protocol versions.
        context.minimum_version = ssl.TLSVersion.TLSv1
        context.maximum_version = ssl.TLSVersion.TLSv1_1
        context.set_ciphers("ALL:@SECLEVEL=0")
        context.load_cert_chain(tls_cert, tls_key)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    print(f"Serving {manifest.channel_id} on {scheme}://{host}:{port}")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
