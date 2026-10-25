from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
from dataclasses import dataclass, field
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
    if re.fullmatch(r"[0-9]{16}", text) is None:
        raise ValueError("Wii mail ID must contain exactly 16 decimal digits")
    return text


@dataclass(frozen=True)
class MailAccount:
    wii_id: str = field(repr=False)
    password: str = field(repr=False)
    mlchkid: str = field(repr=False)
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
        self._atomic_write(self.accounts_path, payload)

    @staticmethod
    def _atomic_write(destination: Path, payload: bytes) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix="mail.", suffix=".tmp", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _ack_intent(inbox: Path) -> tuple[str, ...]:
        path = inbox / "acknowledgment.json"
        try:
            with path.open("rb") as source:
                raw = source.read(8193)
        except FileNotFoundError:
            return ()
        if len(raw) > 8192:
            raise ValueError("mail acknowledgment intent is oversized")
        try:
            value = json.loads(raw)
            names = value["messages"]
            valid = (type(value) is dict and set(value) == {"schema_version", "messages"}
                     and type(value["schema_version"]) is int and value["schema_version"] == 1
                     and type(names) is list and 1 <= len(names) <= 10
                     and all(isinstance(name, str) and re.fullmatch(r"[0-9a-f]{64}\.sent", name) for name in names)
                     and len(set(names)) == len(names))
        except (ValueError, KeyError, TypeError):
            valid = False
        if not valid:
            raise ValueError("mail acknowledgment intent is invalid")
        return tuple(names)

    def _complete_ack(self, inbox: Path) -> int:
        names = self._ack_intent(inbox)
        if names:
            for name in names:
                (inbox / name).unlink(missing_ok=True)
            (inbox / "acknowledgment.json").unlink()
        return len(names)

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
        if re.fullmatch(r"[0-9]{1,64}", challenge) is None:
            raise ValueError("mail challenge must be decimal")
        with self._lock:
            pending = self.pending(account.wii_id)
            # Queue filenames are content hashes (or stable registration keys).
            # Include the durable generation marker so identical content queued
            # after acknowledgment cannot reuse a cached flag. Reading current
            # state avoids relying on a caller's stale MailAccount snapshot.
            # Ignore suffix changes while a batch awaits delete acknowledgment.
            generation = self._read_accounts()[account.wii_id].get("mail_flag", NO_MAIL_FLAG)
            mail_flag = (hashlib.sha256((generation + "\n" + "\n".join(sorted({p.stem for p in pending}))).encode("ascii"))
                         .hexdigest()[:33] if pending else NO_MAIL_FLAG)
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
                # A prior delete acknowledgment may have committed before a
                # crash during retirement. Finish it before treating a new
                # same-content submission as an unacknowledged duplicate.
                self._complete_ack(inbox)
                if message.get("X-Wii-Cmd") == "80010001":
                    # The Wii Menu can reload IOS during startup, causing more than one KD session
                    # to issue the same friend-registration command with a different Date header.
                    # Give that logical operation a stable key so retries remain idempotent.
                    identity = f"registration:{sender.wii_id}:{recipient}".encode("ascii")
                    digest = hashlib.sha256(identity).hexdigest()
                else:
                    digest = hashlib.sha256(message_payload).hexdigest()
                destination = inbox / f"{digest}.eml"
                if not destination.exists() and not destination.with_suffix(".sent").exists():
                    # Commit the generation before publishing the new message.
                    # Failure can cause an extra check, never an undiscoverable
                    # committed message with a reused cached generation.
                    self._advance_flag(recipient)
                    self._atomic_write(destination, message_payload)
        return recipients

    def quarantine_rejected(self, sender: MailAccount, payload: bytes, reason: str) -> Path:
        """Preserve a rejected native payload privately so protocol mismatches are diagnosable."""
        digest = hashlib.sha256(payload).hexdigest()
        destination = self.rejected / f"{sender.wii_id}-{digest}.eml"
        destination.write_bytes(payload)
        destination.with_suffix(".txt").write_text(reason + "\n", encoding="utf-8")
        return destination

    def pending(self, wii_id: str | int) -> list[Path]:
        """Return queued and claimed-but-unacknowledged messages."""
        inbox = self.messages / normalize_wii_id(wii_id)
        if not inbox.is_dir():
            return []
        retired = set(self._ack_intent(inbox))
        return sorted(p for p in (*inbox.glob("*.eml"), *inbox.glob("*.sent")) if p.name not in retired)

    def claim(self, account: MailAccount, max_size: int, limit: int = 10,
              *, message_overhead: int = 0) -> list[bytes]:
        """Replay an outstanding batch until delete.cgi acknowledges it.

        The batch remains on disk across HTTP disconnects and service restarts.
        New mail cannot enter that batch before acknowledgment, since deletion
        is batch-scoped. Overhead lets the CGI enforce its multipart byte budget.
        """
        if type(max_size) is not int or max_size <= 0:
            raise ValueError("maxsize must be positive")
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("mail batch limit must be between one and ten")
        if type(message_overhead) is not int or message_overhead < 0:
            raise ValueError("mail multipart overhead must be nonnegative")
        claimed: list[bytes] = []
        used = 0
        with self._lock:
            inbox = self.messages / normalize_wii_id(account.wii_id)
            self._complete_ack(inbox)
            outstanding = sorted(inbox.glob("*.sent"))
            if len(outstanding) > limit:
                raise ValueError("outstanding mail batch exceeds the requested limit")
            candidates = outstanding or sorted(inbox.glob("*.eml"))
            selected = []
            for path in candidates:
                if len(claimed) >= limit:
                    break
                payload = path.read_bytes().replace(b"\n", b"\r\n").replace(b"\r\r\n", b"\r\n")
                size = len(payload) + message_overhead
                if used + size > max_size:
                    if outstanding:
                        raise ValueError("outstanding mail batch does not fit the requested byte budget")
                    if claimed:
                        break
                    continue
                selected.append(path)
                claimed.append(payload)
                used += size
            for path in selected:
                if path.suffix == ".eml":
                    path.replace(path.with_suffix(".sent"))
        return claimed

    def delete_claimed(self, account: MailAccount, *, expected_count: int | None = None) -> int:
        with self._lock:
            inbox = self.messages / normalize_wii_id(account.wii_id)
            retiring = self._ack_intent(inbox)
            if retiring:
                if expected_count is not None and expected_count != len(retiring):
                    raise ValueError("mail acknowledgment does not match the retiring batch")
                return self._complete_ack(inbox)
            claimed = sorted(inbox.glob("*.sent")) if inbox.is_dir() else []
            if expected_count is not None:
                if type(expected_count) is not int or expected_count < 0:
                    raise ValueError("mail acknowledgment count must be nonnegative")
                # An already acknowledged empty batch permits an idempotent
                # delete retry. Partial acknowledgment needs a separately
                # recovered contract; do not guess which messages were stored.
                if claimed and expected_count != len(claimed):
                    raise ValueError("mail acknowledgment does not match the outstanding batch")
            if not claimed:
                return 0
            intent = {"schema_version": 1, "messages": [path.name for path in claimed]}
            self._atomic_write(inbox / "acknowledgment.json", json.dumps(intent).encode("ascii"))
            return self._complete_ack(inbox)
