from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from jwc24.wii_no_ma_interactions import InteractionStore, INTERACTION_ROUTES


class InteractionStoreTests(unittest.TestCase):
    def test_identical_retries_from_concurrent_workers_reuse_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def submit(_):
                return InteractionStore(root).record("/url2/enquete.cgi", {"choice0": ["1"], "enqid": ["2"]})
            with ThreadPoolExecutor(max_workers=4) as workers:
                identifiers = list(workers.map(submit, range(8)))
            self.assertEqual(len(set(identifiers)), 1)
            receipts = InteractionStore(root).receipts()
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0]["attempts"], 8)
            changed = InteractionStore(root).record("/url2/enquete.cgi", {"choice0": ["2"], "enqid": ["2"]})
            self.assertNotEqual(changed, identifiers[0])

    def test_legacy_receipts_upgrade_without_deleting_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = InteractionStore(root)
            form = {"eval0": ["1"], "movieid": ["2"]}
            document = json.dumps(form, sort_keys=True)
            connection = sqlite3.connect(store.database_path)
            try:
                connection.execute("CREATE TABLE receipts (id INTEGER PRIMARY KEY, endpoint TEXT, received_at TEXT, form TEXT)")
                connection.executemany("INSERT INTO receipts VALUES (?, ?, ?, ?)",
                    [(5, "/url2/evaluate.cgi", "prior", document), (6, "/url2/evaluate.cgi", "prior", document)])
                connection.commit()
            finally:
                connection.close()
            self.assertEqual(len(store.receipts()), 2)
            self.assertEqual(store.record("/url2/evaluate.cgi", form), 5)
            reopened = InteractionStore(root).receipts()
            self.assertEqual([row["id"] for row in reopened], [5, 6])
            self.assertEqual(reopened[0]["attempts"], 2)
            self.assertEqual(reopened[1]["form"], form)

    def test_submissions_survive_restart_with_unicode_and_repeated_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            form = {"wiiid": ["0000000000000000"], "choice0": ["1"], "note": ["日本語", "二番"]}
            store = InteractionStore(root)
            for route in sorted(INTERACTION_ROUTES):
                store.record(route, form)
            reopened = InteractionStore(root)
            self.assertEqual(len(reopened.receipts()), len(INTERACTION_ROUTES))
            self.assertEqual(reopened.receipts("/url2/enquete.cgi")[0]["form"], form)
            self.assertEqual(reopened.receipts("/unrelated"), [])

    def test_empty_or_unsupported_submissions_do_not_create_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory) / "receipts")
            for route, form in (("/url2/enquete.cgi", {}), ("/url2/pay/verify.cgi", {"q": ["x"]}),
                                ("/url2/enquete.cgi", {"choice0": "1"})):
                with self.assertRaises(ValueError):
                    store.record(route, form)
            self.assertFalse(store.root.exists())

    def test_concurrent_submissions_are_not_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def submit(index):
                return InteractionStore(root).record("/url2/evaluate.cgi", {"movieid": [str(index)]})
            with ThreadPoolExecutor(max_workers=4) as workers:
                identifiers = list(workers.map(submit, range(16)))
            self.assertEqual(len(set(identifiers)), 16)
            self.assertEqual(len(InteractionStore(root).receipts()), 16)

    def test_storage_corruption_is_reported_without_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            store = InteractionStore(Path(directory))
            before = b"invalid existing database"
            store.database_path.write_bytes(before)
            with self.assertRaises(sqlite3.DatabaseError):
                store.record("/url2/evaluate.cgi", {"eval0": ["1"]})
            self.assertEqual(store.database_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
