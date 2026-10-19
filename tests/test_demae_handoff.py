from pathlib import Path
from contextlib import closing
import tempfile
import unittest
import sqlite3
import hashlib
from email import policy
from email.parser import BytesParser
from jwc24.demae_handoff import HandoffStore
from jwc24.mail import MailStore


class HandoffTests(unittest.TestCase):
    def test_restaurant_context_is_snapshotted_and_sessions_stay_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handoffs = HandoffStore(root / 'handoff.sqlite')
            context = {'restaurant_id': 'hotpepper:J000000001', 'name': 'Selected Branch',
                       'provider_url': 'https://demae-can.com/shop/menu/1234567'}
            entry = handoffs.create_entry('1234567890123456', restaurant=context)
            first = handoffs.open_entry(entry)
            context['name'] = 'Changed by caller'
            second = handoffs.open_entry(entry)
            self.assertEqual(handoffs.status(first)['restaurant']['name'], 'Selected Branch')
            self.assertEqual(handoffs.status(second)['provider_url'], context['provider_url'])
            handoffs.confirm(first)
            self.assertFalse(handoffs.status(second)['confirmed'])
            mail = MailStore(root / 'mail')
            mail.register('1234567890123456')
            self.assertEqual(handoffs.dispatch_notices(mail), 1)
            notice = BytesParser(policy=policy.default).parsebytes(mail.pending('1234567890123456')[0].read_bytes())
            self.assertIn('Selected Branch', notice.get_content())
            self.assertIn('not a provider receipt', notice.get_content())

    def test_existing_database_migration_preserves_old_generic_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.sqlite'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('CREATE TABLE handoffs (token_hash TEXT PRIMARY KEY, wii_id TEXT NOT NULL, created INTEGER NOT NULL, expires INTEGER NOT NULL, confirmed INTEGER, notice BLOB, dispatched INTEGER NOT NULL DEFAULT 0)')
                db.execute('CREATE TABLE phone_entries (entry_hash TEXT PRIMARY KEY, wii_id TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)')
                db.execute('INSERT INTO handoffs(token_hash,wii_id,created,expires) VALUES(?,?,?,?)',
                           (hashlib.sha256(('A'*43).encode()).hexdigest(), '1234567890123456', 100, 200))
            store = HandoffStore(path)
            self.assertEqual(store.status('A'*43, now=101)['provider_url'], 'https://demae-can.com/')
            token = store.create('1234567890123456')
            reopened = HandoffStore(path)
            self.assertIsNone(reopened.status(token)['restaurant'])
            self.assertEqual(reopened.status(token)['provider_url'], 'https://demae-can.com/')

    def test_stable_entry_creates_distinct_unconfirmed_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            handoffs = HandoffStore(Path(directory) / 'handoffs.sqlite')
            entry = handoffs.create_entry('1234567890123456')
            first, second = handoffs.open_entry(entry), handoffs.open_entry(entry)
            self.assertNotEqual(first, second)
            self.assertFalse(handoffs.status(first)['confirmed'])
            self.assertFalse(handoffs.status(second)['notice_queued'])
    def test_unavailable_mail_recipient_retains_confirmed_outbox(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handoffs = HandoffStore(root / 'handoffs.sqlite')
            mail = MailStore(root / 'mail')
            recipient = '1234567890123456'
            token = handoffs.create(recipient, now=100)
            handoffs.confirm(token, now=101)
            with self.assertRaises(ValueError):
                handoffs.dispatch_notices(mail)
            self.assertFalse(handoffs.status(token, now=102)['notice_queued'])
            mail.register(recipient)
            self.assertEqual(handoffs.dispatch_notices(mail), 1)
            self.assertEqual(len(mail.pending(recipient)), 1)

    def test_confirm_then_mail_idempotence_and_expiry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            handoffs = HandoffStore(root / 'handoffs.sqlite')
            mail = MailStore(root / 'mail')
            recipient = '1234567890123456'
            mail.register(recipient)
            token = handoffs.create(recipient, now=100)
            self.assertFalse(handoffs.status(token, now=101)['confirmed'])
            self.assertEqual(handoffs.dispatch_notices(mail), 0)
            handoffs.confirm(token, now=102)
            handoffs.confirm(token, now=103)
            self.assertEqual(handoffs.dispatch_notices(mail), 1)
            self.assertEqual(handoffs.dispatch_notices(mail), 0)
            self.assertEqual(len(mail.pending(recipient)), 1)
            notice = BytesParser(policy=policy.default).parsebytes(mail.pending(recipient)[0].read_bytes())
            self.assertIn('not a provider receipt', notice.get_content())
            self.assertIn('出前館による正式な注文確認ではありません', notice.get_content())
            self.assertIsNone(notice.get('X-Wii-AppId'))
            self.assertEqual(notice['Content-Transfer-Encoding'], 'base64')
            with self.assertRaises(ValueError):
                handoffs.confirm(token, now=86500)
            with self.assertRaises(ValueError):
                handoffs.status('bad', now=104)
