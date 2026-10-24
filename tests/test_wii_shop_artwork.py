from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
import json

from jwc24.wii_shop_artwork import Artwork, Tree
from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_server import Application
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
        root = Path('private/wii_shop/artwork-v1')
        if not (root/'manifest.json').is_file():
            self.skipTest('Private archived artwork pack unavailable')
        return Artwork(root)

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
        self.assertEqual(scripts, ['/assets/shop.js'])
        links = [attrs.get('href', '') for tag, attrs in elements if tag == 'a']
        self.assertIn('/catalog?category=WiiWare', links)
        self.assertIn('/catalog?category=Virtual+Console', links)
        self.assertTrue(all(url.startswith('/') for url in links))

    def test_all_image_and_stylesheet_references_resolve_in_the_cached_pack(self):
        pack = self.pack()
        app = Application(Catalog([record()]), artwork=pack)
        for path in ('/', '/catalog', '/title/0001000141424344', '/about'):
            status, _, body = app.get(path)
            self.assertEqual(status, 200)
            for tag, attrs in Elements(body).nodes:
                asset = attrs.get('src') if tag in ('img', 'input') else attrs.get('href') if tag == 'link' else None
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
