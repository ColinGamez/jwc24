from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
import json

from jwc24.wii_shop_artwork import Artwork, Tree
from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_server import Application
from jwc24.wii_shop_native_assets import NativeAssets, PREFIX, SCRIPTS
from tests.test_wii_shop_browse import record


class Elements(HTMLParser):
    def __init__(self, data):
        super().__init__()
        self.nodes = []
        self.feed(data.decode('utf-8'))

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


class ShopArtworkTests(unittest.TestCase):
    def pack(self):
        root = Path('private/wii_shop/artwork-v2')
        if not (root/'manifest.json').is_file():
            self.skipTest('Private archived artwork pack unavailable')
        native = Path('private/wii_shop/native-assets-v1')
        if not (native/'manifest.json').is_file():
            self.skipTest('Private native script pack unavailable')
        return Artwork(root, native_assets=NativeAssets(native))

    def test_legacy_void_and_nested_elements_keep_their_structure(self):
        root = Tree('<body><div id="a"><img src="x"><br><span>A &amp; B</span></div></body>').root
        self.assertEqual(root.find('a').children[-1].tag, 'span')
        self.assertIn('A &amp; B', root.render())

    def test_manifest_drift_rejected_before_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'image.gif').write_bytes(b'changed')
            (root/'manifest.json').write_text(json.dumps({'source': 'https://wiishopchannel.net',
                'files': {'/image.gif': {'bytes': 7, 'sha256': '0'*64}}}))
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                Artwork(root)

    def test_original_home_layout_artwork_and_local_routes_are_preserved(self):
        pack = self.pack()
        elements = Elements(pack.home(844)).nodes
        images = [attrs.get('src', '') for tag, attrs in elements if tag == 'img']
        for name in ('top_buy_vc_a.png', 'top_buy_wiiware_a.png', 'top_buy_wiichannel_a.png'):
            self.assertTrue(any(path.endswith(name) for path in images))
        scripts = [attrs.get('src') for tag, attrs in elements if tag == 'script']
        self.assertEqual(scripts, [PREFIX+name for name in SCRIPTS]+['/assets/shop.js'])
        labels = [a['data-shop-string'] for _, a in elements if 'data-shop-string' in a]
        self.assertCountEqual(labels, ['title', 'menuBtn'])
        self.assertNotIn('Wiiメニューへ'.encode(), pack.home(844))
        links = [attrs.get('href', '') for tag, attrs in elements if tag == 'a']
        self.assertIn('/category/wiiware', links)
        self.assertIn('/category/virtual-console', links)
        self.assertTrue(all(url.startswith('/') for url in links))

    def test_all_image_and_stylesheet_references_resolve_in_the_cached_pack(self):
        pack = self.pack()
        app = Application(Catalog([record()]), artwork=pack)
        for path in ('/', '/category/wiiware', '/category/virtual-console', '/catalog', '/title/0001000141424344', '/about'):
            status, _, body = app.get(path)
            self.assertEqual(status, 200)
            for tag, attrs in Elements(body).nodes:
                asset = attrs.get('src') if tag in ('img', 'input', 'script') else attrs.get('href') if tag == 'link' else None
                if asset == '/assets/shop.js':
                    self.assertEqual(app.get(asset)[0], 200)
                    continue
                if asset:
                    with self.subTest(page=path, asset=asset):
                        self.assertEqual(pack.asset(asset)[0], 200)

    def test_archived_rows_bind_filtered_catalog_and_escape_metadata(self):
        pack = self.pack()
        rows = [record(f'00010001{i:08X}', f'Game {i:02}') for i in range(14)]
        rows.append(record('00010001000000FF', '<script>unsafe()</script>'))
        app = Application(Catalog(rows), artwork=pack)
        first = Elements(app.get('/catalog')[2]).nodes
        links = [attrs['href'] for tag, attrs in first if tag == 'a' and attrs.get('href', '').startswith('/title/')]
        self.assertEqual(len(links), 10)
        self.assertEqual(len(set(links)), 10)
        body = app.get('/catalog?q=%3Cscript%3E')[2]
        self.assertIn(b'&lt;script&gt;unsafe()', body)
        self.assertNotIn(b'<script>unsafe()', body)

    def test_category_keyboard_search_uses_local_form_and_native_adapter(self):
        pack = self.pack()
        for category in ('WiiWare', 'Virtual Console'):
            nodes = Elements(pack.category(category)).nodes
            forms = [a for t,a in nodes if t == 'form']
            self.assertEqual(forms, [{'action': '/catalog', 'method': 'get', 'style': 'margin:0'}])
            entries = [a for t,a in nodes if t == 'input' and a.get('name') == 'q']
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['onmousedown'], 'typeSearch()')
            self.assertEqual(entries[0]['onchange'], 'submitCatalogSearch(this)')
            self.assertEqual(entries[0]['maxlength'], '40')
            self.assertTrue(any(t == 'input' and a.get('name') == 'category' and a.get('value') == category for t,a in nodes))

    def test_catalog_back_returns_to_its_category_menu(self):
        app = Application(Catalog([record()]), artwork=self.pack())
        nodes = Elements(app.get('/catalog?category=WiiWare')[2]).nodes
        self.assertTrue(any(a.get('id') == 'underlinkL' and a.get('href') == '/category/wiiware' for _,a in nodes))
