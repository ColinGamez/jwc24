import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24.wii_shop_captured_empty import CapturedEmpty, STYLESHEETS
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE


class SharedFixture:
    def __init__(self):
        self.shared = {p: ('text/css; charset=UTF-8', b'') for p in STYLESHEETS}
        self.shared['/oss/oss/common/images/notice.gif'] = ('image/gif', b'GIF89a')
        self.shared[STYLESHEETS[0]] = ('text/css; charset=UTF-8', b'body { background:url(../images/notice.gif); }')

    def resource_url(self, path):
        if path not in self.shared:
            raise ValueError('Missing display dependency')
        return '/assets/captured'+path


class CapturedEmptyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = ('''<html><head>'''+''.join('<link href="'+p+'" rel="stylesheet">' for p in STYLESHEETS)+'''
        <script src="/original-disabled.js"></script></head><body>
        <div id="text01-01"><div id="listinfo"><script>document.write("Catalog".replace('x',' '));</script></div></div>
        <div id="text02-01">Your search did not return any results.</div>
        <img src="/oss/oss/common/images//notice.gif"></body></html>''').encode()
        self.digest = hashlib.sha256(self.data).hexdigest()
        (self.root/'blobs').mkdir()
        (self.root/'blobs'/self.digest).write_bytes(self.data)
        self.row = {'member': 'oss-auth.shop.wii.com/oss/serv/B_04.jsp?titleId=0001000141424344',
                    'file': 'blobs/'+self.digest, 'bytes': len(self.data), 'sha256': self.digest}
        self.manifest = {'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1, 'files': [self.row]}
        self.write_manifest()
        for name, value in [('LAYOUT_SHA256', self.digest), ('LAYOUT_BYTES', len(self.data))]:
            patcher = patch('jwc24.wii_shop_captured_empty.'+name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_manifest(self):
        (self.root/'manifest.private.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_reads_script_free_structure_and_checks_css_image(self):
        page = CapturedEmpty(self.root, SharedFixture())
        self.assertEqual(page.layout_html, self.data)
        self.assertIn('/oss/oss/common/images/notice.gif', page.display_dependencies)
        self.assertNotIn('<script', page.parsed_root.render())
        self.assertFalse(page.original_japanese_keyword_empty_state_verified)
        self.assertFalse(page.original_search_again_verified)

    def test_rejects_wrong_source_and_selector(self):
        self.manifest['source'] = 'https://example.invalid/recreation'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'source'):
            CapturedEmpty(self.root, SharedFixture())
        self.manifest['source'] = SOURCE
        self.row['member'] = 'oss-auth.shop.wii.com/oss/serv/B_04.jsp?title=search'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'selector/path'):
            CapturedEmpty(self.root, SharedFixture())

    def test_rejects_changed_bytes_and_missing_transitive_asset(self):
        (self.root/'blobs'/self.digest).write_bytes(b'x'*len(self.data))
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            CapturedEmpty(self.root, SharedFixture())
        (self.root/'blobs'/self.digest).write_bytes(self.data)
        shared = SharedFixture()
        del shared.shared['/oss/oss/common/images/notice.gif']
        with self.assertRaisesRegex(ValueError, 'Missing display dependency'):
            CapturedEmpty(self.root, shared)


if __name__ == '__main__':
    unittest.main()
