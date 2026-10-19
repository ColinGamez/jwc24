"""Durable phone checkout handoffs and user-confirmed Wii notices."""
from contextlib import closing
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from .mail import MailAccount, normalize_wii_id
from .demae_restaurant_links import validate_context
from .demae_menu import basket_plan

PROVIDER_URL = 'https://demae-can.com/'


class HandoffStore:
    def __init__(self, database):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS handoffs (token_hash TEXT PRIMARY KEY, wii_id TEXT NOT NULL, created INTEGER NOT NULL, expires INTEGER NOT NULL, confirmed INTEGER, notice BLOB, dispatched INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS phone_entries (entry_hash TEXT PRIMARY KEY, wii_id TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)')
            for table in ('handoffs', 'phone_entries'):
                if 'restaurant_json' not in {row[1] for row in db.execute(f'PRAGMA table_info({table})')}:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN restaurant_json TEXT')
            if 'basket_json' not in {row[1] for row in db.execute('PRAGMA table_info(handoffs)')}:
                db.execute('ALTER TABLE handoffs ADD COLUMN basket_json TEXT')

    @staticmethod
    def _hash(token):
        if not isinstance(token, str) or len(token) != 43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):
            raise ValueError('Invalid handoff token')
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, wii_id, *, now=None, restaurant=None, menu=None, selections=None):
        recipient = normalize_wii_id(wii_id)
        instant = time.time() if now is None else now
        created = int(instant)
        token = secrets.token_urlsafe(32)
        context = json.dumps(validate_context(restaurant), ensure_ascii=False) if restaurant is not None else None
        plan = None
        if menu is not None:
            plan = basket_plan(menu, selections, now=datetime.fromtimestamp(instant, timezone.utc))
            if restaurant is None or validate_context(restaurant) != plan['restaurant']:
                raise ValueError('Basket and handoff restaurant differ')
        elif selections is not None:
            raise ValueError('Basket selections require a verified menu')
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('INSERT INTO handoffs(token_hash,wii_id,created,expires,restaurant_json,basket_json) VALUES(?,?,?,?,?,?)',
                       (self._hash(token), recipient, created, created + 86400, context,
                        json.dumps(plan, ensure_ascii=False) if plan else None))
        return token

    def create_entry(self, wii_id, *, restaurant=None):
        """Stable QR entry; each scan creates its own expiring checkout session."""
        recipient = normalize_wii_id(wii_id)
        token = secrets.token_urlsafe(16)
        context = json.dumps(validate_context(restaurant), ensure_ascii=False) if restaurant is not None else None
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('INSERT INTO phone_entries(entry_hash,wii_id,restaurant_json) VALUES(?,?,?)',
                       (hashlib.sha256(token.encode()).hexdigest(), recipient, context))
        return token

    def open_entry(self, token):
        if not isinstance(token, str) or len(token) != 22 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):
            raise ValueError('Invalid phone entry')
        with closing(sqlite3.connect(self.database)) as db:
            row = db.execute('SELECT wii_id,restaurant_json FROM phone_entries WHERE entry_hash=? AND revoked=0',
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if row is None:
            raise ValueError('Phone entry unavailable')
        return self.create(row[0], restaurant=json.loads(row[1]) if row[1] else None)

    def status(self, token, *, now=None):
        current = int(time.time() if now is None else now)
        with closing(sqlite3.connect(self.database)) as db:
            row = db.execute('SELECT expires,confirmed,dispatched,restaurant_json,basket_json FROM handoffs WHERE token_hash=?', (self._hash(token),)).fetchone()
        if row is None or current >= row[0]:
            raise ValueError('Handoff unavailable or expired')
        context = validate_context(json.loads(row[3])) if row[3] else None
        return {'confirmed': row[1] is not None, 'notice_queued': bool(row[2]),
                'provider_url': context['provider_url'] if context else PROVIDER_URL,
                'restaurant': context, 'basket_plan': json.loads(row[4]) if row[4] else None}

    def confirm(self, token, *, now=None):
        current = int(time.time() if now is None else now)
        digest = self._hash(token)
        with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT wii_id,expires,confirmed,restaurant_json FROM handoffs WHERE token_hash=?', (digest,)).fetchone()
            if row is None or current >= row[1]:
                raise ValueError('Handoff unavailable or expired')
            if row[2] is None:
                message = EmailMessage(policy=SMTP)
                message['From'] = 'Demae Channel (JWC24) <demae@jwc24.local>'
                message['To'] = f'w{row[0]}@wii.com'
                message['Date'] = formatdate(current, usegmt=True)
                message['Message-ID'] = f'<handoff-{digest}@jwc24.local>'
                message['Subject'] = 'Demae: order marked complete'
                message.set_content('You marked your phone order as placed on Demae-can.\n\nThis is your confirmation recorded by JWC24, not a provider receipt.\nCheck Demae-can for payment, acceptance, delivery time and order status.\n\nスマートフォンで注文済みと記録しました。\nこのメッセージは、あなたの確認をJWC24が記録したものです。\n出前館による正式な注文確認ではありません。\n受付・支払い・お届け時刻は出前館でご確認ください。\n', charset='utf-8', cte='base64')
                if row[3]:
                    context = validate_context(json.loads(row[3]))
                    message.set_content(message.get_content() + '\nSelected restaurant / 選択したお店:\n'
                                        + context['name'] + '\n' + context['provider_url'] + '\n',
                                        charset='utf-8', cte='base64')
                db.execute('UPDATE handoffs SET confirmed=?,notice=? WHERE token_hash=?', (current, message.as_bytes(), digest))
        return self.status(token, now=current)

    def dispatch_notices(self, mail_store):
        count = 0
        with closing(sqlite3.connect(self.database, timeout=10)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            for digest, payload in db.execute('SELECT token_hash,notice FROM handoffs WHERE confirmed IS NOT NULL AND dispatched=0').fetchall():
                # The notice bytes are persisted before delivery; MailStore's
                # content digest makes retry after a crash idempotent.
                mail_store.store_message(MailAccount('0000000000000000', '', '', ''), payload)
                db.execute('UPDATE handoffs SET dispatched=1 WHERE token_hash=?', (digest,))
                count += 1
        return count
