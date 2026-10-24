"""Read historical title facts from reviewed Shop detail captures; no commerce."""
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE

FIELDS = ('TitleName1', 'Publisher', 'date', 'Players', 'DisplayCategory', 'Platform', 'price')
VOID = {'img', 'input', 'br', 'hr', 'meta', 'link', 'area', 'base', 'wbr', 'source'}


class DetailFields(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.active, self.fields = [], [], {}
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        identifier = dict(attrs).get('id')
        selected = identifier if identifier in FIELDS else None
        if selected:
            if selected in self.fields:
                raise ValueError('Duplicate captured display field')
            self.fields[selected] = []
            self.active.append(selected)
        if tag == 'br' and not self.ignored:
            for field in self.active:
                self.fields[field].append(' ')
        if tag not in VOID:
            skip = tag in ('script', 'style')
            self.stack.append((tag, selected, skip))
            self.ignored += skip
        elif selected:
            self.active.remove(selected)

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, -1, -1):
            if self.stack[index][0] == tag:
                for _, selected, skip in self.stack[index:]:
                    self.ignored -= skip
                    if selected:
                        self.active.remove(selected)
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        if not self.ignored:
            for field in self.active:
                self.fields[field].append(data)


def parse_detail(data, expected_id):
    if not re.fullmatch('[0-9A-F]{16}', expected_id) or len(data) > 2*1024*1024:
        raise ValueError('Captured detail outside bounds')
    source = data.decode('utf-8-sig')
    identifiers = re.findall(r'\bvar\s+titleId\s*=\s*["\x27]([A-Fa-f0-9]{16})["\x27]', source)
    if not identifiers or any(value.upper() != expected_id for value in identifiers):
        raise ValueError('Captured request and internal title ID disagree')
    parser = DetailFields()
    parser.feed(source)
    fields = {key: ' '.join(''.join(value).split()) for key, value in parser.fields.items()}
    if not fields.get('TitleName1') or any('\ufffd' in value for value in fields.values()):
        raise ValueError('Captured title is missing or has decoding substitutions')
    if any(len(value) > 512 or any(ord(c) < 32 for c in value) for value in fields.values()):
        raise ValueError('Captured title field outside bounds')
    points = None
    literals = [number for _, number in re.findall(r'\bvar\s+titlePoints\s*=\s*(["\x27]?)(\d+)\1\s*;', source)]
    displayed = re.fullmatch(r'([0-9]+(?:,[0-9]{3})*)\s*(?:Wii Points|Wiiポイント)', fields.get('price', ''))
    if literals and len(set(literals)) == 1 and displayed:
        value = int(literals[0])
        if value == int(displayed[1].replace(',', '')) and 0 <= value <= 100000:
            points = value
    return {'title': fields['TitleName1'], 'publisher': fields.get('Publisher') or None,
            'points': points, 'captured_display_date': fields.get('date') or None,
            'captured_player_text': fields.get('Players') or None,
            'captured_platform_text': fields.get('Platform') or None,
            'captured_genre_text': fields.get('DisplayCategory') or None,
            'capture_sha256': hashlib.sha256(data).hexdigest()}


class TitleMetadata:
    def __init__(self, path, catalog_digest, capture_digest=None):
        path = Path(path)
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized historical metadata file')
        data = path.read_bytes()
        document = json.loads(data)
        if (document.get('schema_version') != 1 or document.get('source') != SOURCE
                or document.get('archive_sha1') != ARCHIVE_SHA1
                or document.get('catalog_sha256') != catalog_digest
                or (capture_digest is not None and document.get('capture_manifest_sha256') != capture_digest)
                or not re.fullmatch('[0-9a-f]{64}', document.get('capture_manifest_sha256', ''))):
            raise ValueError('Historical metadata source/catalog mismatch')
        records = document['records']
        if not isinstance(records, dict) or len(records) > 1000:
            raise ValueError('Historical metadata count outside bounds')
        optional = ('publisher', 'captured_display_date', 'captured_player_text',
                    'captured_platform_text', 'captured_genre_text')
        for identifier, row in records.items():
            if (not re.fullmatch('[0-9A-F]{16}', identifier) or not isinstance(row, dict)
                    or set(row) != {'title', 'points', 'capture_sha256', *optional}
                    or not isinstance(row['title'], str) or not row['title'].strip()
                    or not re.fullmatch('[0-9a-f]{64}', row['capture_sha256'])):
                raise ValueError('Historical title lacks identity/provenance')
            if row['points'] is not None and (type(row['points']) is not int or not 0 <= row['points'] <= 100000):
                raise ValueError('Historical points outside bounds')
            for key in ('title', *optional):
                value = row[key]
                if value is not None and (not isinstance(value, str) or len(value) > 512
                                          or '\ufffd' in value or any(ord(c) < 32 for c in value)):
                    raise ValueError('Historical display text outside bounds')
        self.records, self.digest = records, hashlib.sha256(data).hexdigest()

    def get(self, identifier):
        return deepcopy(self.records.get(identifier))
