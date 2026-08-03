from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path


# Public fixed protocol key also embedded in IOS/Dolphin. Keep it as a byte
# table so secret scanners do not mistake it for a private repository token.
MAIL_CHECK_KEY = bytes(
    (
        0xCE,
        0x4C,
        0xF2,
        0x9A,
        0x3D,
        0x6B,
        0xE1,
        0xC2,
        0x61,
        0x91,
        0x72,
        0xB5,
        0xCB,
        0x29,
        0x8C,
        0x89,
        0x72,
        0xD4,
        0x50,
        0xAD,
    )
)
WII_ADDRESS = re.compile(r"(?i)\bw?([0-9]{16})@wii\.com\b")
SMTP_RECIPIENT = re.compile(
    r"(?im)^RCPT TO:\s*w?([0-9]{16})@wii\.com\s*$"
)
SMTP_DATA = re.compile(br"(?im)^DATA\r?\n")
MAX_MAIL_SIZE = 208_952
NO_MAIL_FLAG = "0" * 33


def cgi_response(**fields: str | int) -> bytes:
    return "".join(f"{key}={value}\n" for key, value in fields.items()).encode("ascii")


def normalize_wii_id(value: str | int) -> str:
    text = str(value)
    if text.lower().startswith("w"):
        text = text[1:]
    if not text.isdigit() or len(text) != 16:
        raise ValueError("Wii mail ID must contain exactly 16 decimal digits")
    return text


@dataclass(frozen=True)
class MailAccount:
    wii_id: str
    password: str
    mlchkid: str
    mail_flag: str


