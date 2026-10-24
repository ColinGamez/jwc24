from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
import json
from urllib.parse import urljoin, urlsplit

from jwc24.wii_shop_artwork import Artwork, Tree
from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_server import Application
from jwc24.wii_shop_native_assets import NativeAssets, PREFIX, SCRIPTS
from jwc24.wii_shop_captured_scripts import CapturedScripts, KEYBOARD_URL
from jwc24.wii_shop_title_metadata import TitleMetadata
from tests import test_wii_shop_title_metadata as metadata_fixture
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
        capture = Path('private/wii_shop/frontend-capture-v1')
        if not (capture/'manifest.private.json').is_file():
            self.skipTest('Private storefront capture unavailable')
        return Artwork(root, native_assets=NativeAssets(native), captured_scripts=CapturedScripts(capture))

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
        self.assertEqual(scripts, [PREFIX+name for name in SCRIPTS]+[KEYBOARD_URL, '/assets/shop.js'])
        labels = [a['data-shop-string'] for _, a in elements if 'data-shop-string' in a]
        self.assertCountEqual(labels, ['title', 'menuBtn'])
        self.assertNotIn('Wiiメニューへ'.encode(), pack.home(844))
        self.assertIn('設定・その他'.encode(), pack.home(844))
        self.assertNotIn('設定・特典'.encode(), pack.home(844))
        self.assertIn('Wiiウェア'.encode(), pack.home(844))
        self.assertTrue(any(a.get('id') == 'currentBalance' for _, a in elements))
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

    def test_home_uses_the_reviewed_capture_and_its_styles_instead_of_edited_template(self):
        pack = self.pack()
        pack.files['/oss/serv/W_03.html'] = b'not a usable home template'
        nodes = Elements(pack.home(844)).nodes
        stylesheets = [a['href'] for t, a in nodes if t == 'link']
        self.assertEqual(stylesheets, ['/assets/captured/oss/oss/common/css/oss.css'])
        css_url = stylesheets[0]
        status, mime, data = pack.asset(css_url)
        self.assertEqual(status, 200)
        css = data.decode('cp932' if 'Shift_JIS' in mime else 'utf-8-sig')
        for reference in re.findall(r'url\([\"\x27]?([^\"\x27)]+)', css):
            resolved = urlsplit(urljoin('https://127.0.0.1'+css_url, reference))
            self.assertEqual(resolved.hostname, '127.0.0.1')
            path = resolved.path
            with self.subTest(resource=path):
                self.assertEqual(pack.asset(path)[0], 200)
        self.assertEqual(pack.asset('/assets/captured/oss/oss/common/js/oss.js')[0], 404)

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

    def test_category_keyboard_search_preserves_original_input_and_local_navigation(self):
        pack = self.pack()
        for category in ('WiiWare', 'Virtual Console'):
            nodes = Elements(pack.category(category)).nodes
            forms = [a for t,a in nodes if t == 'form']
            self.assertEqual(forms, [])
            entries = [a for t,a in nodes if t == 'input' and a.get('data-shop-category') == category]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['onmousedown'], 'typeSearch(this)')
            self.assertEqual(entries[0]['onchange'], 'submitCatalogSearch(this)')
            self.assertEqual(entries[0]['maxlength'], '40')
            self.assertEqual(entries[0]['name'], 'Image04s')

    def test_catalog_back_returns_to_its_category_menu(self):
        app = Application(Catalog([record()]), artwork=self.pack())
        nodes = Elements(app.get('/catalog?category=WiiWare')[2]).nodes
        self.assertTrue(any(a.get('id') == 'underlinkL' and a.get('href') == '/category/wiiware' for _,a in nodes))

    def test_historical_title_publisher_and_points_render_without_relabeling_original_release_date(self):
        pack = self.pack()
        fixture = metadata_fixture.HistoricalTitleMetadataTests()
        with tempfile.TemporaryDirectory() as directory:
            metadata = TitleMetadata(fixture.metadata(Path(directory)), 'a'*64)
            app = Application(Catalog([record(name='Romanized file name')], title_metadata=metadata), artwork=pack)
            for path in ('/catalog?q=%E3%83%86%E3%82%B9%E3%83%88', '/title/'+fixture.identifier):
                body = app.get(path)[2]
                with self.subTest(page=path):
                    self.assertIn('テスト &amp; 名前'.encode(), body)
                    self.assertIn(b'Example &amp; Co', body)
                    self.assertIn(b'1,000', body)
                    self.assertNotIn(b'Released 12/13/1984', body)
