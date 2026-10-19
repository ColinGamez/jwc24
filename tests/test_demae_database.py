from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from contextlib import closing

from jwc24.demae_database import DemaeDatabase
from jwc24.mail import MailStore


class DemaeDatabaseTests(unittest.TestCase):
    def reviewed_batch(self):
        timestamp = '2026-10-18T00:00:00+00:00'
        reviews, observations = [], []
        for index, name in enumerate(('Source A', 'Source B'), 1):
            identifier = f'hotpepper:J{index:09d}'
            url = f'https://demae-can.com/shop/menu/{index}'
            reviews.append({'restaurant_id': identifier, 'provider_name': name,
                'provider_address': 'Source address', 'provider_url': url, 'verified_at': timestamp})
            observations.append({'restaurant_id': identifier, 'source_url': url,
                'observed_at': timestamp, 'items': [{'name': 'Source item', 'category': 'Source category',
                'listed_price_yen': 850, 'options_observed': False}]})
        return timestamp, reviews, observations

    def test_reviewed_menu_batch_rejects_all_records_if_one_branch_is_wrong(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            archive.ingest(self.catalog())
            timestamp, reviews, observations = self.reviewed_batch()
            observations[1]['source_url'] = observations[0]['source_url']
            with self.assertRaises(ValueError):
                archive.ingest_reviewed_menus(reviews, observations, now=timestamp)
            self.assertEqual(archive.stats()['evidence_records'], 0)

    def test_reviewed_menu_batch_is_idempotent_and_requires_paired_current_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            archive.ingest(self.catalog())
            timestamp, reviews, observations = self.reviewed_batch()
            for _ in range(2):
                archive.ingest_reviewed_menus(reviews, observations, now=timestamp)
            self.assertEqual(archive.stats()['evidence_records'], 4)
            with self.assertRaises(ValueError):
                archive.ingest_reviewed_menus(reviews, observations[:1], now=timestamp)
            with self.assertRaises(ValueError):
                archive.ingest_reviewed_menus(reviews, observations, now='2026-10-20T00:00:00+00:00')
            self.assertEqual(archive.stats()['evidence_records'], 4)

    def catalog(self, names=('Source A', 'Source B')):
        return [{'provider': 'hotpepper', 'prefecture_id': 'JP-10', 'restaurants': [
            {'id': f'hotpepper:J{index:09d}', 'name': name, 'address': 'Source address'}
            for index, name in enumerate(names, 1)]}]

    def test_partial_and_empty_refresh_preserve_records_and_do_not_create_closures(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            archive.ingest(self.catalog())
            archive.ingest(self.catalog(('Source A updated',)))
            archive.ingest([])
            reopened = DemaeDatabase(archive.path)
            stats = reopened.stats()
            self.assertEqual(stats['restaurants'], 2)
            self.assertEqual(stats['restaurant_versions'], 3)
            self.assertEqual(stats['confirmed_closures'], 0)
            self.assertEqual(stats['closure_notice_events'], 0)
            rows = reopened.catalogs()[0]['restaurants']
            self.assertEqual([row['name'] for row in rows], ['Source A updated', 'Source B'])

    def test_refresh_is_idempotent_and_invalid_evidence_rolls_back_entire_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            archive.ingest(self.catalog())
            archive.ingest(self.catalog())
            self.assertEqual(archive.stats()['restaurant_versions'], 2)
            with self.assertRaises(ValueError):
                archive.ingest(self.catalog(('Bad update',)), reviews=[{'restaurant_id': 'hotpepper:J999999999'}])
            self.assertEqual(archive.catalogs()[0]['restaurants'][0]['name'], 'Source A')
            self.assertEqual(archive.stats()['restaurant_versions'], 2)

    def test_verified_closure_retains_history_and_queues_one_notice_per_follower(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            archive.ingest(self.catalog())
            recipient = '1234567890123456'
            identifier = 'hotpepper:J000000001'
            archive.follow_restaurant(identifier, recipient)
            archive.follow_restaurant(identifier, recipient)
            closure = dict(source_url='https://example.com/permanent-closure', reason='Reviewed official closure announcement',
                           reviewed_at=datetime.now(timezone.utc).isoformat())
            self.assertTrue(archive.record_permanent_closure(identifier, **closure))
            self.assertFalse(archive.record_permanent_closure(identifier, **closure))
            archive.ingest(self.catalog())  # Old source listings cannot reopen it.
            self.assertEqual(archive.stats()['restaurants'], 2)
            self.assertEqual(archive.stats()['closure_notice_events'], 1)
            self.assertEqual(len(archive.catalogs()[0]['restaurants']), 1)
            self.assertEqual(len(archive.catalogs(include_closed=True)[0]['restaurants']), 2)
            with self.assertRaises(ValueError):
                archive.follow_restaurant(identifier, recipient)
            mail = MailStore(Path(temporary)/'mail')
            with self.assertRaises(ValueError):
                archive.dispatch_closure_notices(mail)
            mail.register(recipient)
            self.assertEqual(archive.dispatch_closure_notices(mail), 1)
            self.assertEqual(archive.dispatch_closure_notices(mail), 0)
            self.assertEqual(len(mail.pending(recipient)), 1)

    def test_backup_reopens_with_all_history_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            archive.ingest(self.catalog())
            backup = archive.backup(Path(temporary)/'backups/first.sqlite')
            restored = DemaeDatabase(backup)
            self.assertEqual(restored.stats(), archive.stats())
            self.assertEqual(restored.catalogs(), archive.catalogs())
            with self.assertRaises(FileExistsError):
                archive.backup(backup)

    def test_menu_archive_keeps_history_and_uses_newest_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            identifier = 'hotpepper:J000000001'
            timestamp = '2026-10-18T00:00:00+00:00'
            review = {'restaurant_id': identifier, 'provider_name': 'Source A',
                'provider_address': 'Source address', 'provider_url': 'https://demae-can.com/shop/menu/123',
                'verified_at': timestamp}
            observation = {'restaurant_id': identifier, 'source_url': review['provider_url'],
                'observed_at': timestamp, 'items': [{'name': 'Source item', 'category': 'Source category',
                    'listed_price_yen': 850, 'options_observed': False}]}
            archive.ingest(self.catalog(), reviews=[review], observations=[observation])
            older = dict(observation, observed_at='2026-10-17T00:00:00+00:00',
                         items=[dict(observation['items'][0], listed_price_yen=800)])
            archive.ingest([], observations=[older])
            self.assertEqual(archive.stats()['evidence_records'], 3)
            menu = archive.menu_directory().menu(identifier, now=datetime.fromisoformat(timestamp))
            self.assertEqual(menu['items'][0]['listed_price_yen'], 850)
            backup = archive.backup(Path(temporary)/'backup.sqlite')
            self.assertEqual(DemaeDatabase(backup).menu_directory().menu(
                identifier, now=datetime.fromisoformat(timestamp)), menu)

    def test_unknown_future_schema_is_rejected_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = DemaeDatabase(Path(temporary)/'demae.sqlite')
            with closing(sqlite3.connect(archive.path)) as db:
                db.execute('PRAGMA user_version=99')
            with self.assertRaises(ValueError):
                DemaeDatabase(archive.path)
            with closing(sqlite3.connect(archive.path)) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 99)
