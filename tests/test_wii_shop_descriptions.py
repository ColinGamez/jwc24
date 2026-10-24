"""Synthetic fixtures only; captured proprietary pages/images stay private."""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24 import wii_shop_descriptions as descriptions
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from tools import import_wii_shop_descriptions as importer

TITLE = '000100014142434A'
OTHER = '000100014142444A'
SCRIPT = b'var scroll_step = 30;\nfunction kdown(id) { return id; }\n'


def detail(identifier=TITLE, flag='false', title='Synthetic title'):
    return (f'<html><head><script>var titleId="{identifier}";'
            f'var isFreeIntroEnabled="{flag}";'
            'if (isFreeIntroEnabled=="true") '
            'setUnderButtonR(true, "More Details", '
            f'"javascript:showPage(\'ext/B_30.jsp?titleId={identifier}\')", "wiiSelectSound()"); '
            'else setUnderButtonR(true, "More Details", '
            f'"javascript:showPage(\'B_06.jsp?titleId={identifier}\')", "wiiSelectSound()");'
            f'</script></head><body><div id="TitleName1">{title}</div></body></html>').encode()


def description(identifier=TITLE, title='Synthetic title'):
    return (f'<html><head><link href="{descriptions.STYLESHEETS[0]}" rel="stylesheet">'
            f'<link href="{descriptions.STYLESHEETS[1]}" rel="stylesheet">'
            '<style>#goodsfree{overflow:auto} #text{width:280px}</style>'
            '<script>setUnderButtonL(true, "Back", "javascript:showBack()", "snd.playSE(cSE_Cancel)");'
            + SCRIPT.decode() + '//--></script></head>'
            '<body onkeypress="kdown(\'goodsfree\');" onload="initPage(); goodsfree.focus()">'
            '<div id="goodsfree"><div id="text">合成の説明。<br>Second line.</div>'
            f'<div id="image02"><img src="/oss/ccs/{identifier}/FFFD0002"></div>'
            f'<div id="image01"><img src="/oss/ccs/{identifier}/FFFD0003"></div></div>'
            '<div id="goodsdetails"></div>'
            f'<div id="TitleName1stline">{title}</div><div id="Platform">Synthetic</div>'
            '</body></html>').encode()


def image():
    from PIL import Image
    stream = BytesIO()
    Image.new('RGB', (160, 120), 'black').save(stream, format='PNG')
    return stream.getvalue()


def listing_row(member, size=100, **changes):
    return dict({'Path': member, 'Size': str(size), 'CRC': '1234ABCD',
                 'Encrypted': '-'}, **changes)


def member(kind, identifier=TITLE):
    return descriptions.HOST + f'/oss/serv/{kind}.jsp?titleId={identifier}&country=JP'


