import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qs,urlsplit

from jwc24.wii_shop_artwork import Artwork,Tree
from jwc24.wii_shop_captured_scripts import CapturedScripts
from jwc24.wii_shop_captured_titles import CapturedTitlePages,CONTROLLER_SCRIPT_URL,controller_identity,read_page
from jwc24.wii_shop_native_assets import NativeAssets
from jwc24.wii_shop_server import Application,catalog_from_file
from tests.test_wii_shop_artwork import Elements


class ControllerIdentityTests(unittest.TestCase):
    def test_generated_internal_url_must_match_the_requested_title(self):
        identifier='0001000141424344'
        page=('<script>var url="B_09.jsp?titleId='+identifier+'&SD=";</script>'
              '<body><div id="TitleName1stline">Original title</div></body>').encode()
        self.assertIsNotNone(controller_identity(page,identifier).find('TitleName1stline'))
        with self.assertRaisesRegex(ValueError,'identity'):
            controller_identity(page,'0001000141424345')
        with self.assertRaisesRegex(ValueError,'identity'):
            controller_identity(page+b'<script>var x="?titleId=0001000141424345&"</script>',identifier)
        with self.assertRaisesRegex(ValueError,'title missing'):
            controller_identity(page.replace(b'Original title',b''),identifier)

    def test_changed_captured_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'blobs').mkdir()
            digest=hashlib.sha256(b'original').hexdigest()
            (root/'blobs'/digest).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'fingerprint'):
                read_page(root,dict(file='blobs/'+digest,sha256=digest,bytes=8))


class CapturedTitlePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path('private/wii_shop')
        if not (root/'title-pages-v2/index.json').is_file():
            raise unittest.SkipTest('Private title-page index unavailable')
        cls.root=root
        capture=CapturedScripts(root/'frontend-capture-v1')
        cls.catalog,cls.digest=catalog_from_file(root/'mariocube-catalog-ids.json',root/'title-metadata-v2/metadata.json',capture.manifest_sha256)
        cls.capture=capture
        cls.title_ids={row['title_id'] for row in cls.catalog.items}
        cls.pages=CapturedTitlePages(capture,cls.catalog.title_metadata,root/'frontend-title-support-v1',cls.title_ids,root/'title-pages-v2/index.json')
        cls.artwork=Artwork(root/'artwork-v2',root/'title-artwork-v4',cls.digest,NativeAssets(root/'native-assets-v1'),capture,captured_titles=cls.pages)
        cls.app=Application(cls.catalog,cls.digest,cls.artwork)
        cls.identifier=next(iter(cls.pages.detail_rows))

    def test_captured_information_fields_preserve_source_structure_and_do_not_claim_commerce_state(self):
        source,_=self.pages.page(self.identifier)
        expected=source.find('TitleName1').render()
        status,_,body=self.app.get('/title/'+self.identifier)
        self.assertEqual(status,200)
        tree=Tree(body.decode()).root
        self.assertEqual(tree.find('TitleName1').render(),expected)
        self.assertEqual(tree.find('heading').children,['ソフトの購入'])
        for identifier in ('DisplayCategory','date','Publisher','Players','Platform','Rating'):
            self.assertIsNotNone(tree.find(identifier))
        for identifier in ('buyButton','giftButton','sdbuttons','downloadedMsg','notAvailableMsg','pointError'):
            self.assertIsNone(tree.find(identifier))
        self.assertIn(('/title-artwork/'+self.identifier+'/detail').encode(),body)
        self.assertEqual([a['href'] for t,a in Elements(body).nodes if t=='link'],
            ['/assets/captured/oss/oss/common/css/oss.css','/assets/captured/oss/oss/common/css/error.css','/assets/captured/oss/oss/common/css/B_05.css'])

    def test_controller_round_trip_preserves_list_context_and_uses_captured_assets(self):
        query='offset=30&demos=all'
        body=self.app.get('/title/'+self.identifier+'?'+query)[2]
        anchor=Tree(body.decode()).root.find('ControlAnchor').attrs['href']
        self.assertEqual(urlsplit(anchor).path,'/controller/'+self.identifier)
        status,_,controller=self.app.get(anchor)
        self.assertEqual(status,200)
        tree=Tree(controller.decode()).root
        self.assertEqual(parse_qs(urlsplit(tree.find('underlinkL').attrs['href']).query),{'offset':['30'],'demos':['all']})
        self.assertTrue(tree.find('underlinkL').attrs['href'].startswith('/title/'+self.identifier))
        self.assertIn('display:none',tree.find('underButtonR').attrs['style'])
        self.assertIn(CONTROLLER_SCRIPT_URL.encode(),controller)
        self.assertNotIn(b'ec.setSessionValue',controller)
        for tag,attrs in Elements(controller).nodes:
            path=attrs.get('src') if tag in ('img','input','script') else attrs.get('href') if tag=='link' else None
            if path:self.assertEqual(self.app.get(path)[0],200,path)

    def test_missing_descriptor_keeps_the_earlier_view_without_substituting_a_rating(self):
        identifier=next(iter(self.pages.excluded_details))
        self.assertIsNone(self.pages.page(identifier))
        status,_,body=self.app.get('/title/'+identifier)
        self.assertEqual(status,200)
        self.assertNotIn(b'Pic_Rating/GRB/cd05.gif',body)
        self.assertNotIn(b'Pic_Rating/PEGI/cd05.gif',body)

    def test_cached_source_trees_are_copied_before_rendering(self):
        first,_=self.pages.page(self.identifier)
        expected=first.find('TitleName1').render()
        first.text('TitleName1','changed copy')
        second,_=self.pages.page(self.identifier)
        self.assertEqual(second.find('TitleName1').render(),expected)

    def test_stale_index_cannot_be_attached_to_different_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            original=json.loads((self.root/'title-pages-v2/index.json').read_text(encoding='utf-8'))
            for field,value in [('metadata_sha256','0'*64),('validation_revision',1)]:
                document=dict(original,**{field:value})
                path=Path(directory)/'index.json';path.write_text(json.dumps(document))
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'source binding'):
                    CapturedTitlePages(self.capture,self.catalog.title_metadata,self.root/'frontend-title-support-v1',self.title_ids,path)

    @unittest.skipUnless(shutil.which('node'),'Compatibility handler check requires Node')
    def test_original_vwii_condition_hides_gamecube_art_only_in_compatible_mode(self):
        source=self.pages.controller_mode_script.decode()
        harness=r'''
const vm=require('vm'),assert=require('assert');
for(const compatible of [false,true]){
const image={style:{display:'inline-block'}};
const context={shop:{isCompatibleMode:compatible},document:{getElementById:()=>image}};
vm.createContext(context);vm.runInContext(process.argv[1],context);context.applyControllerMode();
assert.strictEqual(image.style.display,compatible?'none':'inline-block');
context.document.getElementById=()=>null;context.applyControllerMode();
}
'''
        result=subprocess.run([shutil.which('node'),'-e',harness,source],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
