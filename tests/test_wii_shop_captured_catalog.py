import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from jwc24.wii_shop_artwork import Artwork, Tree
from jwc24.wii_shop_captured_catalog import CapturedCatalog, LAYOUT_SHA256, NAVIGATION_URL, panel_identity
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE, CapturedScripts
from jwc24.wii_shop_native_assets import NativeAssets
from jwc24.wii_shop_server import Application, catalog_from_file
from tests.test_wii_shop_artwork import Elements
from tests.test_wii_shop_browse import record
from jwc24.wii_shop_browse import Catalog


class CapturedCatalogTests(unittest.TestCase):
    def pack(self):
        root = Path('private/wii_shop')
        paths = [root/'frontend-japan-catalog-v2/manifest.private.json',root/'artwork-v2/manifest.json',
                 root/'frontend-capture-v1/manifest.private.json',root/'title-metadata-v2/metadata.json',
                 root/'native-assets-v1/manifest.json']
        if not all(path.is_file() for path in paths):
            self.skipTest('Private captured catalog fixtures unavailable')
        catalog,digest = catalog_from_file(root/'mariocube-catalog-ids.json',root/'title-metadata-v2/metadata.json')
        capture = CapturedCatalog(root/'frontend-japan-catalog-v2',{row['title_id'] for row in catalog.items})
        artwork = Artwork(root/'artwork-v2',native_assets=NativeAssets(root/'native-assets-v1'),
                          captured_scripts=CapturedScripts(root/'frontend-capture-v1'),captured_catalog=capture)
        return catalog,capture,artwork

    def test_identity_requires_one_matching_original_link_and_image(self):
        identifier = '0001000141424344'
        source = ('<div><a href="B_05.jsp?titleId='+identifier+'">'
                  '<img src="/oss/ccs/'+identifier+'/FFFD0000"></a></div>')
        self.assertEqual(panel_identity(Tree(source).root),identifier)
        wrong = source.replace('titleId='+identifier,'titleId=0001000141424345')
        self.assertIsNone(panel_identity(Tree(wrong).root))
        duplicate = source.replace('</div>','<img src="/oss/ccs/'+identifier+'/FFFD0001"></div>')
        self.assertIsNone(panel_identity(Tree(duplicate).root))

    def test_capture_layout_and_css_work_without_the_modified_catalog_template(self):
        catalog,capture,artwork = self.pack()
        artwork.files['/oss/serv/B_04.html'] = b'not a template'
        app = Application(catalog,artwork=artwork)
        nodes = Elements(app.get('/catalog')[2]).nodes
        self.assertEqual([row['href'] for tag,row in nodes if tag=='link'],
            ['/assets/captured/oss/oss/common/css/oss.css','/assets/captured/oss/oss/common/css/error.css'])
        self.assertIn(NAVIGATION_URL,[row.get('src') for tag,row in nodes if tag=='script'])
        self.assertEqual(sum(row.get('id','').startswith('panel0') for _,row in nodes),10)
        body = next(row for tag,row in nodes if tag=='body')
        self.assertEqual(body['onkeypress'],'kdown();')
        self.assertIn("getElementById('catalogFrame').focus()",body['onload'])
        for tag,row in nodes:
            asset = row.get('src') if tag in ('img','input','script') else row.get('href') if tag=='link' else None
            if asset:
                self.assertEqual(app.get(asset)[0],200,asset)

    def test_original_title_lines_are_copied_without_gift_update_or_account_claims(self):
        catalog,capture,artwork = self.pack()
        item = next(row for row in catalog.items if row['title_id'] in capture.panels)
        original = capture.panels[item['title_id']]
        lines = lambda panel: [''.join(child for child in node.children if isinstance(child,str))
            for node in panel.walk() if node.attrs.get('id','').startswith(('title1_','title2_'))]
        before = original.render()
        card = capture.card(item,4)
        self.assertEqual(lines(card),lines(original))
        self.assertEqual(original.render(),before)
        self.assertIn('top:472px',card.attrs['style'])
        self.assertEqual(card.attrs['id'],'panel05')
        for prefix in ('UPDATE','giftTitle','storedGiftTitle','scaTitle'):
            self.assertIsNone(card.find(prefix+'5'))
        self.assertEqual(card.find('regularTitle5').attrs['style'],'')

    def test_paging_wraps_and_preserves_filters_through_details_and_back(self):
        catalog,_,artwork = self.pack()
        app = Application(catalog,artwork=artwork)
        first = Elements(app.get('/catalog?platform=FC%2FNES')[2]).nodes
        count = catalog.query(platform='FC/NES')['total']
        last = ((count-1)//10)*10
        root = Tree(app.get('/catalog?platform=FC%2FNES')[2].decode()).root
        previous = next(node for node in root.find('arrowL').walk() if node.tag=='a').attrs['href']
        self.assertEqual(parse_qs(urlsplit(previous).query),{'platform':['FC/NES'],'offset':[str(last)],'demos':['all']})
        forward = Tree(app.get(previous)[2].decode()).root.find('arrowR')
        next_link = next(node for node in forward.walk() if node.tag=='a').attrs['href']
        self.assertEqual(parse_qs(urlsplit(next_link).query)['offset'],['0'])
        detail = next(row['href'] for tag,row in first if tag=='a' and row.get('href','').startswith('/title/'))
        detail_root = Tree(app.get(detail)[2].decode()).root
        self.assertEqual(parse_qs(urlsplit(detail_root.find('underlinkL').attrs['href']).query)['platform'],['FC/NES'])

    def test_unmatched_titles_are_escaped_and_empty_results_keep_the_existing_experiment(self):
        _,_,artwork = self.pack()
        app = Application(Catalog([record(name='<script>unsafe()</script>')]),artwork=artwork)
        body = app.get('/catalog')[2]
        self.assertIn(b'&lt;script&gt;unsafe()',body)
        self.assertNotIn(b'<script>unsafe()',body)
        empty = app.get('/catalog?q=missing')[2]
        self.assertIn(b'id="notFound"',empty)
        self.assertNotIn(NAVIGATION_URL.encode(),empty)
        self.assertEqual(app.get('/about')[0],200)

    def test_self_consistent_modified_layout_is_rejected(self):
        _,capture,_ = self.pack()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'blobs').mkdir()
            data = capture.layout_html+b'changed'
            digest = hashlib.sha256(data).hexdigest()
            (root/'blobs'/digest).write_bytes(data)
            document = dict(source=SOURCE,archive_sha1=ARCHIVE_SHA1,files=[dict(
                member='oss-auth.shop.wii.com/oss/serv/B_04.jsp?country=JP',
                sha256=digest,bytes=len(data),file='blobs/'+digest)])
            (root/'manifest.private.json').write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,'reviewed catalog layout'):
                CapturedCatalog(root,set())

    @unittest.skipUnless(shutil.which('node'),'Script behavior check requires Node')
    def test_original_navigation_handler_scrolls_and_clicks_page_controls(self):
        _,capture,_ = self.pack()
        self.assertEqual(hashlib.sha256(capture.layout_html).hexdigest(),LAYOUT_SHA256)
        harness = r'''
const vm=require('vm'),assert=require('assert');
const frame={scrollTop:50};let left=0,right=0;
const nodes={catalogFrame:frame,arrowLImg:{click(){left++;}},arrowRImg:{click(){right++;}}};
const context={event:{keyCode:0},document:{getElementById:id=>nodes[id]||null}};
vm.createContext(context);vm.runInContext(process.argv[1],context);
for(const key of [175,38]){context.event.keyCode=key;context.kdown();}
assert.strictEqual(frame.scrollTop,-10);
for(const key of [176,40]){context.event.keyCode=key;context.kdown();}
assert.strictEqual(frame.scrollTop,50);
context.event.keyCode=178;context.kdown();assert.strictEqual(left,1);
context.event.keyCode=177;context.kdown();assert.strictEqual(right,1);
context.event.keyCode=999;context.kdown();assert.strictEqual(frame.scrollTop,50);
delete nodes.catalogFrame;context.kdown();
'''
        result = subprocess.run([shutil.which('node'),'-e',harness,capture.navigation_script.decode()],
                                capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
