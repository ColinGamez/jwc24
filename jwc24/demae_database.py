"""Persistent restaurant archive: source absence never means permanent closure."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime

from .demae_menu_directory import MenuDirectory
from .mail import normalize_wii_id, MailAccount


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _timestamp(value=None):
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Expected a timezone-aware review timestamp')
    return parsed.astimezone(timezone.utc).isoformat()


class DemaeDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError('Unsupported Demae database version')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS restaurants (
                    restaurant_id TEXT PRIMARY KEY, prefecture TEXT NOT NULL,
                    current_json TEXT NOT NULL, first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'listed'
                    CHECK(state IN ('listed','permanently_closed')));
                CREATE INDEX IF NOT EXISTS restaurants_prefecture ON restaurants(prefecture);
                CREATE TABLE IF NOT EXISTS restaurant_versions (
                    restaurant_id TEXT NOT NULL REFERENCES restaurants(restaurant_id),
                    sha256 TEXT NOT NULL, source_json TEXT NOT NULL, captured_at TEXT NOT NULL,
                    PRIMARY KEY(restaurant_id,sha256));
                CREATE TABLE IF NOT EXISTS evidence (
                    restaurant_id TEXT NOT NULL REFERENCES restaurants(restaurant_id),
                    kind TEXT NOT NULL CHECK(kind IN ('branch_review','menu_observation')),
                    sha256 TEXT NOT NULL, source_json TEXT NOT NULL, imported_at TEXT NOT NULL,
                    PRIMARY KEY(restaurant_id,kind,sha256));
                CREATE TABLE IF NOT EXISTS permanent_closures (
                    restaurant_id TEXT PRIMARY KEY REFERENCES restaurants(restaurant_id),
                    source_url TEXT NOT NULL, reason TEXT NOT NULL, reviewed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS closure_notice_events (
                    restaurant_id TEXT PRIMARY KEY REFERENCES permanent_closures(restaurant_id),
                    created_at TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending'
                    CHECK(state IN ('pending','dispatched')));
                CREATE TABLE IF NOT EXISTS restaurant_followers (
                    restaurant_id TEXT NOT NULL REFERENCES restaurants(restaurant_id),
                    wii_id TEXT NOT NULL, PRIMARY KEY(restaurant_id,wii_id));
                CREATE TABLE IF NOT EXISTS closure_notice_deliveries (
                    restaurant_id TEXT NOT NULL REFERENCES permanent_closures(restaurant_id),
                    wii_id TEXT NOT NULL, notice BLOB NOT NULL, dispatched INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(restaurant_id,wii_id));
                PRAGMA user_version=1;
            ''')

    def ingest(self, catalogs, *, reviews=(), observations=(), now=None):
        timestamp = _timestamp(now)
        # Reuse strict catalog identity/prefecture checks. Evidence is preserved
        # even when old; consumers must revalidate freshness before using it.
        incoming = MenuDirectory(catalogs, [], [])
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            for prefecture, identifiers in incoming.prefectures.items():
                for identifier in identifiers:
                    payload = _json(incoming.restaurants[identifier])
                    db.execute('''INSERT INTO restaurants(restaurant_id,prefecture,current_json,first_seen,last_seen)
                        VALUES(?,?,?,?,?) ON CONFLICT(restaurant_id) DO UPDATE SET
                        prefecture=excluded.prefecture,current_json=excluded.current_json,last_seen=excluded.last_seen''',
                        (identifier, prefecture, payload, timestamp, timestamp))
                    db.execute('INSERT OR IGNORE INTO restaurant_versions VALUES(?,?,?,?)',
                        (identifier, hashlib.sha256(payload.encode()).hexdigest(), payload, timestamp))
            known = {row[0] for row in db.execute('SELECT restaurant_id FROM restaurants')}
            for kind, records in (('branch_review', reviews), ('menu_observation', observations)):
                seen = set()
                for record in records:
                    identifier = record.get('restaurant_id') if isinstance(record, dict) else None
                    if identifier not in known or identifier in seen:
                        raise ValueError('Unknown or duplicate restaurant evidence')
                    seen.add(identifier)
                    payload = _json(record)
                    db.execute('INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?)',
                        (identifier, kind, hashlib.sha256(payload.encode()).hexdigest(), payload, timestamp))
        return self.stats()

    def catalogs(self, *, include_closed=False):
        """Preserve missing listings; confirmed closures are hidden, not erased."""
        groups = {}
        with closing(sqlite3.connect(self.path)) as db:
            query = 'SELECT prefecture,current_json FROM restaurants'
            if not include_closed:
                query += " WHERE state!='permanently_closed'"
            for prefecture, payload in db.execute(query+' ORDER BY prefecture,restaurant_id'):
                groups.setdefault(prefecture, []).append(json.loads(payload))
        return [{'provider': 'hotpepper', 'prefecture_id': prefecture, 'restaurants': rows,
                 'scope': 'retained source archive; listing is not delivery eligibility'}
                for prefecture, rows in groups.items()]

    def record_permanent_closure(self, identifier, *, source_url, reason, reviewed_at):
        """Only an explicit reviewed closure creates a pending notice event."""
        if not isinstance(source_url, str):
            raise ValueError('Permanent closure requires an evidence URL')
        parsed = urlsplit(source_url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000):
            raise ValueError('Permanent closure requires an evidence URL and review reason')
        timestamp = _timestamp(reviewed_at)
        if datetime.fromisoformat(timestamp) > datetime.now(timezone.utc):
            raise ValueError('Closure review cannot be in the future')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM restaurants WHERE restaurant_id=?', (identifier,)).fetchone() is None:
                raise ValueError('Unknown restaurant closure')
            existing = db.execute('SELECT 1 FROM permanent_closures WHERE restaurant_id=?', (identifier,)).fetchone()
            if existing:
                return False
            db.execute('INSERT INTO permanent_closures VALUES(?,?,?,?)', (identifier, source_url, reason, timestamp))
            db.execute("UPDATE restaurants SET state='permanently_closed' WHERE restaurant_id=?", (identifier,))
            db.execute('INSERT INTO closure_notice_events(restaurant_id,created_at) VALUES(?,?)', (identifier, timestamp))
            restaurant = json.loads(db.execute('SELECT current_json FROM restaurants WHERE restaurant_id=?',
                                              (identifier,)).fetchone()[0])
            for (recipient,) in db.execute('SELECT wii_id FROM restaurant_followers WHERE restaurant_id=?',
                                            (identifier,)).fetchall():
                message = EmailMessage(policy=SMTP)
                message['From'] = 'Demae Channel (JWC24) <demae@jwc24.local>'
                message['To'] = f'w{recipient}@wii.com'
                message['Date'] = format_datetime(datetime.fromisoformat(timestamp))
                digest = hashlib.sha256((identifier+'\0'+recipient+'\0'+timestamp).encode()).hexdigest()
                message['Message-ID'] = f'<closure-{digest}@jwc24.local>'
                message['Subject'] = 'Demae: restaurant permanently closed'
                message.set_content('A restaurant you follow has been reviewed as permanently closed.\n\n'
                    +restaurant['name']+'\n'+reason+'\n\nSource: '+source_url
                    +'\n\nYour saved restaurant history is retained in JWC24.\n', charset='utf-8', cte='base64')
                db.execute('INSERT INTO closure_notice_deliveries(restaurant_id,wii_id,notice) VALUES(?,?,?)',
                           (identifier, recipient, message.as_bytes()))
        return True

    def menu_directory(self):
        """Read branch/menu evidence from the archive; consumers recheck age."""
        catalogs = self.catalogs()
        available = {row['id'] for catalog in catalogs for row in catalog['restaurants']}
        selected = {'branch_review': {}, 'menu_observation': {}}
        with closing(sqlite3.connect(self.path)) as db:
            for identifier, kind, payload, imported in db.execute(
                    'SELECT restaurant_id,kind,source_json,imported_at FROM evidence ORDER BY imported_at,rowid'):
                if identifier not in available:
                    continue
                record = json.loads(payload)
                field = 'verified_at' if kind == 'branch_review' else 'observed_at'
                try:
                    date = datetime.fromisoformat(_timestamp(record.get(field))) if record.get(field) else None
                except (ValueError, TypeError):
                    date = None
                key = date.timestamp() if date else float('-inf')
                previous = selected[kind].get(identifier)
                if previous is None or key >= previous[0]:
                    selected[kind][identifier] = (key, record)
        return MenuDirectory(catalogs,
            [record for _, record in selected['branch_review'].values()],
            [record for _, record in selected['menu_observation'].values()])

    def ingest_reviewed_menus(self, reviews, observations, *, now=None):
        """Validate an entire menu batch before committing any evidence."""
        timestamp = _timestamp(now)
        moment = datetime.fromisoformat(timestamp)
        current = self.menu_directory()
        def index(records):
            result = {}
            for record in records:
                identifier = record.get('restaurant_id') if isinstance(record, dict) else None
                if identifier not in current.restaurants or identifier in result:
                    raise ValueError('Unknown or duplicate reviewed menu restaurant')
                result[identifier] = record
            return result
        new_reviews, new_observations = index(reviews), index(observations)
        if not new_reviews or new_reviews.keys() != new_observations.keys():
            raise ValueError('Menu import requires a branch review and observation for every restaurant')
        merged_reviews = {**current.reviews, **new_reviews}
        merged_observations = {**current.observations, **new_observations}
        candidate = MenuDirectory(self.catalogs(), list(merged_reviews.values()), list(merged_observations.values()))
        for identifier in new_observations:
            candidate.menu(identifier, now=moment)
        return self.ingest([], reviews=list(new_reviews.values()),
                           observations=list(new_observations.values()), now=timestamp)

    def follow_restaurant(self, identifier, wii_id):
        """Explicitly subscribe a Wii to a restaurant's future closure notice."""
        recipient = normalize_wii_id(wii_id)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            state = db.execute('SELECT state FROM restaurants WHERE restaurant_id=?', (identifier,)).fetchone()
            if state is None or state[0] == 'permanently_closed':
                raise ValueError('Cannot follow unknown or confirmed closed restaurant')
            db.execute('INSERT OR IGNORE INTO restaurant_followers VALUES(?,?)', (identifier, recipient))

    def dispatch_closure_notices(self, mail_store):
        """Deliver persisted notices only to explicit followers; safe to retry."""
        count = 0
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            for identifier, recipient, payload in db.execute(
                    'SELECT restaurant_id,wii_id,notice FROM closure_notice_deliveries WHERE dispatched=0').fetchall():
                mail_store.store_message(MailAccount('0000000000000000', '', '', ''), payload)
                db.execute('UPDATE closure_notice_deliveries SET dispatched=1 WHERE restaurant_id=? AND wii_id=?',
                           (identifier, recipient))
                count += 1
            db.execute("""UPDATE closure_notice_events SET state='dispatched' WHERE NOT EXISTS
                (SELECT 1 FROM closure_notice_deliveries WHERE closure_notice_deliveries.restaurant_id=
                 closure_notice_events.restaurant_id AND dispatched=0)""")
        return count

    def backup(self, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Reserve a new path; never overwrite a previous backup.
        with destination.open('xb'):
            pass
        try:
            with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(destination)) as target:
                source.backup(target)
                if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('Demae backup integrity check failed')
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return destination

    def stats(self):
        with closing(sqlite3.connect(self.path)) as db:
            return {**{key: db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                for key, table in (('restaurants', 'restaurants'), ('restaurant_versions', 'restaurant_versions'),
                    ('evidence_records', 'evidence'), ('confirmed_closures', 'permanent_closures'),
                    ('closure_notice_events', 'closure_notice_events'))},
                'prefectures': db.execute('SELECT COUNT(DISTINCT prefecture) FROM restaurants').fetchone()[0]}
