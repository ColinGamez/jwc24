"""Synthetic local submission checks; no original votes or device identity."""
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from jwc24.wii_no_ma_interactions import INTERACTION_ROUTES, InteractionStore


class WiiNoMaSubmissionTests(unittest.TestCase):
    def test_each_acknowledgment_is_backed_by_a_reopened_receipt(self):
        roots = {
            "/url2/evaluate.cgi": ("Evaluate", "1"),
            "/url2/pay/pevaluate.cgi": ("PayEvaluate", "1"),
            "/url2/enquete.cgi": ("Enquete", "2"),
            "/url2/piceval.cgi": ("PicEval", "1"),
        }
        self.assertEqual(set(roots), set(INTERACTION_ROUTES))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            form = {"wiiid": ["0000000000000000"], "synthetic": ["日本語", "二番"]}
            for endpoint, (name, code) in roots.items():
                result = InteractionStore(root).submit(endpoint, form)
                xml = ET.fromstring(result.response)
                self.assertEqual(xml.tag, name)
                self.assertEqual(xml.findtext("code"), code)
                self.assertEqual(xml.findtext("ver"), "399")
                receipt, = InteractionStore(root).receipts(endpoint)
                self.assertEqual(receipt["id"], result.identifier)
                self.assertEqual(receipt["form"], form)
                self.assertEqual(receipt["attempts"], 1)

    def test_insert_failure_returns_no_acknowledgment_or_new_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory))
            original = store.submit("/url2/evaluate.cgi", {"synthetic": ["first"]})
            with closing(sqlite3.connect(store.database_path)) as connection, connection:
                connection.execute("""CREATE TRIGGER reject_receipts BEFORE INSERT ON receipts
                    BEGIN SELECT RAISE(ABORT, 'synthetic insert failure'); END""")
            with self.assertRaises(sqlite3.IntegrityError):
                store.submit("/url2/evaluate.cgi", {"synthetic": ["second"]})
            rows = InteractionStore(store.root).receipts()
            self.assertEqual([row["id"] for row in rows], [original.identifier])
            self.assertEqual(rows[0]["form"], {"synthetic": ["first"]})

    def test_retry_update_failure_preserves_attempt_count(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory))
            form = {"synthetic": ["retry"]}
            store.submit("/url2/enquete.cgi", form)
            with closing(sqlite3.connect(store.database_path)) as connection, connection:
                connection.execute("""CREATE TRIGGER reject_retry BEFORE UPDATE OF attempts ON receipts
                    BEGIN SELECT RAISE(ABORT, 'synthetic retry failure'); END""")
            with self.assertRaises(sqlite3.IntegrityError):
                store.submit("/url2/enquete.cgi", form)
            self.assertEqual(store.receipts()[0]["attempts"], 1)

    def test_missing_response_and_invalid_forms_create_no_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory) / "unused")
            with patch("jwc24.wii_no_ma.get_response", return_value=None):
                with self.assertRaises(ValueError):
                    store.submit("/url2/enquete.cgi", {"synthetic": ["1"]})
            for endpoint, form in (
                ("/url2/pay/verify.cgi", {"synthetic": ["1"]}),
                ("/url2/enquete.cgi", None),
                ("/url2/enquete.cgi", {}),
                ("/url2/enquete.cgi", {"synthetic": []}),
                ("/url2/enquete.cgi", {"synthetic": "1"}),
                ("/url2/enquete.cgi", {"synthetic": ["\ud800"]}),
            ):
                with self.subTest(endpoint=endpoint, form=form):
                    with self.assertRaises((ValueError, UnicodeError)):
                        store.submit(endpoint, form)
            self.assertFalse(store.root.exists())

    def test_migration_canonicalizes_json_without_rewriting_legacy_forms(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory))
            form = {"z": ["日本語", "二番"], "a": ["1"]}
            documents = [json.dumps(form), json.dumps(form, ensure_ascii=False, indent=2)]
            with closing(sqlite3.connect(store.database_path)) as connection, connection:
                connection.execute("CREATE TABLE receipts (id INTEGER PRIMARY KEY, endpoint TEXT, received_at TEXT, form TEXT)")
                connection.executemany("INSERT INTO receipts VALUES (?, ?, ?, ?)", [
                    (identifier, "/url2/enquete.cgi", "legacy", document)
                    for identifier, document in zip((5, 6), documents)
                ])
            result = store.submit("/url2/enquete.cgi", form)
            self.assertEqual(result.identifier, 5)
            self.assertEqual([row["id"] for row in store.receipts()], [5, 6])
            with closing(sqlite3.connect(store.database_path)) as connection, connection:
                rows = connection.execute("SELECT form, attempts FROM receipts ORDER BY id").fetchall()
                self.assertEqual(rows, [(documents[0], 2), (documents[1], 1)])
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)

    def test_migration_also_repairs_prior_noncanonical_fingerprints(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory))
            form = {"synthetic": ["日本語"]}
            with closing(sqlite3.connect(store.database_path)) as connection, connection:
                connection.execute("""CREATE TABLE receipts (id INTEGER PRIMARY KEY, endpoint TEXT,
                    received_at TEXT, form TEXT, fingerprint TEXT, attempts INTEGER,
                    last_received_at TEXT)""")
                connection.execute("CREATE UNIQUE INDEX receipts_fingerprint ON receipts(fingerprint)")
                connection.execute("INSERT INTO receipts VALUES (8, ?, ?, ?, ?, 4, ?)",
                    ("/url2/piceval.cgi", "first", json.dumps(form), "prior-noncanonical-digest", "last"))
            self.assertEqual(store.submit("/url2/piceval.cgi", form).identifier, 8)
            self.assertEqual(store.receipts()[0]["attempts"], 5)

    def test_bad_legacy_json_rolls_back_schema_upgrade_without_acknowledgment(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory))
            with closing(sqlite3.connect(store.database_path)) as connection, connection:
                connection.execute("CREATE TABLE receipts (id INTEGER PRIMARY KEY, endpoint TEXT, received_at TEXT, form TEXT)")
                connection.execute("INSERT INTO receipts VALUES (1, ?, 'legacy', ?)",
                                   ("/url2/evaluate.cgi", "invalid prior JSON"))
            with self.assertRaises(sqlite3.DatabaseError):
                store.submit("/url2/evaluate.cgi", {"synthetic": ["1"]})
            with closing(sqlite3.connect(store.database_path)) as connection, connection:
                self.assertEqual(connection.execute("SELECT form FROM receipts").fetchall(), [("invalid prior JSON",)])
                self.assertEqual([row[1] for row in connection.execute("PRAGMA table_info(receipts)")],
                                 ["id", "endpoint", "received_at", "form"])
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
    def test_duplicate_legacy_keys_roll_back_every_row_and_schema_change(self):
        for ambiguous in (
            '{"synthetic": ["first"], "synthetic": ["second"]}',
            r'{"synthetic": ["first"], "\u0073ynthetic": ["second"]}',
        ):
            with self.subTest(document=ambiguous), tempfile.TemporaryDirectory() as directory:
                store = InteractionStore(Path(directory))
                before = [
                    (1, "/url2/enquete.cgi", "legacy-first", '{"valid": ["preserved"]}'),
                    (2, "/url2/enquete.cgi", "legacy-second", ambiguous),
                ]
                with closing(sqlite3.connect(store.database_path)) as connection, connection:
                    connection.execute("CREATE TABLE receipts (id INTEGER PRIMARY KEY, endpoint TEXT, received_at TEXT, form TEXT)")
                    connection.executemany("INSERT INTO receipts VALUES (?, ?, ?, ?)", before)
                with self.assertRaises(sqlite3.DatabaseError):
                    store.submit("/url2/enquete.cgi", {"synthetic": ["second"]})
                with closing(sqlite3.connect(store.database_path)) as connection, connection:
                    self.assertEqual(connection.execute("SELECT * FROM receipts ORDER BY id").fetchall(), before)
                    self.assertEqual([row[1] for row in connection.execute("PRAGMA table_info(receipts)")],
                                     ["id", "endpoint", "received_at", "form"])
                    self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)
                    self.assertEqual(connection.execute("PRAGMA index_list(receipts)").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
