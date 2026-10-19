"""Offline Japan Post address directory, preserving ambiguous postal matches."""
import csv
from contextlib import closing
import io
import re
import sqlite3
from pathlib import Path

SOURCE_URL = 'https://www.post.japanpost.jp/service/search/zipcode/download/utf-zip.html'
DOWNLOAD_URL = 'https://www.post.japanpost.jp/service/search/zipcode/download/utf/zip/utf_ken_all.zip'
MAX_CSV_BYTES = 64 * 1024 * 1024


def records(data):
    if len(data) > MAX_CSV_BYTES:
        raise ValueError('Postal CSV exceeds import limit')
    for number, row in enumerate(csv.reader(io.StringIO(data.decode('utf-8-sig')), strict=True), 1):
        if number > 250000 or len(row) != 15:
            raise ValueError('Invalid postal CSV structure')
        municipality, postal = row[0], row[2]
        if not re.fullmatch(r'[0-9]{5}', municipality) or not re.fullmatch(r'[0-9]{7}', postal):
            raise ValueError('Invalid postal or municipality code')
        if not 1 <= int(municipality[:2]) <= 47:
            raise ValueError('Invalid prefecture code')
        names = row[6:9]
        if any(not name or len(name) > 2048 or '\0' in name for name in names):
            raise ValueError('Invalid postal address name')
        yield (postal, municipality, 'JP-' + municipality[:2], *names,
               'municipality_default' if names[2] == '以下に掲載がない場合' else 'town')


def build_database(data, destination):
    """Build a new staging database; callers atomically publish only on success."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Refusing to overwrite an existing database')
    with closing(sqlite3.connect(destination)) as db, db:
        db.execute('CREATE TABLE addresses(postal TEXT, municipality TEXT, prefecture_id TEXT, prefecture TEXT, city TEXT, town TEXT, kind TEXT, UNIQUE(postal,municipality,prefecture,city,town))')
        db.execute('CREATE INDEX postal_lookup ON addresses(postal)')
        db.execute('CREATE INDEX area_lookup ON addresses(prefecture_id,municipality)')
        db.execute('CREATE INDEX town_lookup ON addresses(municipality)')
        db.executemany('INSERT OR IGNORE INTO addresses VALUES(?,?,?,?,?,?,?)', records(data))
        db.execute('PRAGMA user_version=1')
        count = db.execute('SELECT count(*) FROM addresses').fetchone()[0]
        prefectures = db.execute('SELECT count(DISTINCT prefecture_id) FROM addresses').fetchone()[0]
    return {'records': count, 'prefectures': prefectures}


def lookup(database, postal):
    """Return all matches; never choose a street or house for the caller."""
    if not isinstance(postal, str) or not re.fullmatch(r'[0-9]{7}', postal):
        raise ValueError('Postal lookup requires seven ASCII digits')
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute('SELECT * FROM addresses WHERE postal=? ORDER BY municipality,city,town', (postal,))]


def areas(database, parent=None):
    """Public geographic navigation using JIS IDs, not recovered native API IDs.

    None lists prefectures; JP-xx lists municipalities; a five-digit JIS code
    lists postal towns. Defaults stay explicit and ambiguous codes stay intact.
    """
    if parent is None:
        query = 'SELECT DISTINCT prefecture_id AS id, prefecture AS name FROM addresses ORDER BY id'
        parameters = ()
    elif isinstance(parent, str) and re.fullmatch(r'JP-(0[1-9]|[1-3][0-9]|4[0-7])', parent):
        query = 'SELECT DISTINCT municipality AS id, city AS name FROM addresses WHERE prefecture_id=? ORDER BY id,name'
        parameters = (parent,)
    elif isinstance(parent, str) and re.fullmatch(r'[0-9]{5}', parent) and 1 <= int(parent[:2]) <= 47:
        query = 'SELECT DISTINCT postal, town AS name, kind FROM addresses WHERE municipality=? ORDER BY postal,name'
        parameters = (parent,)
    else:
        raise ValueError('Invalid geographic parent identifier')
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(query, parameters)]