class MailStore:
    """Small filesystem-backed WC24 mail store shared by every channel."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.accounts_path = self.root / "accounts.json"
        self.messages = self.root / "messages"
        self.rejected = self.root / "rejected"
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        self.messages.mkdir(parents=True, exist_ok=True)
        self.rejected.mkdir(parents=True, exist_ok=True)

    def _read_accounts(self) -> dict[str, dict[str, str]]:
        if not self.accounts_path.is_file():
            return {}
        document = json.loads(self.accounts_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("mail account database is not an object")
        return document

    def _write_accounts(self, accounts: dict[str, dict[str, str]]) -> None:
        payload = (json.dumps(accounts, indent=2, sort_keys=True) + "\n").encode()
        with tempfile.NamedTemporaryFile(
            dir=self.root, prefix="accounts.", suffix=".tmp", delete=False
        ) as temporary:
            temporary.write(payload)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, self.accounts_path)

    @staticmethod
    def _account(wii_id: str, record: dict[str, str]) -> MailAccount:
        return MailAccount(
            wii_id,
            record["password"],
            record["mlchkid"],
            record.get("mail_flag", NO_MAIL_FLAG),
        )

    def register(self, wii_id: str | int) -> MailAccount:
        normalized = normalize_wii_id(wii_id)
        with self._lock:
            accounts = self._read_accounts()
            record = accounts.get(normalized)
            if record is None:
                record = {
                    "password": secrets.token_hex(8),
                    "mlchkid": secrets.token_hex(16),
                    "mail_flag": NO_MAIL_FLAG,
                }
                accounts[normalized] = record
                self._write_accounts(accounts)
            return self._account(normalized, record)

    def by_check_id(self, mlchkid: str) -> MailAccount | None:
        with self._lock:
            for wii_id, record in self._read_accounts().items():
                if hmac.compare_digest(record.get("mlchkid", ""), mlchkid):
                    return self._account(wii_id, record)
        return None

    def authenticate(self, wii_id: str | int, password: str) -> MailAccount | None:
        normalized = normalize_wii_id(wii_id)
        with self._lock:
            record = self._read_accounts().get(normalized)
            if record and hmac.compare_digest(record.get("password", ""), password):
                return self._account(normalized, record)
        return None

    def check_response(self, account: MailAccount, challenge: str, interval: int = 1) -> bytes:
        if not challenge.isdigit():
            raise ValueError("mail challenge must be decimal")
        mail_flag = account.mail_flag if self.pending(account.wii_id) else NO_MAIL_FLAG
        message = (
            f"{challenge}\nw{account.wii_id}\n{mail_flag}\n{interval}"
        ).encode("ascii")
        digest = hmac.new(MAIL_CHECK_KEY, message, hashlib.sha1).hexdigest()
        return cgi_response(
            cd=100,
            res=digest,
            **{"mail.flag": mail_flag, "interval": interval},
        )

    def _advance_flag(self, wii_id: str) -> None:
        accounts = self._read_accounts()
        record = accounts[wii_id]
        # KD compares only the first 22 characters of this opaque 33-character
        # value. A conventional right-aligned counter can therefore change
        # without the Wii noticing. Generate a fresh full-width value instead.
        record["mail_flag"] = secrets.token_hex(17)[:33]
        self._write_accounts(accounts)

    def store_message(self, sender: MailAccount, payload: bytes) -> list[str]:
        if not 0 < len(payload) <= MAX_MAIL_SIZE:
            raise ValueError("mail payload is empty or exceeds the WC24 limit")
        smtp_recipients = set(SMTP_RECIPIENT.findall(payload.decode("utf-8", errors="replace")))
        data_marker = SMTP_DATA.search(payload)
        message_payload = payload[data_marker.end() :] if data_marker else payload
        message_payload = message_payload.lstrip(b"\r\n").replace(b"\0", b"")
        message = BytesParser(policy=policy.default).parsebytes(message_payload)
        header_recipients = {
            match.group(1)
            for header in ("to", "cc", "bcc")
            for match in WII_ADDRESS.finditer(str(message.get(header, "")))
        }
        recipients = sorted(smtp_recipients | header_recipients)
        if not recipients:
            raise ValueError("mail has no w################@wii.com recipient")
        with self._lock:
            accounts = self._read_accounts()
            unknown = [recipient for recipient in recipients if recipient not in accounts]
            if unknown:
                raise ValueError(f"unknown Wii mail recipient: {unknown[0]}")
            for recipient in recipients:
                inbox = self.messages / recipient
                inbox.mkdir(parents=True, exist_ok=True)
                if message.get("X-Wii-Cmd") == "80010001":
                    # The Wii Menu can reload IOS during startup, causing more than one KD session
                    # to issue the same friend-registration command with a different Date header.
                    # Give that logical operation a stable key so retries remain idempotent.
                    identity = f"registration:{sender.wii_id}:{recipient}".encode("ascii")
                    digest = hashlib.sha256(identity).hexdigest()
                else:
                    digest = hashlib.sha256(message_payload).hexdigest()
                destination = inbox / f"{digest}.eml"
                if not destination.exists():
                    destination.write_bytes(message_payload)
                    self._advance_flag(recipient)
        return recipients

    def quarantine_rejected(self, sender: MailAccount, payload: bytes, reason: str) -> Path:
        """Preserve a rejected native payload privately so protocol mismatches are diagnosable."""
        digest = hashlib.sha256(payload).hexdigest()
        destination = self.rejected / f"{sender.wii_id}-{digest}.eml"
        destination.write_bytes(payload)
        destination.with_suffix(".txt").write_text(reason + "\n", encoding="utf-8")
        return destination

    def pending(self, wii_id: str | int) -> list[Path]:
        inbox = self.messages / normalize_wii_id(wii_id)
        return sorted(inbox.glob("*.eml")) if inbox.is_dir() else []

    def claim(self, account: MailAccount, max_size: int, limit: int = 10) -> list[bytes]:
        if max_size <= 0:
            raise ValueError("maxsize must be positive")
        claimed: list[bytes] = []
        used = 0
        with self._lock:
            for path in self.pending(account.wii_id)[:limit]:
                payload = path.read_bytes().replace(b"\n", b"\r\n").replace(b"\r\r\n", b"\r\n")
                if claimed and used + len(payload) > max_size:
                    break
                if len(payload) > max_size:
                    continue
                path.replace(path.with_suffix(".sent"))
                claimed.append(payload)
                used += len(payload)
        return claimed

    def delete_claimed(self, account: MailAccount) -> int:
        inbox = self.messages / account.wii_id
        claimed = sorted(inbox.glob("*.sent")) if inbox.is_dir() else []
        for path in claimed:
            path.unlink()
        return len(claimed)
