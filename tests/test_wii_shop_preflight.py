"""Offline preview checks use synthetic pages, never proprietary fixtures."""
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jwc24.wii_shop_preflight import PreviewPacks, PreviewPreflightError, preflight_preview
from tools.preflight_wii_shop import main


class SyntheticPreview:
    def __init__(self):
        ids = ['0001000141424344', '0001000145464748']
        self.catalog = SimpleNamespace(items=[{'title_id': i} for i in ids])
        self.page_size = 1
        self.pages = SimpleNamespace(captured_titles=SimpleNamespace(
            detail_rows={ids[0]: {}}, controller_rows={ids[0]: {}}),
            descriptions=SimpleNamespace(rows={ids[1]: {}}))
        self.visited = []
        self.overrides = {}

    def get(self, target):
        self.visited.append(target)
        if target in self.overrides:
            value = self.overrides[target]
            if isinstance(value, Exception):
                raise value
            return value
        if target == '/css/main.css':
            return 200, 'text/css', b'div {background:url(../image.gif)} span {background:url(main.css)}'
        if target == '/image.gif':
            return 200, 'image/gif', b'synthetic-image'
        if target == '/script.js':
            return 200, 'text/javascript', b'/* synthetic */'
        return 200, 'text/html; charset=utf-8', (b'<html><head><link rel="stylesheet" href="/css/main.css">'
            b'<script src="/script.js"></script></head><body style="background:url(/image.gif)">'
            b'<img src="/image.gif"><a href="https://external.invalid/private-selector">more</a></body></html>')


class ShopPreflightTests(unittest.TestCase):
    def test_every_retained_title_support_and_catalog_page_is_checked_without_network(self):
        app = SyntheticPreview()
        progress = []
        with patch('socket.socket', side_effect=AssertionError('No sockets in offline preflight')):
            result = preflight_preview(app, progress=lambda checked, total: progress.append((checked, total)))
        self.assertEqual(progress, [(0, 11), (11, 11)])
        self.assertTrue(result['offline_preview_passed'])
        self.assertEqual(result['html_routes_checked'], 11)
        self.assertEqual(result['display_dependencies_checked'], 3)
        self.assertEqual(result['missing_captured_detail_titles'], 1)
        self.assertEqual(result['missing_captured_controller_titles'], 1)
        self.assertEqual(result['missing_captured_description_titles'], 1)
        self.assertIn('/catalog?offset=1', app.visited)
        self.assertIn('/title/0001000145464748', app.visited)
        self.assertIn('/controller/0001000141424344', app.visited)
        self.assertIn('/description/0001000145464748', app.visited)
        self.assertEqual(app.visited.count('/image.gif'), 1)
        self.assertEqual(app.visited.count('/css/main.css'), 1)
        self.assertFalse(result['http_tls_checked'])
        self.assertFalse(result['native_rendering_checked'])
        self.assertFalse(result['commerce_supported'])
        self.assertFalse(result['complete_original_japanese_experience'])
        self.assertNotIn('private-selector', json.dumps(result))

    def test_missing_resources_and_failed_pages_are_counted_without_replacements(self):
        app = SyntheticPreview()
        app.overrides['/image.gif'] = (404, 'text/plain', b'missing')
        app.overrides['/title/0001000141424344'] = ValueError('private-content')
        result = preflight_preview(app)
        self.assertFalse(result['offline_preview_passed'])
        self.assertEqual(result['failures']['display_dependencies'], 1)
        self.assertEqual(result['failures']['html_routes'], 1)
        self.assertIn('/description/0001000145464748', app.visited)
        self.assertNotIn('private-content', json.dumps(result))
        self.assertEqual(app.visited.count('/image.gif'), 1)

    def test_external_display_dependencies_are_reported_without_being_requested(self):
        app = SyntheticPreview()
        app.overrides['/css/main.css'] = (200, 'text/css', b'@font-face {src:url(https://external.invalid/font)}')
        result = preflight_preview(app)
        self.assertFalse(result['offline_preview_passed'])
        self.assertEqual(result['failures']['external_display_dependencies'], 1)
        self.assertTrue(all(not target.startswith('http') for target in app.visited))

    def test_bad_catalog_and_bounded_css_chains_are_rejected(self):
        app = SyntheticPreview()
        app.catalog.items.append(app.catalog.items[0])
        with self.assertRaises(PreviewPreflightError):
            preflight_preview(app)
        app = SyntheticPreview()
        for i in range(34):
            app.overrides['/chain/'+str(i)+'.css'] = (
                200, 'text/css', ('div {background:url('+str(i+1)+'.css)}').encode())
        app.overrides['/css/main.css'] = (200, 'text/css', b'div {background:url(/chain/0.css)}')
        with self.assertRaises(PreviewPreflightError):
            preflight_preview(app)

    def test_quoted_css_imports_check_missing_and_external_stylesheets(self):
        app = SyntheticPreview()
        app.overrides['/css/main.css'] = (
            200, 'text/css', b'@import /* comment */ "missing.css"; @import \'https://external.invalid/private.css\';')
        app.overrides['/css/missing.css'] = (404, 'text/plain', b'missing')
        result = preflight_preview(app)
        self.assertFalse(result['offline_preview_passed'])
        self.assertEqual(result['failures']['display_dependencies'], 1)
        self.assertEqual(result['failures']['external_display_dependencies'], 1)
        self.assertIn('/css/missing.css', app.visited)
        self.assertTrue(all(not target.startswith('http') for target in app.visited))
        self.assertNotIn('private.css', json.dumps(result))

    def test_commented_css_urls_and_imports_do_not_create_dependencies(self):
        app = SyntheticPreview()
        app.overrides['/css/main.css'] = (
            200, 'text/css', b'/* @import "missing.css"; div {background:url(https://external.invalid/font)} */')
        result = preflight_preview(app)
        self.assertTrue(result['offline_preview_passed'])
        self.assertNotIn('/css/missing.css', app.visited)

    def test_cli_failure_is_nonzero_and_does_not_print_private_paths(self):
        output = io.StringIO()
        with patch('tools.preflight_wii_shop.load_preview_application',
                   side_effect=ValueError('private-path-or-content')), contextlib.redirect_stdout(output):
            self.assertEqual(main(['--catalog', 'private/synthetic.json']), 1)
        data = json.loads(output.getvalue())
        self.assertFalse(data['offline_preview_passed'])
        self.assertNotIn('private-path', output.getvalue())

    def test_cli_accepts_shared_pack_overrides_and_returns_failed_report(self):
        output = io.StringIO()
        app = SyntheticPreview()
        app.overrides['/script.js'] = (404, 'text/plain', b'missing')
        with patch('tools.preflight_wii_shop.load_preview_application', return_value=app) as load, \
                contextlib.redirect_stdout(output):
            self.assertEqual(main(['--catalog', 'private/synthetic.json']), 1)
        packs = load.call_args.args[0]
        self.assertIsInstance(packs, PreviewPacks)
        self.assertEqual(packs.catalog, Path('private/synthetic.json'))
        self.assertFalse(json.loads(output.getvalue())['offline_preview_passed'])


if __name__ == '__main__':
    unittest.main()
