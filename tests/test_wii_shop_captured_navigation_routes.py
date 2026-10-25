import json
from pathlib import Path
import unittest

from jwc24.wii_shop_artwork import Tree
from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_captured_navigation import CapturedNavigation
from jwc24.wii_shop_server import Application
from tests.test_wii_shop_artwork import Elements
from tests import test_wii_shop_artwork as artwork_fixture
from tests.test_wii_shop_browse import record


class CapturedNavigationRouteTests(unittest.TestCase):
    def app(self):
        artwork = artwork_fixture.ShopArtworkTests.pack(self)
        root = Path('private/wii_shop/frontend-navigation-v1')
        if not (root/'manifest.private.json').is_file():
            self.skipTest('Private navigation capture unavailable')
        artwork.captured_navigation = CapturedNavigation(root, artwork.captured_scripts)
        return Application(Catalog([record(category_label='Virtual Console')]), artwork=artwork)

    def test_original_vc_menu_does_not_depend_on_modified_template(self):
        app = self.app()
        capture = app.pages.captured_navigation
        before = capture.vc_root.render()
        app.pages.files['/oss/serv/B_01.html'] = b'not a usable modified template'
        status, _, body = app.get('/category/virtual-console')
        self.assertEqual(status, 200)
        tree = Tree(body.decode()).root
        for identifier in ('text00-01','text00-02','text01','text02','text03','text04'):
            source = capture.vc_root.find(identifier)
            if source:
                self.assertEqual(tree.find(identifier).render(), source.render(), identifier)
        self.assertEqual(capture.vc_root.render(), before)
        self.assertEqual(app.get('/category/virtual-console')[2], body)

    def test_category_and_ranked_controls_are_not_repurposed_as_data_filters(self):
        tree = Tree(self.app().get('/category/virtual-console')[2].decode()).root
        for identifier in ('spacer01', 'spacer02', 'spacer03'):
            links = [node for node in tree.find(identifier).walk() if node.tag == 'a']
            self.assertTrue(links, identifier)
            self.assertEqual([node.attrs['href'] for node in links], ['/about'])
        self.assertIsNone(tree.find('text05'))
        self.assertEqual(tree.find('underlinkL').attrs['href'], '/')
        self.assertEqual(tree.find('underlinkL').attrs['onclick'], 'snd.playSE(cSE_Cancel)')

    def test_captured_standalone_search_retains_native_keyboard_shape(self):
        nodes = Elements(self.app().get('/category/virtual-console')[2]).nodes
        self.assertFalse(any(tag == 'form' for tag, _ in nodes))
        inputs = [attrs for tag, attrs in nodes if tag == 'input']
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]['id'], 'Image04s')
        self.assertEqual(inputs[0]['maxlength'], '40')
        self.assertEqual(inputs[0]['data-shop-category'], 'Virtual Console')
        self.assertEqual(inputs[0]['onmousedown'], 'typeSearch(this)')
        self.assertEqual(inputs[0]['onchange'], 'submitCatalogSearch(this)')

    def test_vc_menu_uses_captured_display_resources_and_only_reviewed_scripts(self):
        app = self.app()
        body = app.get('/category/virtual-console')[2]
        scripts = []
        for tag, attrs in Elements(body).nodes:
            path = attrs.get('src') if tag in ('img','input','script') else attrs.get('href') if tag == 'link' else None
            if path:
                self.assertEqual(app.get(path)[0], 200, path)
                if tag != 'script':
                    self.assertTrue(path.startswith('/assets/captured/'), path)
            if tag == 'script':
                scripts.append(path)
            for event, value in attrs.items():
                if event.startswith('on'):
                    self.assertNotIn('https:', value)
                    self.assertNotIn('oss/serv/', value)
        self.assertEqual(scripts[-1], '/assets/shop.js')
        self.assertFalse(any(path.endswith(('/ec.js', '/oss.js', '/title_manager.js')) for path in scripts))

    def test_health_reports_the_exact_navigation_pack(self):
        app = self.app()
        health = json.loads(app.get('/healthz')[2])
        self.assertTrue(health['captured_vc_menu'])
        self.assertEqual(health['captured_navigation_manifest_sha256'], app.pages.captured_navigation.manifest_sha256)


if __name__ == '__main__':
    unittest.main()
