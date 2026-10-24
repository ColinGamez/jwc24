import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zlib

from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_manual import ARCHIVE_SHA256, CapturedManuals, HOST, PREFIX, manual_path
from tools.import_wii_shop_manual import select_manual_members

TITLE = '000100015732434A'
ROOT = HOST+PREFIX+TITLE+'/FFFD0000/'
INDEX = f'html/{TITLE}/JPN/ja/index.html'


def listing_row(suffix, data=b'fixture'):
    return {'Path': ROOT+suffix, 'Size': str(len(data)), 'CRC': f'{zlib.crc32(data):08X}'}


def write_pack(root):
    (root/'blobs').mkdir()
    files = []
    for suffix, data in ((INDEX, b'<html>test fixture</html>'),
                         ('js/manual.js', b'/* test fixture */'),
                         (f'html/{TITLE}/JPN/ja/image.png', b'test image bytes')):
        digest = hashlib.sha256(data).hexdigest()
        (root/'blobs'/digest).write_bytes(data)
        files.append({'member': ROOT+suffix, 'bytes': len(data), 'sha256': digest,
                      'file': 'blobs/'+digest})
    manifest = {'schema_version': 1, 'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1,
                'archive_sha256': ARCHIVE_SHA256, 'selection': 'japanese-game-manuals',
                'title_ids': [TITLE], 'files': files}
    (root/'manifest.private.json').write_text(json.dumps(manifest), encoding='utf-8')
    return manifest


class ManualSelectionTests(unittest.TestCase):
    def test_only_explicit_japanese_game_locale_and_shared_scripts_are_selected(self):
        rows = [listing_row(INDEX), listing_row('js/manual.js'),
                listing_row(f'html/{TITLE}/USA/en/index.html'),
                listing_row('html/index.html'), listing_row('download.sh')]
        rows.append(dict(listing_row(INDEX), Path=ROOT.replace(TITLE, '000100015732474A')+INDEX))
        self.assertEqual(select_manual_members(rows, {TITLE}), rows[:2])

    def test_missing_japanese_index_and_shop_or_unbounded_title_requests_fail(self):
        for titles in (set(), {'0001000248414241'}, {'0001000157324345'},
                       {f'00010001{i:06X}4A' for i in range(9)}):
            with self.subTest(titles=titles), self.assertRaises(ValueError):
                select_manual_members([], titles)
        with self.assertRaisesRegex(ValueError, 'index is absent'):
            select_manual_members([listing_row('js/manual.js')], {TITLE})

    def test_links_encryption_duplicate_bad_crc_and_member_size_are_rejected(self):
        valid = listing_row(INDEX)
        for changes in ({'Symbolic Link': 'elsewhere'}, {'Hard Link': 'elsewhere'},
                        {'Encrypted': '+'}, {'CRC': 'invalid'}, {'Size': '0'},
                        {'Size': str(2*1024*1024+1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                select_manual_members([dict(valid, **changes)], {TITLE})
        with self.assertRaises(ValueError):
            select_manual_members([valid, valid], {TITLE})

    def test_versions_and_aggregate_bounds_are_checked_before_extraction(self):
        rows = [listing_row(INDEX), dict(listing_row('js/manual.js'),
                                        Path=ROOT.replace('FFFD0000', 'FFFD0001')+'js/manual.js')]
        with self.assertRaisesRegex(ValueError, 'version'):
            select_manual_members(rows, {TITLE})
        with patch('tools.import_wii_shop_manual.MAX_BYTES', 1), self.assertRaisesRegex(ValueError, 'bounds'):
            select_manual_members([listing_row(INDEX)], {TITLE})

    def test_member_paths_cannot_escape_or_alias_the_japanese_namespace(self):
        for suffix in ('js/../manual.js', 'js/%2e%2e/manual.js', 'js/manual.js?token=secret',
                       'js/manual.js#fragment', 'js//manual.js', 'js\\manual.js',
                       f'html/{TITLE}/JPN/ja/../../index.html'):
            with self.subTest(suffix=suffix):
                self.assertIsNone(manual_path(ROOT+suffix))


class ManualReaderTests(unittest.TestCase):
    def test_active_content_stays_disabled_and_passive_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_pack(root)
            reader = CapturedManuals(root)
            for row in manifest['files'][:2]:
                self.assertEqual(reader.asset(row['member'][len(HOST):])[0], 403)
            image = manifest['files'][2]
            self.assertEqual(reader.asset(image['member'][len(HOST):]),
                             (200, 'image/png', b'test image bytes'))
            with self.assertRaisesRegex(ValueError, 'not reviewed'):
                reader.index_url(TITLE)
            self.assertEqual(reader.asset('/outside')[0], 404)

    def test_explicit_review_enables_only_the_fingerprinted_active_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_pack(root)
            index, script = manifest['files'][:2]
            reader = CapturedManuals(root, reviewed_active_sha256=[index['sha256']])
            path = index['member'][len(HOST):]
            self.assertEqual(reader.index_url(TITLE), path)
            self.assertEqual(reader.asset(path)[2], (root/index['file']).read_bytes())
            self.assertEqual(reader.asset(script['member'][len(HOST):])[0], 403)
            self.assertFalse(reader.has_asset(path+'?language=ja'))
            with self.assertRaisesRegex(ValueError, 'absent'):
                CapturedManuals(root, reviewed_active_sha256=['0'*64])

    def test_tampered_blob_or_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_pack(root)
            row = manifest['files'][0]
            blob = root/row['file']
            blob.write_bytes(bytes(row['bytes']))
            with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
                CapturedManuals(root)
            row['file'] = '../outside'
            (root/'manifest.private.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fingerprint/path'):
                CapturedManuals(root)

    def test_wrong_archive_namespace_duplicate_and_ambiguous_version_are_rejected(self):
        for case in ('archive', 'locale', 'duplicate', 'version'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = write_pack(root)
                if case == 'archive':
                    manifest['archive_sha256'] = '0'*64
                elif case == 'locale':
                    manifest['files'][0]['member'] = manifest['files'][0]['member'].replace('/JPN/ja/', '/USA/en/')
                elif case == 'duplicate':
                    manifest['files'].append(manifest['files'][0])
                else:
                    manifest['files'][1]['member'] = manifest['files'][1]['member'].replace('FFFD0000', 'FFFD0001')
                (root/'manifest.private.json').write_text(json.dumps(manifest), encoding='utf-8')
                with self.assertRaises(ValueError):
                    CapturedManuals(root)

    @unittest.skipUnless(Path('private/wii_shop/manual-japan-pilot-v1/manifest.private.json').is_file(),
                         'Private collector pilot is optional')
    def test_private_pilot_is_byte_verified_and_has_no_enabled_active_content(self):
        reader = CapturedManuals('private/wii_shop/manual-japan-pilot-v1')
        self.assertEqual(len(reader.resources), 52)
        self.assertEqual(sum(len(row[1]) for row in reader.resources.values()), 210144)
        self.assertEqual(set(reader.indexes), {TITLE})
        for path, (_, data, _) in reader.resources.items():
            status, _, served = reader.asset(path)
            self.assertEqual(status, 403 if path.endswith(('.html', '.js')) else 200)
            if status == 200:
                self.assertEqual(served, data)


if __name__ == '__main__':
    unittest.main()
