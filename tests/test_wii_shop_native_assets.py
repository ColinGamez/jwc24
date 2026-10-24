import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from jwc24.wii_shop_native import JS
from jwc24.wii_shop_native_assets import NativeAssets, RESOURCE_SHA256, SCRIPTS, PREFIX
from jwc24.wii_shop_captured_scripts import CapturedScripts


class NativeShopAssetsTests(unittest.TestCase):
    def pack_root(self):
        root = Path('private/wii_shop/native-assets-v1')
        if not (root/'manifest.json').is_file():
            self.skipTest('Private installed Shop scripts unavailable')
        return root

    def test_exact_installed_scripts_are_served_and_unknown_paths_are_rejected(self):
        pack = NativeAssets(self.pack_root())
        for name, digest in SCRIPTS.items():
            status, mime, data = pack.asset(PREFIX+name)
            self.assertEqual((status, mime), (200, 'text/javascript'))
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
        self.assertEqual(pack.asset('/assets/native/../keys.bin')[0], 404)

    def test_self_consistent_substitute_cannot_pass_pinned_original_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b'substitute script'
            metadata = {'resource_sha256': RESOURCE_SHA256, 'files': {}}
            for name in SCRIPTS:
                (root/name).write_bytes(data)
                metadata['files'][name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            (root/'manifest.json').write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                NativeAssets(root)

    @unittest.skipUnless(shutil.which('node'), 'JavaScript behavior test requires Node')
    def test_original_initializers_supply_localized_strings_without_duplicate_objects(self):
        pack = NativeAssets(self.pack_root())
        capture = Path('private/wii_shop/frontend-capture-v1')
        if not (capture/'manifest.private.json').is_file():
            self.skipTest('Private captured keyboard script unavailable')
        keyboard = CapturedScripts(capture)
        # All browser/native dependencies are synthetic; no account or network call.
        harness = r'''
const vm=require('vm'),assert=require('assert');
let shopCount=0,soundCount=0,keyboardCount=0,music=0,returned=0,keyboardCall=null;
function span(key){return {getAttribute:()=>key,firstChild:null,appendChild(n){this.text=n.text;}};}
const labels=[span('title'),span('menuBtn')];
const picture={src:'original-a.gif'};
const context={wiiShop:function(){shopCount++;return {title:'native <title>',menuBtn:'native & menu',
connecting:'connecting',setWallpaper(){},enableHRP(){},endWaiting(){},returnToMenu(){returned++;}};},
wiiSound:function(){soundCount++;return {playBGM(){music++;},playSE(){}};},
wiiKeyboard:function(){keyboardCount++;return {call(...args){keyboardCall=args;}};},Image:function(){},window:{innerWidth:608,innerHeight:456,location:{href:'unchanged'}},
document:{getElementsByTagName:()=>labels,createTextNode:text=>({text}),documentElement:{},body:{},
forms:[],getElementById:()=>picture}};
vm.createContext(context);
const scripts=JSON.parse(process.argv[1]);
scripts.forEach(source=>vm.runInContext(source,context));
context.initShop();
assert.strictEqual(shopCount,1);assert.strictEqual(soundCount,1);assert.strictEqual(music,1);
const input={value:'',blurCount:0,blur(){this.blurCount++;},getAttribute(name){assert.strictEqual(name,'data-shop-category');return 'WiiWare';}};
assert.strictEqual(keyboardCount,1);context.typeSearch(input);assert.deepStrictEqual(keyboardCall,[10,5,false]);
assert.strictEqual(input.blurCount,1);
input.value='\u30bc\u30eb\u30c0 & +?#';context.submitCatalogSearch(input);
assert.strictEqual(input.value,'');assert.strictEqual(input.blurCount,2);
assert.strictEqual(context.window.location.href,'/catalog?category=WiiWare&q='+encodeURIComponent('\u30bc\u30eb\u30c0 & +?#'));
context.window.location.href='unchanged';context.submitCatalogSearch(input);
assert.strictEqual(context.window.location.href,'unchanged');assert.strictEqual(input.blurCount,3);
assert.strictEqual(labels[0].text,'native <title>');assert.strictEqual(labels[1].text,'native & menu');
assert.strictEqual(context.document.title,'native <title>');
assert.ok(context.window.readyImage.src.endsWith('bridge=1&music=1&keyboard=1'));
assert.strictEqual(context.leaveShop(),false);assert.strictEqual(returned,1);
context.MM_swapImage('picture','','original-b.gif',1);assert.strictEqual(picture.src,'original-b.gif');
context.MM_swapImgRestore();assert.strictEqual(picture.src,'original-a.gif');
'''
        scripts = [pack.files[PREFIX+name].decode('utf-8-sig') for name in SCRIPTS]
        scripts += [keyboard.keyboard.decode('cp932'), JS.decode('ascii')]
        result = subprocess.run([shutil.which('node'), '-e', harness, json.dumps(scripts)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
