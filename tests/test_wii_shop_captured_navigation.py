import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24.wii_shop_captured_navigation import CapturedNavigation, SYSTEM_CODES
from jwc24.wii_shop_captured_empty import STYLESHEETS
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE


class NavigationSharedFixture:
    def __init__(self):
        self.shared = {p: ('text/css; charset=UTF-8', b'') for p in STYLESHEETS}
        self.shared[STYLESHEETS[0]] = ('text/css; charset=UTF-8', b'body{background:url(../images/background.gif)}')
        for image in ('visible.gif', 'hover.gif', 'background.gif'):
            self.shared['/oss/oss/common/images/'+image] = ('image/gif', b'GIF89a')
        for code in SYSTEM_CODES:
            self.shared['/oss/oss/ext/attributes/images/platform/'+code.replace('/', '_')+'.gif'] = ('image/gif', b'GIF89a')

    def resource_url(self, path):
        if path not in self.shared:
            raise ValueError('Missing test dependency')
        return '/assets/captured'+path


class CapturedNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'blobs').mkdir()
        head = '<html><head>'+''.join('<link rel="stylesheet" href="'+p+'">' for p in STYLESHEETS)
        head += '<style>.fixture {color:blue}</style></head><body>'
        common = '''<img src="/oss/oss/common/images/visible.gif">
        <script>MM_preloadImages('/oss/oss/common/images/hover.gif');</script>'''
        controls = []
        for number, route in enumerate(('B_04.jsp?popular=true&amp;p=1&amp;vc=true',
                                         'B_04.jsp?order=new&amp;p=1&amp;vc=true',
                                         'B_23.jsp?vc=true'), 1):
            controls.append('<div id="text0'+str(number)+'">Fixture '+str(number)+'</div><div id="spacer0'+str(number)+'"><a href="javascript:showPage(\''+route+'\')">x</a></div>')
        controls.append('''<div id="text04">Fixture title input</div><div id="spacer04"><input id="Image04s" maxlength="40"
        onmousedown="kbd.call(cKT_PredictNoLF, 5, false, 'Fixture prompt')"
        onchange="searchUrl=addParam('B_04.jsp?p=1&amp;vc=true', 'title', searchValue);" /></div>''')
        vc = (head+common+''.join(controls)+'''<script>setUnderButtonL(true, "Back", "javascript:showPage('W_03.jsp')");</script></body></html>''').encode()
        controls = []
        for number, code in enumerate(SYSTEM_CODES, 1):
            suffix = '0'+str(number)
            image = '/oss/oss/ext/attributes/images/platform/'+code.replace('/', '_')+'.gif'
            controls.append('<div id="word'+suffix+'">Fixture '+code+'</div><div id="spacer'+suffix+'"><a href="javascript:showPage(\'B_04.jsp?p=1&amp;vc=true&amp;platform='+code+'\')"><img src="'+image+'"></a></div>')
        self.scroll = b'var scroll_step = 30; function kdown(){return 1;}'
        systems = (head+common+''.join(controls)+'''<script>setUnderButtonL(true, "Back", "javascript:showPage('B_23.jsp')");</script><script>'''+self.scroll.decode()+'''</script></body></html>''').encode()
        pins, member_pins, rows = {}, {}, []
        for page, data in [('B_01.jsp', vc), ('B_03.jsp', systems)]:
            digest = hashlib.sha256(data).hexdigest()
            member = 'oss-auth.shop.wii.com/oss/serv/'+page+'?titleId=fixture'
            (self.root/'blobs'/digest).write_bytes(data)
            pins[page] = (digest, len(data))
            member_pins[page] = hashlib.sha256(member.encode()).hexdigest()
            rows.append({'member': member, 'file': 'blobs/'+digest, 'bytes': len(data), 'sha256': digest})
        self.manifest = {'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1, 'files': rows}
        self.write_manifest()
        for name, value in [('PAGE_PINS', pins), ('MEMBER_PINS', member_pins),
                            ('SYSTEM_SCROLL_SHA256', hashlib.sha256(self.scroll).hexdigest())]:
            patcher = patch('jwc24.wii_shop_captured_navigation.'+name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_manifest(self):
        (self.root/'manifest.private.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_vc_preserves_labels_original_destinations_and_search_constants(self):
        page = CapturedNavigation(self.root, NavigationSharedFixture())
        self.assertEqual([c['label'] for c in page.vc_controls], ['Fixture 1', 'Fixture 2', 'Fixture 3', 'Fixture title input'])
        self.assertEqual(page.vc_controls[0]['query']['popular'], 'true')
        self.assertEqual(page.vc_controls[1]['query']['order'], 'new')
        self.assertEqual(page.vc_controls[2]['page'], 'B_23.jsp')
        self.assertEqual(page.vc_search['keyboard_mode'], 'cKT_PredictNoLF')
        self.assertEqual(page.vc_search['maximum_characters'], 40)
        self.assertEqual(page.vc_back_page, 'W_03.jsp')
        self.assertIn('.fixture', page.vc_styles)
        self.assertNotIn('<script', page.vc_root.render())
        self.assertFalse(page.category_gateway_recovered)

    def test_hover_and_transitive_css_dependencies_are_required(self):
        for missing in ('hover.gif', 'background.gif'):
            shared = NavigationSharedFixture()
            del shared.shared['/oss/oss/common/images/'+missing]
            with self.assertRaisesRegex(ValueError, 'display dependencies'):
                CapturedNavigation(self.root, shared)

    def test_wrong_source_member_and_duplicate_page_are_rejected(self):
        for key in ('source', 'archive_sha1'):
            original = self.manifest[key]
            self.manifest[key] = 'unrelated'
            self.write_manifest()
            with self.assertRaisesRegex(ValueError, 'source'):
                CapturedNavigation(self.root, NavigationSharedFixture())
            self.manifest[key] = original
        row = self.manifest['files'][0]
        original = row['member']
        row['member'] += '&accountId=fixture'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'fingerprint/member/path'):
            CapturedNavigation(self.root, NavigationSharedFixture())
        row['member'] = original.replace('oss-auth.shop.wii.com', 'other.example')
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Missing or ambiguous'):
            CapturedNavigation(self.root, NavigationSharedFixture())
        row['member'] = original
        self.manifest['files'].append(dict(row))
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            CapturedNavigation(self.root, NavigationSharedFixture())

    def test_tampered_bytes_and_blob_path_are_rejected(self):
        row = self.manifest['files'][0]
        path = self.root/row['file']
        original = path.read_bytes()
        path.write_bytes(b'x'*len(original))
        with self.assertRaisesRegex(ValueError, 'fingerprint differs'):
            CapturedNavigation(self.root, NavigationSharedFixture())
        path.write_bytes(original)
        row['file'] = '../outside'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'fingerprint/member/path'):
            CapturedNavigation(self.root, NavigationSharedFixture())

    def test_system_review_keeps_all_codes_and_requires_missing_assets(self):
        shared = NavigationSharedFixture()
        del shared.shared['/oss/oss/ext/attributes/images/platform/WII.gif']
        page = CapturedNavigation(self.root, shared)
        with self.assertRaisesRegex(ValueError, 'display dependencies'):
            page.review_systems()
        systems = page.review_systems(allow_incomplete=True)
        self.assertFalse(systems.ready_for_display)
        self.assertEqual(len(systems.controls), 10)
        self.assertEqual(tuple(c['query']['platform'] for c in systems.controls), SYSTEM_CODES)
        self.assertEqual(systems.back_page, 'B_23.jsp')
        self.assertEqual(systems.navigation_script, self.scroll)
        self.assertEqual(len(systems.missing_dependencies), 1)


if __name__ == '__main__':
    unittest.main()
