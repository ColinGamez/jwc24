"""Private durable receipts for Wii no Ma voting and rating submissions."""
from __future__ import annotations

import json
import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

INTERACTION_ROUTES = frozenset({
    "/url2/evaluate.cgi", "/url2/pay/pevaluate.cgi",
    "/url2/enquete.cgi", "/url2/piceval.cgi",
})


def _canonical_form(form: object) -> str:
    if not isinstance(form, dict) or not form:
        raise ValueError("a submitted form is required")
    if any(not isinstance(key, str) or not isinstance(values, list)
           or not values or any(not isinstance(value, str) for value in values)
           for key, values in form.items()):
        raise ValueError("interaction fields must contain lists of strings")
    document = json.dumps(form, ensure_ascii=False, sort_keys=True)
    # Reject surrogate code points before opening storage, rather than failing
    # after a partial schema migration or while binding a SQLite TEXT value.
    document.encode("utf-8")
    return document


def _fingerprint(endpoint: str, document: str) -> str:
    return hashlib.sha256((endpoint + "\0" + document).encode("utf-8")).hexdigest()


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate legacy interaction field")
        result[key] = value
    return result


@dataclass(frozen=True)
class InteractionReceipt:
    """An acknowledgment for a committed local receipt, not an authenticated vote."""

    identifier: int
    response: bytes


class InteractionStore:
    """Commit each distinct form before the HTTP handler acknowledges it.

    These are submission receipts, including emulator submissions. They do
    not infer per-Mii eligibility or aggregate historical voting statistics.
    """

    def __init__(self, root: Path):
        self.root = root
        self.database_path = root / "receipts.sqlite3"

    def record(self, endpoint: str, form: dict[str, list[str]]) -> int:
        if endpoint not in INTERACTION_ROUTES:
            raise ValueError("a supported interaction and submitted form are required")
        document = _canonical_form(form)
        fingerprint = _fingerprint(endpoint, document)
        received = datetime.now(timezone.utc).isoformat()
        self.root.mkdir(parents=True, exist_ok=True)
        # Each worker has its own connection. SQLite serializes commits across
        # threads/processes; the default synchronous mode protects the receipt.
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection, connection:
            # Serialize schema upgrades and identical retries across workers.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY,
                endpoint TEXT NOT NULL,
                received_at TEXT NOT NULL,
                form TEXT NOT NULL,
                fingerprint TEXT,
                attempts INTEGER NOT NULL DEFAULT 1,
                last_received_at TEXT
            )""")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(receipts)")}
            for column, definition in (("fingerprint", "TEXT"),
                                       ("attempts", "INTEGER NOT NULL DEFAULT 1"),
                                       ("last_received_at", "TEXT")):
                if column not in columns:
                    connection.execute(f"ALTER TABLE receipts ADD COLUMN {column} {definition}")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                # Preserve every legacy receipt, including earlier duplicates.
                # Only the first matching row anchors future identical retries.
                # Canonicalize parsed JSON: escaping, whitespace and object key
                # order never distinguish otherwise identical submitted forms.
                # Preserve the original stored form bytes and attempt counts.
                connection.execute("UPDATE receipts SET fingerprint = NULL")
                seen = set()
                rows = connection.execute("SELECT id, endpoint, form FROM receipts ORDER BY id").fetchall()
                for identifier, route, prior_form in rows:
                    try:
                        prior = json.loads(prior_form, object_pairs_hook=_unique_json_object)
                        digest = _fingerprint(route, _canonical_form(prior))
                    except (TypeError, ValueError, UnicodeError):
                        raise sqlite3.DatabaseError("invalid legacy interaction receipt") from None
                    if digest not in seen:
                        connection.execute("UPDATE receipts SET fingerprint = ? WHERE id = ?", (digest, identifier))
                        seen.add(digest)
                connection.execute("PRAGMA user_version = 1")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS receipts_fingerprint ON receipts(fingerprint)")
            existing = connection.execute("SELECT id FROM receipts WHERE fingerprint = ?", (fingerprint,)).fetchone()
            if existing:
                connection.execute(
                    "UPDATE receipts SET attempts = attempts + 1, last_received_at = ? WHERE id = ?",
                    (received, existing[0]),
                )
                return existing[0]
            cursor = connection.execute(
                "INSERT INTO receipts (endpoint, received_at, form, fingerprint, last_received_at) VALUES (?, ?, ?, ?, ?)",
                (endpoint, received, document, fingerprint, received),
            )
            identifier = cursor.lastrowid
        return identifier

    def submit(self, endpoint: str, form: dict[str, list[str]]) -> InteractionReceipt:
        """Return existing channel XML only after ``record`` has committed.

        Request field meanings and identity eligibility remain unverified. This
        method does not turn a receipt into a counted vote, purchase, or notice.
        A legacy static XML response alone is not evidence of submission.
        """
        if endpoint not in INTERACTION_ROUTES:
            raise ValueError("a supported interaction is required")
        # Resolve the existing response before storing; a missing response must
        # not create a receipt that the service cannot acknowledge. Lazy import
        # keeps the durable store independently usable without catalog modules.
        from .wii_no_ma import get_response
        response = get_response(endpoint)
        if response is None:
            raise ValueError("interaction response is unavailable")
        identifier = self.record(endpoint, form)
        return InteractionReceipt(identifier, response)

    def receipts(self, endpoint: str | None = None) -> list[dict[str, object]]:
        if not self.database_path.is_file():
            return []
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(receipts)")}
            attempts = "attempts" if "attempts" in columns else "1"
            last_received = "COALESCE(last_received_at, received_at)" if "last_received_at" in columns else "received_at"
            query = f"SELECT id, endpoint, received_at, form, {attempts}, {last_received} FROM receipts"
            parameters = ()
            if endpoint is not None:
                query += " WHERE endpoint = ?"
                parameters = (endpoint,)
            rows = connection.execute(query + " ORDER BY id", parameters).fetchall()
        return [{"id": identifier, "endpoint": route, "received_at": received,
                 "form": json.loads(form), "attempts": attempts, "last_received_at": last_received}
                for identifier, route, received, form, attempts, last_received in rows]
