from __future__ import annotations

import hashlib
import os
import shutil
import ssl
import subprocess
import re
from datetime import datetime, timezone
from collections.abc import Sequence
from urllib.parse import parse_qs, urlparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .manifest import ChannelManifest
from .wii_no_ma import get_response as wii_no_ma_get_response


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
    manifest: ChannelManifest | Sequence[ChannelManifest],
    host: str,
    port: int,
    nand_root: Path | None,
    tls_cert: Path | None = None,
    tls_key: Path | None = None,
) -> None:
    manifests = (manifest,) if isinstance(manifest, ChannelManifest) else tuple(manifest)
    if not manifests:
        raise ValueError("at least one manifest is required")
    if (tls_cert is None) != (tls_key is None):
        raise ValueError("TLS requires both a certificate and private key")
    all_tasks = tuple(task for item in manifests for task in item.tasks)
    all_assets = tuple(asset for item in manifests for asset in item.assets)
    wii_no_ma_base = next(
        (item.base_url for item in manifests if item.channel_id == "HCIJ"),
        "http://127.0.0.1",
    )
    routes = {task.route: task for task in all_tasks}
    if len(routes) != len(all_tasks):
        raise ValueError("manifests declare duplicate task routes")
    asset_routes = {}
    items_by_filename = {
        item.filename: item for item in (*all_tasks, *all_assets)
    }
    if len(items_by_filename) != len(all_tasks) + len(all_assets):
        raise ValueError("manifests declare duplicate payload filenames")
    for asset in all_assets:
        asset_routes[f"/{asset.filename}"] = asset
        for server_number in range(1, 11):
            asset_routes[f"/bin{server_number}/{asset.filename}"] = asset
    missing = [
        str(item.payload)
        for item in (*all_tasks, *all_assets)
        if not item.payload.is_file()
    ]
    if missing:
        raise FileNotFoundError("missing declared payloads:\n" + "\n".join(missing))
    request_log = Path("private/wii_no_ma/request.log")
    request_log.parent.mkdir(parents=True, exist_ok=True)
    request_log.write_text("", encoding="utf-8")
    key_file = None
    if any(
        item.envelope == "wc24-aes-ofb"
        for item in (*all_tasks, *all_assets)
    ):
        if nand_root is None:
            raise ValueError("manifest requires wc24-aes-ofb; pass --nand-root")
        encrypted_manifests = [
            item
            for item in manifests
            if any(value.envelope == "wc24-aes-ofb" for value in (*item.tasks, *item.assets))
        ]
        if len(encrypted_manifests) != 1:
            raise ValueError("multi-channel encrypted serving requires exactly one key owner")
        key_manifest = encrypted_manifests[0]
        key_file = (
            nand_root
            / "title"
            / f"{key_manifest.title_type:08x}"
            / f"{key_manifest.title_code:08x}"
            / "data"
            / "wc24pubk.mod"
        )
        if not key_file.is_file():
            raise FileNotFoundError(f"missing channel WC24 key: {key_file}")

    class Handler(BaseHTTPRequestHandler):
        server_version = "JWC24/0.1"
        # Wii no Ma uses NHTTP directly and expects the persistent HTTP/1.1
        # behavior of Nintendo's original service.  HTTP/1.0 delivered the
        # complete bodies but closed each socket, leaving the title's startup
        # completion gate with generic service error 354153.
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802
            raw_route = self.path.split("?", 1)[0]
            # Shorter replacement hosts are slash-padded in fixed-size channel
            # URL fields. Treat repeated path separators as equivalent.
            route = "/" + "/".join(part for part in raw_route.split("/") if part)
            if route == "/conf/first.bin" or route.startswith(("/url1/", "/url2/", "/url3/", "/shop/")):
                with request_log.open("a", encoding="utf-8") as handle:
                    handle.write(f"GET {self.path}\n")
                print(
                    f"{self.client_address[0]} HCIJ GET {self.path} "
                    f"user-agent={self.headers.get('User-Agent', '')!r}"
                )
            route_filename = route.rsplit("/", 1)[-1]
            suffix_asset = items_by_filename.get(route_filename)
            direct_response = wii_no_ma_get_response(route, wii_no_ma_base)
            shop_asset = None
            theater_asset = None
            brtest_asset = None
            wall_asset = None
            intro_asset = None
            pay_wall_asset = None
            pay_intro_asset = None
            mii_asset = None
            normal_category_asset = None
            special_asset = None
            picture_asset = None
            if route in ("/url1/conf/brtest-H.mov", "/url1/conf/brtest-L.mov"):
                brtest_asset = Path("private/wii_no_ma/theater/assets/movies/c8/2-H.mov")
            theater_match = re.fullmatch(
                r"/url1/movie/([0-9a-f]{2})/(\d+(?:-H)?\.(?:img|mov))", route
            )
            if theater_match:
                theater_asset = (
                    Path("private/wii_no_ma/theater/assets/movies")
                    / theater_match.group(1)
                    / theater_match.group(2)
                )
            wall_match = re.fullmatch(r"/url1/wall/(\d+\.img)", route)
            if wall_match:
                wall_asset = (
                    Path("private/wii_no_ma/theater/assets/normal-wall")
                    / wall_match.group(1)
                )
            intro_match = re.fullmatch(r"/url1/intro/([\w-]+\.img)", route)
            if intro_match:
                intro_asset = (
                    Path("private/wii_no_ma/theater/assets/normal-intro")
                    / intro_match.group(1)
                )
            pay_wall_match = re.fullmatch(r"/url3/pay/wall/(\d+)\.img", route)
            if pay_wall_match:
                product_id = int(pay_wall_match.group(1))
                bucket = hashlib.md5(
                    str(product_id).encode("ascii"), usedforsecurity=False
                ).hexdigest()[:2]
                pay_wall_asset = Path(
                    f"private/wii_no_ma/shop/assets/pay-movie/{bucket}/{product_id}/{product_id}.img"
                )
            if route == "/url3/pay/intro/1-1.img":
                bucket = hashlib.md5(b"1", usedforsecurity=False).hexdigest()[:2]
                pay_intro_asset = Path(
                    f"private/wii_no_ma/shop/assets/pay-movie/{bucket}/1/1.img"
                )
            mii_match = re.fullmatch(r"/url1/mii/(\d+\.mii)", route)
            if mii_match:
                mii_asset = Path("private/wii_no_ma/miis") / mii_match.group(1)
            normal_category_match = re.fullmatch(
                r"/url1/list/category/img/(2\d{4}\.img)", route
            )
            if normal_category_match:
                normal_category_asset = (
                    Path("private/wii_no_ma/miis/assets/categories")
                    / normal_category_match.group(1)
                )
            special_match = re.fullmatch(r"/url1/special/(\d+)/img/([\w-]+\.img)", route)
            if special_match:
                filename = "parade_banner.jpg" if special_match.group(2) == "g1234.img" else special_match.group(2)
                special_asset = (
                    Path("private/wii_no_ma/special/assets")
                    / special_match.group(1)
                    / filename
                )
            picture_match = re.fullmatch(r"/url1/picture/(\d+-\d+\.img)", route)
            if picture_match:
                picture_asset = (
                    Path("private/wii_no_ma/special/assets/picture")
                    / picture_match.group(1)
                )
            category_match = re.fullmatch(
                r"/url3/pay/list/category/img/(1000[1-5])\.img", route
            )
            if category_match:
                shop_asset = Path(
                    f"private/wii_no_ma/shop/assets/pay-category/{category_match.group(1)}.img"
                )
            else:
                asset_match = re.fullmatch(
                    r"/url3/pay/movie/([0-9a-f]{2})/(\d+)/([^/]+\.img)", route
                )
                if asset_match:
                    shop_asset = (
                        Path("private/wii_no_ma/shop/assets/pay-movie")
                        / asset_match.group(1)
                        / asset_match.group(2)
                        / asset_match.group(3)
                    )
            if route == "/healthz":
                body = b'{"status":"ok"}\n'
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
            elif direct_response is not None:
                body = direct_response
                self.send_response(HTTPStatus.OK)
                # The original/reference v1025 service is Flask-backed and
                # returns its XML documents as text/html. Match that legacy
                # MIME contract for the stock channel's response gate.
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif brtest_asset is not None and brtest_asset.is_file():
                body = brtest_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
            elif shop_asset is not None and shop_asset.is_file():
                body = shop_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
            elif theater_asset is not None and theater_asset.is_file():
                body = theater_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header(
                    "Content-Type",
                    "image/jpeg" if theater_asset.suffix == ".img" else "application/octet-stream",
                )
            elif wall_asset is not None and wall_asset.is_file():
                body = wall_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
            elif intro_asset is not None and intro_asset.is_file():
                body = intro_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
            elif pay_wall_asset is not None and pay_wall_asset.is_file():
                body = pay_wall_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
            elif pay_intro_asset is not None and pay_intro_asset.is_file():
                body = pay_intro_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
            elif mii_asset is not None and mii_asset.is_file():
                body = mii_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
            elif normal_category_asset is not None and normal_category_asset.is_file():
                body = normal_category_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
            elif special_asset is not None and special_asset.is_file():
                body = special_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
            elif picture_asset is not None and picture_asset.is_file():
                body = picture_asset.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
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
                    if not area_payload.is_file():
                        # Never fall back to the national package for an
                        # unknown numeric area. Its station count exceeds the
                        # channel's 24-station native model capacity.
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
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
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(body)
            if route == "/conf/first.bin" or route.startswith(("/url1/", "/url2/", "/url3/", "/shop/")):
                with request_log.open("a", encoding="utf-8") as handle:
                    handle.write(
                        f"DONE {datetime.now(timezone.utc).isoformat()} GET {self.path} "
                        f"status=200 bytes={len(body)} sha256={hashlib.sha256(body).hexdigest()}\n"
                    )

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else b""
            path = urlparse(self.path).path
            form = parse_qs(body.decode("ascii", errors="replace"), keep_blank_values=True)
            print(
                f"{self.client_address[0]} POST {path} bytes={len(body)} "
                f"fields={sorted(form)} user-agent={self.headers.get('User-Agent', '')!r}"
            )
            with request_log.open("a", encoding="utf-8") as handle:
                handle.write(f"POST {path} bytes={len(body)} fields={sorted(form)}\n")

            endpoint = path.rsplit("/", 1)[-1]
            endpoint = endpoint.replace("activate", "activate", 1)
            direct_response = wii_no_ma_get_response(path, wii_no_ma_base)
            if direct_response is not None:
                response = direct_response
                result = "0100"
                content_type = "application/xml; charset=utf-8"
            elif endpoint.startswith("activate") and endpoint.endswith(".cgi"):
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
            self.send_header("Connection", "keep-alive")
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
    channel_ids = ", ".join(item.channel_id for item in manifests)
    print(f"Serving {channel_ids} on {scheme}://{host}:{port}")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
