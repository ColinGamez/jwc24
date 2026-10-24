import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.inspect_wii_shop_category_capture import inspect_html, inspect_listing, inspect_manifest, summarize_capture, target
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE


class CategoryCaptureTests(unittest.TestCase):
    def test_code_route_decodes_entities_and_omits_free_text(self):
        source = '''<div id="word011">Board &amp; Table</div>
        <div id="spacer011"><a href="javascript:showPage('B_04.jsp?genre=BOARD%2fTABLE&amp;publisher=private-name&amp;token=secret')">x</a></div>'''
        result = inspect_html(source, 'B_16.jsp')
        self.assertEqual(result['controls'], [{'slot': '011', 'label': 'Board & Table',
                         'page': 'B_04.jsp', 'category_codes': {'genre': ['BOARD/TABLE']}}])
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('private-name', json.dumps(result))

    def test_heading_and_empty_catalog_do_not_claim_search_empty(self):
        result = inspect_html('<div id="text01-01"><a href="x">Again</a></div><div id="catalogFrame"></div>', 'B_04.jsp')
        self.assertEqual(result['catalog_state'], {'catalog_frame_present': True, 'panel_count': 0, 'heading_text': 'Again',
                         'heading_link_present': True, 'heading_input_present': False,
                         'heading_caption_kind': None, 'captured_english_no_results_notice_present': False,
                         'not_found_element_present': False})
        populated = inspect_html('<div id="catalogFrame"><!-- comment --><script>var x=0;</script><div id="panel01">Title</div></div>', 'B_04.jsp')
        self.assertEqual(populated['catalog_state']['panel_count'], 1)

    def test_no_results_notice_differs_from_empty_page_frame(self):
        source = '''<div id="text01-01"><div id="listinfo"><script>document.write("Catalog".replace('x', ' '));</script></div></div>
        <div id="text02-01">Your search did not return any results.<br>Notice</div>'''
        state = inspect_html(source, 'B_04.jsp')['catalog_state']
        self.assertFalse(state['catalog_frame_present'])
        self.assertTrue(state['captured_english_no_results_notice_present'])
        self.assertEqual(state['heading_caption_kind'], 'catalog')

    def test_listing_counts_encoded_missing_names_without_query_values(self):
        rows = [{'Path': 'host/oss/serv/B_17.jsp%3Ftoken%3Dsecret', 'Size': '1'},
                {'Path': 'host/oss/serv/B_04.jsp?genre=ACTION&key=private', 'Size': '1'},
                {'Path': 'host/oss/serv/B_23.jsp', 'Folder': '+'}]
        result = inspect_listing(rows)
        self.assertEqual(result['missing_page_filename_hits']['B_17.jsp'], 1)
        self.assertEqual(result['missing_page_filename_hits']['B_23.jsp'], 0)
        self.assertEqual(result['B_04_requests_with_filter_key']['genre'], 1)
        self.assertEqual(result['B_04_requests_with_filter_key']['key'], 1)
        self.assertNotIn('private', json.dumps(result))
        self.assertIsNone(target('https://example.org/not-a-shop-page'))

    def test_original_input_control_reports_keyboard_constants_only(self):
        source = '''<div id="text04">Search by Game Title</div><div id="spacer04">
        <input maxlength="40" onmousedown="kbd.call(cKT_PredictNoLF, 5, false, 'private prompt');"
        onchange="searchUrl=addParam('B_04.jsp?p=1&amp;vc=true', 'title', searchValue);" /></div>'''
        result = inspect_html(source, 'B_01.jsp')
        self.assertEqual(result['controls'][0]['keyboard_rows'], 5)
        self.assertEqual(result['controls'][0]['keyboard_mode'], 'cKT_PredictNoLF')
        self.assertNotIn('private prompt', json.dumps(result))

    def test_manifest_checks_bytes_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = b'<div id="catalogFrame"></div>'
            (root/'blob').write_bytes(data)
            row = {'member': 'oss-auth.shop.wii.com/oss/serv/B_04.jsp?country=JP&p=85&token=secret',
                   'file': 'blob', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            def write():
                (root/'manifest.private.json').write_text(json.dumps({'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1, 'files': [row]}), encoding='utf-8')
            write()
            result = inspect_manifest(root)
            self.assertEqual(result['pages'][0]['request_page_number'], 85)
            self.assertNotIn('secret', json.dumps(result))
            (root/'blob').write_bytes(b'x'*len(data))
            with self.assertRaisesRegex(ValueError, 'checksum/size'):
                inspect_manifest(root)
            row['file'] = '../escape'
            write()
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                inspect_manifest(root)

    def test_manifest_rejects_wrong_source_archive_and_member_host(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = b'<div id="catalogFrame"></div>'
            (root/'blob').write_bytes(data)
            row = {'member': 'oss-auth.shop.wii.com/oss/serv/B_04.jsp?p=1',
                   'file': 'blob', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            manifest = {'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1, 'files': [row]}
            def write():
                (root/'manifest.private.json').write_text(json.dumps(manifest), encoding='utf-8')
            for key in ('source', 'archive_sha1'):
                original = manifest[key]
                manifest[key] = 'unrelated-archive'
                write()
                with self.assertRaisesRegex(ValueError, 'source'):
                    inspect_manifest(root)
                manifest[key] = original
            row['member'] = 'other.example/oss/serv/B_04.jsp?p=1'
            write()
            with self.assertRaisesRegex(ValueError, 'member host/path'):
                inspect_manifest(root)

    def test_summary_keeps_exception_evidence_without_all_populated_pages(self):
        observation = inspect_html('<div id="catalogFrame"><div id="panel01">x</div></div>', 'B_04.jsp')
        observation.update(sha256='a'*64, bytes=1, request_page_number=1, request_region_hints={})
        result = summarize_capture({'capture_name': 'test', 'manifest_sha256': 'b'*64,
                                    'pages': [observation]*100})
        self.assertEqual(result['catalog_state_counts'], {'populated_catalog': 100})
        self.assertEqual(len(result['representative_catalog_pages']), 1)


if __name__ == '__main__':
    unittest.main()
