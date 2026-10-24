"""Read a bounded private Japanese game-manual capture without rewriting it.

No Shop route uses this reader. Active HTML/JavaScript requires explicit reviewed
SHA-256 fingerprints; a collector checksum does not establish Nintendo origin.
"""
import hashlib
import json
from pathlib import Path
import re

from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE

ARCHIVE_SHA256 = 'f7f349b8baf06f0f77ba6d413ed87e535378bc746084e24c7d5f59273acacda0'
MAX_TITLES = 8
MAX_FILES = 4096
MAX_BYTES = 32*1024*1024
HOST = 'oss-auth.shop.wii.com'
PREFIX = '/oss/oss/ext/manual/'
MIMES = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
         '.png': 'image/png', '.gif': 'image/gif', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}


def manual_path(member):
    """Return only canonical Japanese game content or that game's shared scripts."""
    match = re.fullmatch(re.escape(HOST+PREFIX)+r'(00010001[0-9A-F]{6}4A)/(FFFD[0-9A-F]{4})/(.+)', member)
    if not match:
        return None
    title, version, suffix = match.groups()
    if (any(part in ('', '.', '..') for part in suffix.split('/'))
            or re.search(r'[\\%?#:\x00-\x20\x7f]', suffix)
            or Path(suffix).suffix.lower() not in MIMES):
        return None
    if not (suffix.startswith(f'html/{title}/JPN/ja/')
            or re.fullmatch(r'js/[A-Za-z0-9_-]+\.js', suffix)):
        return None
    return title, version, suffix


class CapturedManuals:
    def __init__(self, root, *, reviewed_active_sha256=()):
        self.root = Path(root).resolve()
        manifest_path = self.root/'manifest.private.json'
        if manifest_path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized manual manifest')
        manifest_data = manifest_path.read_bytes()
        manifest = json.loads(manifest_data)
        if (manifest.get('schema_version') != 1 or manifest.get('source') != SOURCE
                or manifest.get('archive_sha1') != ARCHIVE_SHA1
                or manifest.get('archive_sha256') != ARCHIVE_SHA256
                or manifest.get('selection') != 'japanese-game-manuals'):
            raise ValueError('Unexpected manual capture source')
        titles = manifest.get('title_ids')
        files = manifest.get('files')
        if (not isinstance(titles, list) or not 0 < len(titles) <= MAX_TITLES
                or any(not isinstance(t, str) or not re.fullmatch('00010001[0-9A-F]{6}4A', t) for t in titles)
                or len(set(titles)) != len(titles)
                or not isinstance(files, list) or not 0 < len(files) <= MAX_FILES):
            raise ValueError('Manual pack count or identity outside bounds')
        reviewed = frozenset(reviewed_active_sha256)
        if any(not isinstance(d, str) or not re.fullmatch('[0-9a-f]{64}', d) for d in reviewed):
            raise ValueError('Invalid reviewed manual fingerprint')
        self.manifest_sha256 = hashlib.sha256(manifest_data).hexdigest()
        self.resources, self.indexes, versions = {}, {}, {}
        active_digests = set()
        total = 0
        for row in files:
            parsed = manual_path(row['member'])
            if parsed is None or parsed[0] not in titles:
                raise ValueError('Manual resource outside requested Japanese title namespace')
            title, version, suffix = parsed
            if title in versions and versions[title] != version:
                raise ValueError('Ambiguous captured manual version')
            versions[title] = version
            path = row['member'][len(HOST):]
            if path in self.resources:
                raise ValueError('Duplicate manual resource')
            digest, size = row['sha256'], row['bytes']
            if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                    or row['file'] != 'blobs/'+digest or type(size) is not int
                    or not 0 < size <= 2*1024*1024):
                raise ValueError('Manual resource fingerprint/path outside bounds')
            total += size
            if total > MAX_BYTES:
                raise ValueError('Manual pack bytes exceed bounds')
            local = (self.root/row['file']).resolve()
            if not local.is_relative_to(self.root) or local.stat().st_size != size:
                raise ValueError('Manual blob outside pack or size mismatch')
            data = local.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('Manual resource fingerprint mismatch')
            extension = Path(suffix).suffix.lower()
            mime = MIMES[extension]
            active = extension in ('.html', '.js')
            if extension in ('.html', '.js', '.css'):
                try:
                    data.decode('utf-8-sig')
                    mime += '; charset=UTF-8'
                except UnicodeDecodeError:
                    data.decode('cp932')
                    mime += '; charset=Shift_JIS'
            if active:
                active_digests.add(digest)
            self.resources[path] = (mime, data, not active or digest in reviewed)
            if suffix == f'html/{title}/JPN/ja/index.html':
                self.indexes[title] = path
        if set(self.indexes) != set(titles):
            raise ValueError('Requested Japanese manual index is absent')
        if reviewed - active_digests:
            raise ValueError('Reviewed fingerprints are absent from this manual pack')

    def index_url(self, title_id):
        path = self.indexes.get(title_id)
        if path is None or not self.resources[path][2]:
            raise ValueError('Japanese manual index is absent or not reviewed')
        return path

    def has_asset(self, path):
        return path in self.resources

    def asset(self, path):
        resource = self.resources.get(path)
        if resource is None:
            return 404, 'text/plain; charset=UTF-8', b'Captured manual resource not found'
        mime, data, permitted = resource
        if not permitted:
            return 403, 'text/plain; charset=UTF-8', b'Captured manual active content requires review'
        return 200, mime, data
