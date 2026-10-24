"""Serve a narrowly reviewed script from the private 2019 collector capture."""
import hashlib
import json
from pathlib import Path

ARCHIVE_SHA1 = 'e20c789c86bd602d7af3816d105c3f62ab504374'
SOURCE = 'https://archive.org/details/WiiShopChannelBackup'
KEYBOARD_SHA256 = '400739e24fc85e592812b06866188ba5ccc3aec4da4341f2b9546936087a0103'
KEYBOARD_URL = '/assets/captured/keyboard.js'


class CapturedScripts:
    def __init__(self, root):
        root = Path(root).resolve()
        path = root/'manifest.private.json'
        if path.stat().st_size > 2*1024*1024:
            raise ValueError('Oversized capture manifest')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if manifest.get('source') != SOURCE or manifest.get('archive_sha1') != ARCHIVE_SHA1:
            raise ValueError('Unexpected storefront capture source')
        rows = [r for r in manifest['files'] if r['member'].endswith('/common/js/keyboard.js')]
        if len(rows) != 1:
            raise ValueError('Missing or ambiguous captured keyboard script')
        row = rows[0]
        if row['sha256'] != KEYBOARD_SHA256 or row['file'] != 'blobs/'+KEYBOARD_SHA256:
            raise ValueError('Unexpected captured keyboard fingerprint/path')
        local = (root/row['file']).resolve()
        if not local.is_relative_to(root) or local.stat().st_size != 1426 or row['bytes'] != 1426:
            raise ValueError('Captured keyboard size/path differs')
        self.keyboard = local.read_bytes()
        if hashlib.sha256(self.keyboard).hexdigest() != KEYBOARD_SHA256:
            raise ValueError('Captured keyboard fingerprint mismatch')

    def asset(self, path):
        if path == KEYBOARD_URL:
            return 200, 'text/javascript; charset=Shift_JIS', self.keyboard
        return 404, 'text/plain', b'Captured script not found'

    def script_tags(self):
        return '<script type="text/javascript" charset="Shift_JIS" src="'+KEYBOARD_URL+'"></script>'
