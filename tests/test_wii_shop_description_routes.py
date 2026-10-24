import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest
from copy import deepcopy
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit

from jwc24.wii_shop_artwork import Artwork,Tree,Node
from jwc24.wii_shop_captured_scripts import CapturedScripts
from jwc24.wii_shop_captured_titles import CapturedTitlePages
from jwc24.wii_shop_descriptions import Descriptions,SCROLL_SCRIPT_URL,SCROLL_SHA256
from jwc24.wii_shop_native_assets import NativeAssets
from jwc24.wii_shop_server import Application,catalog_from_file
from tests.test_wii_shop_artwork import Elements


@unittest.skipUnless(importlib.util.find_spec('PIL'),'Screenshot checks require Pillow')
class DescriptionRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path('private/wii_shop')
        if not (root/'descriptions-v2/manifest.private.json').is_file():
            raise unittest.SkipTest('Private description capture unavailable')
        capture=CapturedScripts(root/'frontend-capture-v1')
        cls.catalog,digest=catalog_from_file(root/'mariocube-catalog-ids.json',root/'title-metadata-v2/metadata.json',capture.manifest_sha256)
        ids={row['title_id'] for row in cls.catalog.items}
        cls.descriptions=Descriptions(root/'descriptions-v2',digest,ids,shared_paths=capture.shared)
        titles=CapturedTitlePages(capture,cls.catalog.title_metadata,root/'frontend-title-support-v1',ids,root/'title-pages-v2/index.json')
        cls.artwork=Artwork(root/'artwork-v2',root/'title-artwork-v4',digest,NativeAssets(root/'native-assets-v1'),capture,
                            captured_titles=titles,descriptions=cls.descriptions)
        cls.app=Application(cls.catalog,digest,cls.artwork)
        cls.identifier=next(identifier for identifier in cls.descriptions.rows if identifier in titles.detail_rows)

    def test_original_more_details_button_and_return_preserve_catalog_context(self):
        query='offset=30&demos=all'
        detail=Tree(self.app.get('/title/'+self.identifier+'?'+query)[2].decode()).root
        self.assertTrue(detail.find('underButtonR').attrs['style'].endswith('display:block'))
        link=detail.find('underlinkR').attrs['href']
        self.assertEqual(urlsplit(link).path,'/description/'+self.identifier)
        self.assertIn('MM_swapImage',detail.find('underspacerR').attrs['onmouseover'])
        status,_,body=self.app.get(link)
        self.assertEqual(status,200)
        tree=Tree(body.decode()).root
        back=tree.find('underlinkL')
        self.assertEqual(urlsplit(back.attrs['href']).path,'/title/'+self.identifier)
        self.assertEqual(parse_qs(urlsplit(back.attrs['href']).query),{'offset':['30'],'demos':['all']})
        self.assertEqual(back.attrs['onclick'],'snd.playSE(cSE_Cancel)')

    def test_original_description_markup_and_native_scroll_wiring_are_retained(self):
        source,_,_=self.descriptions.page(self.identifier)
        status,_,body=self.app.get('/description/'+self.identifier)
        self.assertEqual(status,200)
        tree=Tree(body.decode()).root
        self.assertEqual(tree.find('text').render(),source.find('text').render())
        self.assertEqual(tree.find('TitleName1stline').render(),source.find('TitleName1stline').render())
        self.assertEqual(tree.attrs['onkeypress'],"kdown('goodsfree');")
        self.assertIn("getElementById('goodsfree').focus()",tree.attrs['onload'])
        self.assertIn(SCROLL_SCRIPT_URL.encode(),body)
        for tag,attrs in Elements(body).nodes:
            path=attrs.get('src') if tag in ('img','input','script') else attrs.get('href') if tag=='link' else None
            if path:self.assertEqual(self.app.get(path)[0],200,path)

    def test_only_original_screenshot_paths_are_exposed(self):
        row=self.descriptions.rows[self.identifier]
        for path in row['screenshots']:
            status,mime,data=self.app.get(path)
            self.assertEqual(status,200)
            self.assertTrue(mime.startswith('image/'))
            self.assertEqual(hashlib.sha256(data).hexdigest(),self.descriptions.images[path]['sha256'])
        for path in ('/oss/ccs/'+self.identifier+'/tmd','/oss/ccs/'+self.identifier+'/00000001','/oss/ccs/../keys.bin'):
            self.assertEqual(self.app.get(path)[0],404,path)
        missing=next(row['title_id'] for row in self.catalog.items if row['title_id'] not in self.descriptions.rows)
        self.assertEqual(self.app.get('/description/'+missing)[0],404)

    def test_vetted_content_links_and_css_keep_their_original_meaning_and_asset_pack(self):
        page=self.descriptions.page(self.identifier)
        root,styles,sheets=page
        href='https://publisher.invalid/B_05.jsp?titleId=0001000141424344'
        content=root.find('text')
        content.children.append(Node('a',{'href':href},['Synthetic publisher link']))
        asset='/oss/oss/common/images/banner/top_a.gif'
        content.attrs['style']="background-image:url('"+asset+"')"
        page=(root,styles+'\n.synthetic{background:url('+asset+')}',sheets)
        original=root.render()
        with patch.object(self.descriptions,'page',side_effect=lambda identifier:deepcopy(page)):
            body=self.app.get('/description/'+self.identifier)[2]
        tree=Tree(body.decode()).root
        link=next(node for node in tree.find('text').walk() if node.tag=='a')
        self.assertEqual(link.attrs['href'],href)
        self.assertIn("url('/assets/captured"+asset+"')",tree.find('text').attrs['style'])
        self.assertIn(('url(/assets/captured'+asset+')').encode(),body)
        self.assertEqual(root.render(),original)

    @unittest.skipUnless(shutil.which('node'),'Original key-handler check requires Node')
    def test_pinned_original_key_handler_scrolls_the_description_frame(self):
        status,_,data=self.app.get(SCROLL_SCRIPT_URL)
        self.assertEqual(status,200)
        self.assertEqual(hashlib.sha256(data).hexdigest(),SCROLL_SHA256)
        harness=r'''
const vm=require('vm'),assert=require('assert');
const frame={scrollTop:50};
const context={event:{keyCode:0},document:{getElementById:id=>{assert.strictEqual(id,'goodsfree');return frame;}}};
vm.createContext(context);vm.runInContext(process.argv[1],context);
for(const key of [175,38]){context.event.keyCode=key;context.kdown('goodsfree');}
assert.strictEqual(frame.scrollTop,-10);
for(const key of [176,40]){context.event.keyCode=key;context.kdown('goodsfree');}
assert.strictEqual(frame.scrollTop,50);
context.event.keyCode=999;context.kdown('goodsfree');assert.strictEqual(frame.scrollTop,50);
'''
        result=subprocess.run([shutil.which('node'),'-e',harness,data.decode()],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
