from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .mail import MailStore
from .mail_server import create_mail_server


def _mail_service_healthy(host: str, port: int) -> bool:
    try:
        with urlopen(f"http://{host}:{port}/healthz", timeout=2) as response:
            document = json.loads(response.read())
        return document.get("status") == "ok" and document.get("service") == "mail"
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False


def launch(
    dolphin: Path,
    data_dir: Path,
    host: str = "127.0.0.1",
    port: int = 8081,
    title: str = "0000000100000002",
) -> int:
    executable = dolphin.resolve()
    if not executable.is_file():
        raise ValueError(f"Dolphin executable does not exist: {executable}")

    owned_server = None
    server_thread = None
    if not _mail_service_healthy(host, port):
        owned_server = create_mail_server(host, port, MailStore(data_dir))
        server_thread = threading.Thread(
            target=owned_server.serve_forever, name="JWC24 Mail", daemon=True
        )
        server_thread.start()
        for _ in range(20):
            if _mail_service_healthy(host, port):
                break
            time.sleep(0.1)
        else:
            owned_server.shutdown()
            raise RuntimeError("JWC24 mail service failed its startup health check")

    try:
        return subprocess.run([str(executable), "-n", title], check=False).returncode
    finally:
        if owned_server is not None:
            owned_server.shutdown()
            owned_server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=5)
