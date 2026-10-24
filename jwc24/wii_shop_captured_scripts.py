"""Serve reviewed scripts, home layout and shared assets from the private capture."""
import hashlib
import json
import mimetypes
from pathlib import Path
import posixpath
import re

ARCHIVE_SHA1 = 'e20c789c86bd602d7af3816d105c3f62ab504374'
SOURCE = 'https://archive.org/details/WiiShopChannelBackup'
KEYBOARD_SHA256 = '400739e24fc85e592812b06866188ba5ccc3aec4da4341f2b9546936087a0103'
KEYBOARD_URL = '/assets/captured/keyboard.js'
HOME_SHA256 = '4d204a5bc459d0c8c5df8cbed965ff60461036500af59ffb84560367f5c20aaa'
ASSET_PREFIX = '/assets/captured'


class CapturedScripts:
    def __init__(self, root):
        root = Path(root).resolve()
        path = root/'manifest.private.json'
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized capture manifest')
        manifest_data = path.read_bytes()
        self.manifest_sha256 = hashlib.sha256(manifest_data).hexdigest()
        manifest = json.loads(manifest_data)
        if manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1:
            raise ValueError('Unexpected storefront capture source')
        self.root = root
        rows = [r for r in manifest['files'] if r['member'].endswith('/common/js/keyboard.js')]
        if len(rows) != 1:
            raise ValueError('Missing or ambiguous captured keyboard script')
        row = rows[0]
        if row['sha256'] != KEYBOARD_SHA256 or row['file'] != 'blobs/'+KEYBOARD_SHA256:
            raise ValueError('Unexpected captured keyboard fingerprint/path')
        if row['bytes'] != 1426:
            raise ValueError('Captured keyboard size/path differs')
        self.keyboard = self._read(row)
        homes = [r for r in manifest['files'] if r['member'].rsplit('/', 1)[-1].split('?', 1)[0] == 'W_03.jsp']
        if len(homes) != 1 or homes[0]['sha256'] != HOME_SHA256:
            raise ValueError('Missing or unreviewed captured home layout')
        self.home_html = self._read(homes[0])
        self.shared = {}
        total = 0
        for row in manifest['files']:
            member = row['member']
            prefix = 'oss-auth.shop.wii.com'
            if not member.startswith(prefix+'/oss/oss/'):
                continue
            path = member[len(prefix):]
            if posixpath.normpath(path) != path or '?' in path:
                raise ValueError('Noncanonical captured resource path')
            if Path(path).suffix.lower() not in ('.css', '.gif', '.png', '.jpg', '.jpeg', '.bmp'):
                continue  # Other commerce scripts are not enabled.
            if path in self.shared:
                raise ValueError('Duplicate captured resource')
            data = self._read(row)
            total += len(data)
            if total > 16*1024*1024 or len(self.shared) >= 512:
                raise ValueError('Captured shared resources exceed bounds')
            mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            if path.endswith('.css'):
                try:
                    data.decode('utf-8-sig')
                    mime += '; charset=UTF-8'
                except UnicodeDecodeError:
                    data.decode('cp932')
                    mime += '; charset=Shift_JIS'
            self.shared[path] = (mime, data)

    def _read(self, row):
        digest = row['sha256']
        if not re.fullmatch('[0-9a-f]{64}', digest) or row['file'] != 'blobs/'+digest:
            raise ValueError('Unexpected captured resource fingerprint/path')
        local = (self.root/row['file']).resolve()
        if not local.is_relative_to(self.root) or local.stat().st_size > 2*1024*1024:
            raise ValueError('Captured resource outside pack bounds')
        data = local.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Captured resource fingerprint mismatch')
        return data

    def resource_url(self, path):
        path = posixpath.normpath(path)
        if path not in self.shared:
            raise ValueError('Required captured home asset is missing')
        return ASSET_PREFIX+path

    def has_asset(self, path):
        return path.startswith(ASSET_PREFIX+'/') and path[len(ASSET_PREFIX):] in self.shared

    def asset(self, path):
        if path == KEYBOARD_URL:
            return 200, 'text/javascript; charset=Shift_JIS', self.keyboard
        if self.has_asset(path):
            mime, data = self.shared[path[len(ASSET_PREFIX):]]
            return 200, mime, data
        return 404, 'text/plain', b'Captured script not found'

    def script_tags(self):
        return '<script type="text/javascript" charset="Shift_JIS" src="'+KEYBOARD_URL+'"></script>'
