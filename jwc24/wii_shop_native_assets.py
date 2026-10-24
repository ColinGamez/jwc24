"""Load unchanged v21 browser scripts from a private, fingerprinted pack."""
import hashlib
import json
from pathlib import Path


RESOURCE_SHA256 = '9e4a171c24782be38a88225fda507b5c17120531cf517a6ebd9bd3f8ee580ead'
SCRIPTS = {
    'sound.js': '1da241101239e20084539267183350d2f066ed8e9500d84eeef6087c27c7988a',
    'common.js': '431710d4b723f3875f394fbdb48e7b8e065ba163fbd749c43b7247d55b14fcc3',
    'shop.js': '47d9797ae0bcc68599ca42e4c34c8b576ffc153cdd47d20a9560116201500fc4',
}
PREFIX = '/assets/native/'


class NativeAssets:
    def __init__(self, root):
        root = Path(root).resolve()
        manifest = root/'manifest.json'
        if manifest.stat().st_size > 16384:
            raise ValueError('Oversized native script manifest')
        metadata = json.loads(manifest.read_text(encoding='utf-8'))
        if metadata.get('resource_sha256') != RESOURCE_SHA256 or set(metadata['files']) != set(SCRIPTS):
            raise ValueError('Unexpected native script source')
        self.files = {}
        for name, digest in SCRIPTS.items():
            path = (root/name).resolve()
            if not path.is_relative_to(root) or path.stat().st_size > 65536:
                raise ValueError('Native script outside pack bounds')
            data = path.read_bytes()
            row = metadata['files'][name]
            if (hashlib.sha256(data).hexdigest() != digest or row.get('sha256') != digest
                    or row.get('bytes') != len(data)):
                raise ValueError('Native script fingerprint mismatch')
            self.files[PREFIX+name] = data

    def asset(self, path):
        if path in self.files:
            return 200, 'text/javascript', self.files[path]
        return 404, 'text/plain', b'Native resource not found'

    def script_tags(self):
        return ''.join('<script type="text/javascript" src="'+PREFIX+name+'"></script>' for name in SCRIPTS)
