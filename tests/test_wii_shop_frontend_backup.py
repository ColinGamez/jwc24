from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import zlib

from tools.inspect_wii_shop_frontend_backup import listing_rows, member_path, summarize
from tools.import_wii_shop_frontend_capture import PRIVATE, extract_selected, select_members
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE, KEYBOARD_SHA256, CapturedScripts


class FrontendBackupInventoryTests(unittest.TestCase):
    def test_query_values_are_not_published_with_the_inventory(self):
        listing = ('Path = capture\nSize = 0\nAttributes = D\n\n'
                   'Path = capture/W_03.jsp?country=JP&language=ja&serial=private&token=secret\n'
                   'Size = 42\nFolder = -\n\nPath = capture/common.js\nSize = 7\n')
        report = summarize(listing_rows(StringIO(listing)))
        self.assertEqual(report['capture_files'], 2)
        self.assertEqual(report['declared_uncompressed_bytes'], 49)
        self.assertEqual(report['navigation_page_basenames'], {'W_03.jsp': 1})
        self.assertEqual(report['regional_filename_hints'], {'country=JP': 1, 'language=JA': 1})
        for secret in ('private', 'secret', 'token=', 'serial='):
            self.assertNotIn(secret, json.dumps(report))

    def test_unsafe_paths_and_duplicate_fields_are_rejected(self):
        for path in ('../outside', 'root/../outside', '/absolute', 'C:\\outside', '\\\\host\\file'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                member_path(path)
        with self.assertRaises(ValueError):
            list(listing_rows(StringIO('Path = a\nPath = b\n')))

    def test_links_and_oversized_members_are_rejected(self):
        for row in ({'Path': 'link', 'Size': '1', 'Symbolic Link': '../outside'},
                    {'Path': 'huge', 'Size': str(256*1024*1024+1)}):
            with self.assertRaises(ValueError):
                summarize([row])

    def test_selection_keeps_only_matched_japanese_details_and_shared_resources(self):
        def row(path):
            return {'Path': path, 'Size': '8', 'CRC': '00000000'}
        prefix = 'oss-auth.shop.wii.com/oss/'
        rows = [row(prefix+'serv/B_05.jsp?titleId=000100014142434A&country=JP'),
                row(prefix+'serv/B_05.jsp?titleId=000100014142434A&country=US'),
                row(prefix+'serv/B_05.jsp?titleId=0001000141424342&country=JP'),
                row(prefix+'oss/common/script.js'), row(prefix+'oss/common/download.sh'),
                row(prefix+'ccs/000100014142434A/FFFD0001')]
        chosen = select_members(rows, {'000100014142434A'})
        self.assertEqual(chosen, [rows[0], rows[3]])

    def test_captured_script_body_must_match_the_reviewed_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'blobs').mkdir()
            (root/'blobs'/KEYBOARD_SHA256).write_bytes(bytes(1426))
            manifest = {'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1, 'files': [{
                'member': 'oss-auth.shop.wii.com/oss/oss/common/js/keyboard.js',
                'bytes': 1426, 'sha256': KEYBOARD_SHA256, 'file': 'blobs/'+KEYBOARD_SHA256}]}
            (root/'manifest.private.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                CapturedScripts(root)

    def test_navigation_selection_excludes_product_pages_scripts_and_zero_length_responses(self):
        prefix = 'oss-auth.shop.wii.com/oss/'
        rows = [{'Path': prefix+path, 'Size': str(size)} for path, size in
                (('serv/B_03.jsp', 42), ('serv/B_16.jsp', 42), ('serv/W_02_1.jsp?language=jp', 42),
                 ('serv/B_05.jsp?titleId=000100014142434A&country=JP', 42), ('serv/B_04.jsp', 42),
                 ('serv/B_17.jsp', 0), ('oss/common/script.js', 42), ('serv/urls.sh', 42))]
        self.assertEqual(select_members(rows, set(), navigation_only=True), rows[:3])

    def test_title_image_selection_follows_explicit_file_ids_and_excludes_other_payloads(self):
        prefix='oss-auth.shop.wii.com/oss/ccs/000100014142434A/'
        rows=[{'Path':prefix+name,'Size':'100'} for name in ('FFFD0001','FFFD0005','00000001','tmd')]
        chosen=select_members(rows,{'000100014142434A'},title_images_only=True,image_members={prefix+'FFFD0005'})
        self.assertEqual(chosen,[rows[1]])
        self.assertEqual(select_members(rows,{'000100014142434A'},title_images_only=True),[rows[0]])

    def test_large_japanese_all_titles_page_is_bounded_and_region_specific(self):
        prefix = 'oss-auth.shop.wii.com/oss/serv/B_04.jsp?country='
        rows = [{'Path':prefix+region,'Size':str(size)} for region,size in
                (('JP&all=true',6*1024*1024),('US&all=true',6*1024*1024),('JP',9*1024*1024))]
        self.assertEqual(select_members(rows,set(),japan_catalog_only=True),rows[:1])
        self.assertEqual(select_members(rows,set()),[])
        self.assertEqual(select_members(rows,set(),catalog_only=True),rows[:2])
        with self.assertRaises(ValueError):
            select_members(rows,set(),catalog_only=True,japan_catalog_only=True)

    def test_title_support_selection_requires_exact_region_page_and_known_title(self):
        prefix = 'oss-auth.shop.wii.com/oss/serv/'
        paths = ['B_08.jsp?country=JP&titleId=000100014142434A',
                 'B_08.jsp?country=US&titleId=000100014142434A',
                 'B_08.jsp?country=JP&titleId=0001000141424342',
                 'B_07.jsp?country=JP&titleId=000100014142434A']
        rows = [{'Path':prefix+path,'Size':'100'} for path in paths]
        self.assertEqual(select_members(rows,{'000100014142434A'},title_support_only=True),rows[:1])

    @unittest.skipUnless(Path('C:/Program Files/7-Zip/7z.exe').is_file(), 'Extraction test requires 7-Zip')
    def test_stream_extraction_hashes_url_names_and_detects_wrong_member_boundaries(self):
        PRIVATE.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=PRIVATE) as directory:
            root = Path(directory)
            archive = root/'fixture.zip'
            entries = [('capture/b.jsp?country=JP&serial=private', b'first'),
                       ('capture/a.js', b'second')]
            with zipfile.ZipFile(archive, 'w') as package:
                for name, data in entries:
                    package.writestr(name, data)
            rows = [{'Path': name, 'Size': str(len(data)), 'CRC': f'{zlib.crc32(data):08X}'}
                    for name, data in entries]
            files = extract_selected(archive, rows, root/'good', 'C:/Program Files/7-Zip/7z.exe')
            for item, (_, expected) in zip(files, entries):
                self.assertEqual((root/'good'/item['file']).read_bytes(), expected)
                self.assertNotIn('?', item['file'])
            rows[0]['CRC'] = '00000000'
            with self.assertRaisesRegex(ValueError, 'CRC'):
                extract_selected(archive, rows, root/'bad', 'C:/Program Files/7-Zip/7z.exe')