class DescriptionsTests(unittest.TestCase):
    def setUp(self):
        self.scroll_pin = patch.object(descriptions, 'SCROLL_SHA256', hashlib.sha256(SCRIPT).hexdigest())
        self.scroll_pin.start()
        self.addCleanup(self.scroll_pin.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def pack(self, *, title='Synthetic title', detail_title='Synthetic title', omit=(), corrupt_image=False):
        files = []

        def blob(raw, member_name, stage):
            digest = hashlib.sha256(raw).hexdigest()
            local = self.root / stage / 'blobs' / digest
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(raw)
            row = {'member': member_name, 'bytes': len(raw), 'sha256': digest,
                   'file': stage + '/blobs/' + digest}
            files.append(row)
            return row

        b05 = detail(title=detail_title)
        b06 = description(title=title)
        d = blob(b05, member('B_05'), 'source-pages')
        p = blob(b06, member('B_06'), 'source-pages')
        parsed = descriptions.parse_description(b06, TITLE)
        for resource in parsed['screenshots']:
            if resource not in omit:
                raw = b'invalid synthetic image' if corrupt_image else image()
                row = blob(raw, descriptions.HOST + resource, 'screenshots')
                row['image_info'] = descriptions.image_info(image())
        manifest = {'schema_version': 1, 'validation_revision': descriptions.VALIDATION_REVISION,
                    'source': SOURCE, 'archive_sha1': ARCHIVE_SHA1,
                    'archive_sha256': descriptions.ARCHIVE_SHA256,
                    'catalog_sha256': 'a' * 64, 'listing_sha256': 'b' * 64,
                    'selection': 'japan-b06-descriptions', 'files': files, 'excluded': {},
                    'titles': {TITLE: {'detail_member': d['member'],
                                      'description_member': p['member'],
                                      'description_sha256': p['sha256'],
                                      'detail_proof': descriptions.b05_description_link(b05, TITLE),
                                      'display_title_differs': title != detail_title,
                                      'screenshots': parsed['screenshots'],
                                      'shared_paths': parsed['shared_paths'],
                                      'content_activities': parsed['content_activities'],
                                      'back_button': parsed['back_button']}}}
        self.write_manifest(manifest)
        return manifest, parsed

    def write_manifest(self, manifest):
        (self.root / 'manifest.private.json').write_text(json.dumps(manifest), encoding='utf-8')

    def load(self, shared=None):
        return descriptions.Descriptions(self.root, 'a' * 64, {TITLE},
                                         shared_paths=set(descriptions.STYLESHEETS) if shared is None else shared)

    def test_preserves_description_layout_copy_and_exact_image_bytes(self):
        self.pack()
        pack = self.load()
        self.assertEqual(set(pack.rows), {TITLE})
        tree, styles, stylesheets = pack.page(TITLE)
        self.assertEqual(tree.find('goodsfree').attrs['id'], 'goodsfree')
        self.assertIn('合成の説明。', tree.render())
        self.assertIn('#goodsfree{overflow:auto}', styles)
        self.assertEqual(stylesheets, descriptions.STYLESHEETS)
        self.assertEqual(pack.asset(f'/oss/ccs/{TITLE}/FFFD0002'), (200, 'image/png', image()))
        self.assertEqual(pack.asset(descriptions.SCROLL_SCRIPT_URL)[2], SCRIPT)
        tree.find('text').children = ['changed']
        self.assertIn('合成の説明。', pack.page(TITLE)[0].render())
        self.assertIsNone(pack.page(OTHER))
        self.assertEqual(pack.asset(f'/oss/ccs/{OTHER}/FFFD0002')[0], 404)

    def test_b05_same_id_generated_route_is_required(self):
        for raw in (detail(flag='true'), detail(flag=''),
                    detail().replace(b'B_06.jsp?titleId=' + TITLE.encode(), b'B_06.jsp?titleId=' + OTHER.encode()),
                    detail().replace(b'var titleId="' + TITLE.encode(), b'var titleId="' + OTHER.encode())):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                descriptions.b05_description_link(raw, TITLE)

    def test_display_title_differences_are_preserved_not_treated_as_id_conflicts(self):
        self.pack(title='Synthetic title®', detail_title='Synthetic title')
        pack = self.load()
        self.assertTrue(pack.rows[TITLE]['display_title_differs'])
        self.assertIn('Synthetic title®', pack.page(TITLE)[0].render())

    def test_mismatched_ccs_id_absent_title_and_unreviewed_scripts_reject(self):
        source = description()
        cases = [source.replace(f'/oss/ccs/{TITLE}/FFFD0002'.encode(), f'/oss/ccs/{OTHER}/FFFD0002'.encode()),
                 source.replace(b'Synthetic title</div>', b'</div>'),
                 source.replace(SCRIPT, SCRIPT + b'fetch("https://invalid/");\n'),
                 source.replace(b'FFFD0003', b'NOTANIMAGE'),
                 source.replace(b'id="goodsdetails"', b'id="different"'),
                 source.replace('合成'.encode(), '\ufffd'.encode())]
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                descriptions.parse_description(raw, TITLE)

    def test_alternative_exact_source_screenshot_file_ids_are_preserved(self):
        raw = description().replace(b'FFFD0002', b'FFFD0006').replace(b'FFFD0003', b'FFFD001C')
        self.assertEqual(descriptions.parse_description(raw, TITLE)['screenshots'],
                         [f'/oss/ccs/{TITLE}/FFFD0006', f'/oss/ccs/{TITLE}/FFFD001C'])

    def test_missing_or_invalid_screenshots_exclude_page_without_substitutes(self):
        self.pack(omit=(f'/oss/ccs/{TITLE}/FFFD0003',))
        pack = self.load()
        self.assertFalse(pack.rows)
        self.assertIsNone(pack.page(TITLE))
        self.assertFalse(pack.images)
        self.assertIn(TITLE, pack.excluded)

    def test_invalid_image_bytes_exclude_page(self):
        self.pack(corrupt_image=True)
        with self.assertRaises(ValueError):
            self.load().asset(f'/oss/ccs/{TITLE}/FFFD0002')

    def test_missing_shared_original_stylesheet_excludes_page(self):
        self.pack()
        self.assertFalse(self.load(shared=set()).rows)

    def test_original_content_activity_inventory_and_embedded_content_gate(self):
        raw = description().replace(b'Second line.',
            b'<a href="https://publisher.invalid/original">Synthetic link</a>'
            b'<script>syntheticUnreviewed();</script><form action="/unreviewed"></form>')
        parsed = descriptions.parse_description(raw, TITLE)
        self.assertEqual([a['tag'] for a in parsed['content_activities']], ['a', 'script', 'form'])
        self.assertEqual(parsed['content_activities'][0]['attrs']['href'],
                         'https://publisher.invalid/original')
        self.assertEqual(parsed['back_button']['target'], 'javascript:showBack()')
        manifest, _ = self.pack()
        manifest['titles'][TITLE]['content_activities'] = parsed['content_activities']
        self.write_manifest(manifest)
        self.assertFalse(self.load().rows)

    def test_inline_css_dependencies_require_captured_namespaces(self):
        raw = description().replace(b'#text{width:280px}',
            b'#text{background:url("/oss/oss/common/images/synthetic.gif")}')
        parsed = descriptions.parse_description(raw, TITLE)
        self.assertIn('/oss/oss/common/images/synthetic.gif', parsed['shared_paths'])
        self.assertEqual(parsed['inline_css_urls'], ['/oss/oss/common/images/synthetic.gif'])
        for url in ('https://unreviewed.invalid/image.png', '//unreviewed.invalid/image.png',
                    'data:image/png;base64,AAAA', '/outside/image.png'):
            source = description().replace(b'#text{width:280px}',
                ('#text{background:url("' + url + '")}').encode())
            with self.subTest(url=url), self.assertRaises(ValueError):
                descriptions.parse_description(source, TITLE)

    def test_startup_does_not_read_original_payloads_and_caches_are_bounded(self):
        self.pack()
        with patch.object(descriptions, 'read_blob', side_effect=AssertionError('eager payload read')):
            pack = self.load()
            self.assertIn(TITLE, pack.rows)
        with patch.object(descriptions, 'read_blob', wraps=descriptions.read_blob) as read:
            pack.page(TITLE)
            count = read.call_count
            pack.page(TITLE)
            self.assertEqual(read.call_count, count)
        self.assertEqual(pack._page.cache_info().maxsize, 8)
        self.assertEqual(pack._image.cache_info().maxsize, 16)

    def test_source_catalog_and_page_fingerprint_binding(self):
        original, _ = self.pack()
        for mutate in (lambda m: m.update(catalog_sha256='c' * 64),
                       lambda m: m.update(validation_revision=1),
                       lambda m: m.update(archive_sha256='c' * 64),
                       lambda m: m['titles'][TITLE].update(description_sha256='c' * 64),
                       lambda m: m['titles'][TITLE]['detail_proof'].update(flag='true'),
                       lambda m: m['files'][0].update(file='../outside'),
                       lambda m: m['files'].append(deepcopy(m['files'][0]))):
            altered = deepcopy(original)
            mutate(altered)
            self.write_manifest(altered)
            with self.assertRaises(ValueError):
                self.load()

    def test_raw_source_drift_rejects(self):
        manifest, _ = self.pack()
        local = self.root / manifest['files'][0]['file']
        local.write_bytes(local.read_bytes() + b'x')
        with self.assertRaises(ValueError):
            self.load().page(TITLE)

    def test_mime_dimension_metadata_is_checked_against_decoded_image(self):
        manifest, _ = self.pack()
        manifest['files'][2]['image_info']['width'] = 161
        self.write_manifest(manifest)
        with self.assertRaises(ValueError):
            self.load().asset(f'/oss/ccs/{TITLE}/FFFD0002')

    def test_page_selection_is_catalog_japan_only_and_excludes_binaries(self):
        selected = [listing_row(member('B_05')), listing_row(member('B_06'))]
        irrelevant = [listing_row(member('B_06', OTHER)),
                      listing_row(member('B_06').replace('country=JP', 'country=US')),
                      listing_row(descriptions.HOST + f'/oss/ccs/{TITLE}/00000001'),
                      listing_row(descriptions.HOST + f'/oss/oss/ext/manual/{TITLE}/index.html')]
        self.assertEqual(importer.select_source_pages(iter(selected + irrelevant), {TITLE}), selected)
        with self.assertRaises(ValueError):
            importer.select_source_pages(iter(selected + selected[:1]), {TITLE})

    def test_exact_screenshot_selection_never_expands_to_other_ccs_members(self):
        wanted = descriptions.HOST + f'/oss/ccs/{TITLE}/FFFD0002'
        good = listing_row(wanted)
        other = listing_row(wanted.replace('FFFD0002', 'FFFD0000'))
        self.assertEqual(importer.select_screenshots(iter([good, other]), {wanted}), [good])
        with self.assertRaises(ValueError):
            importer.select_screenshots(iter([good, good]), {wanted})
        # An alternative file ID is eligible only if explicitly source referenced.
        self.assertEqual(importer.select_screenshots(iter([other]), {other['Path']}), [other])

    def test_linked_encrypted_oversized_and_ambiguous_members_reject(self):
        source = listing_row(member('B_06'))
        for changes in ({'Symbolic Link': 'target'}, {'Hard Link': 'target'}, {'Encrypted': '+'},
                        {'Size': str(2 * 1024 * 1024 + 1)}, {'CRC': 'invalid'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                importer.select_source_pages(iter([dict(source, **changes)]), {TITLE})
        duplicate = listing_row(member('B_06') + '&language=JA')
        with self.assertRaises(ValueError):
            importer.select_source_pages(iter([source, duplicate]), {TITLE})

    def test_import_output_must_be_new_and_private(self):
        with self.assertRaises(ValueError):
            importer.import_descriptions('absent', 'absent', 'absent', self.root / 'output', 'absent')

    def test_two_stage_import_then_reader_preserves_source_bound_flow(self):
        payloads = {member('B_05'): detail(), member('B_06'): description(),
                    descriptions.HOST + f'/oss/ccs/{TITLE}/FFFD0002': image(),
                    descriptions.HOST + f'/oss/ccs/{TITLE}/FFFD0003': image(),
                    descriptions.HOST + f'/oss/ccs/{TITLE}/FFFD0000': b'not an image/manual pack'}
        rows = [listing_row(name, len(data)) for name, data in payloads.items()]
        listing = self.root / 'listing.txt'
        listing.write_text('\n\n'.join('\n'.join(f'{k} = {v}' for k, v in row.items())
                                     for row in rows), encoding='utf-8')
        catalog = self.root / 'catalog.json'
        record = {'title_id': TITLE, 'name': 'Synthetic', 'title_version': 0,
                  'catalog_id': 'synthetic', 'title_id_status': 'source_metadata',
                  'region_label': 'Japan', 'category_label': 'WiiWare', 'is_demo': False,
                  'is_dlc': False, 'japan_browse_candidate': True, 'title_id_evidence': {}}
        catalog.write_text(json.dumps({'records': [record]}), encoding='utf-8')
        stages = []

        def extract(archive, selected, output, sevenzip):
            stages.append([row['Path'] for row in selected])
            result = []
            for row in selected:
                data = payloads[row['Path']]
                digest = hashlib.sha256(data).hexdigest()
                local = output / 'blobs' / digest
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(data)
                result.append({'member': row['Path'], 'bytes': len(data),
                               'sha256': digest, 'file': 'blobs/' + digest})
            return result

        output = self.root / 'pack'
        with patch.object(importer, 'PRIVATE', self.root), \
                patch.object(importer, 'verify_archive', return_value=descriptions.ARCHIVE_SHA256), \
                patch.object(importer, 'extract_selected', side_effect=extract):
            report = importer.import_descriptions('synthetic.7z', listing, catalog, output, 'synthetic-7z')
        self.assertEqual(len(stages), 2)
        self.assertEqual(set(stages[0]), {member('B_05'), member('B_06')})
        self.assertEqual(set(stages[1]), {descriptions.HOST + p for p in
                                         (f'/oss/ccs/{TITLE}/FFFD0002', f'/oss/ccs/{TITLE}/FFFD0003')})
        self.assertEqual(report['eligible_descriptions'], 1)
        self.assertFalse(report['routes_enabled'])
        loaded = descriptions.Descriptions(output, hashlib.sha256(catalog.read_bytes()).hexdigest(),
                                           {TITLE}, shared_paths=set(descriptions.STYLESHEETS))
        self.assertIn('合成の説明。', loaded.page(TITLE)[0].render())
        self.assertEqual(loaded.asset(f'/oss/ccs/{TITLE}/FFFD0002')[2], image())


if __name__ == '__main__':
    unittest.main()
