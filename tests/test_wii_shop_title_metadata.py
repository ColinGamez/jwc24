import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_title_metadata import parse_detail, TitleMetadata
from tests.test_wii_shop_browse import record
from tools.build_wii_shop_image_requests import resolve_photo, resolve_catalog


class HistoricalTitleMetadataTests(unittest.TestCase):
    identifier = '0001000141424344'

    def page(self, internal=None, displayed='1,000 Wii Points', literal="'1000'", extra=''):
        return (f'<script>var titleId="{internal or self.identifier}";var titlePoints={literal};</script>'
                '<div id="TitleName1">テスト &amp; 名前<script>untrusted();</script></div>'
                '<div id="Publisher"><span>Example &amp; Co</span></div>'
                '<div id="date">Released 12/13/1984</div><div id="Players">For 1-2 players</div>'
                '<div id="Platform">Virtual Console Arcade</div><div id="DisplayCategory">Action</div>'
                f'<div id="price">{displayed}</div>{extra}').encode()

    def metadata(self, root, row=None, **changes):
        document = dict(schema_version=1, source=SOURCE, archive_sha1=ARCHIVE_SHA1,
                        catalog_sha256='a'*64, capture_manifest_sha256='b'*64,
                        records={self.identifier: row or parse_detail(self.page(), self.identifier)})
        document.update(changes)
        path = root/'metadata.json'
        path.write_text(json.dumps(document), encoding='utf-8')
        return path

    def test_visible_fields_and_literal_points_agree_without_running_scripts(self):
        value = parse_detail(self.page(), self.identifier)
        self.assertEqual(value['title'], 'テスト & 名前')
        self.assertEqual(value['publisher'], 'Example & Co')
        self.assertEqual(value['points'], 1000)
        self.assertEqual(value['captured_display_date'], 'Released 12/13/1984')
        self.assertNotIn('wii_release_date', value)
        self.assertEqual(value['capture_sha256'], hashlib.sha256(self.page()).hexdigest())

    def test_mismatched_or_absent_internal_identity_cannot_supply_metadata(self):
        for data in (self.page(internal='0001000141424345'), b'<div id="TitleName1">name</div>'):
            with self.assertRaisesRegex(ValueError, 'title ID'):
                parse_detail(data, self.identifier)

    def test_original_photo_scope_selects_the_requested_asset_without_guessing(self):
        extra = ('<img src="/oss/ccs/0001000141424345/FFFD0001">'
                 '<div id="Photo"><a><img src="/oss/ccs/'+self.identifier+'/FFFD0005"></a></div>')
        data = self.page(extra=extra)
        metadata = parse_detail(data,self.identifier)
        selected = resolve_photo(data,self.identifier,metadata)
        self.assertTrue(selected['member'].endswith('/'+self.identifier+'/FFFD0005'))
        self.assertEqual(selected['reference_detail_sha256'],hashlib.sha256(data).hexdigest())
        changed = dict(metadata,title='wrong cached title')
        with self.assertRaises(ValueError):
            resolve_photo(data,self.identifier,changed)
        with self.assertRaises(ValueError):
            resolve_photo(self.page(),self.identifier,parse_detail(self.page(),self.identifier))

    def test_ambiguous_price_is_unknown_instead_of_selected_or_invented(self):
        for page in (self.page(displayed='500 Wii Points'), self.page(literal='calculatePrice()'),
                     self.page(extra='<script>var titlePoints=500;</script>')):
            self.assertIsNone(parse_detail(page, self.identifier)['points'])
        self.assertEqual(parse_detail(self.page(displayed='0 Wii Points', literal='0'), self.identifier)['points'], 0)

    def test_catalog_icon_requires_a_matching_detail_link_inside_the_original_panel(self):
        def page(identifier, extra=''):
            return ('<body><div id="panel01"><a href="javascript:showPage(\'B_05.jsp?titleId='+identifier+
                    '\')"><img src="/oss/ccs/'+self.identifier+'/FFFD0000"></a>'+extra+'</div></body>').encode()
        data = page(self.identifier)
        result = resolve_catalog(data,{self.identifier})
        self.assertTrue(result[self.identifier]['member'].endswith('/FFFD0000'))
        self.assertEqual(result[self.identifier]['reference_catalog_sha256'],hashlib.sha256(data).hexdigest())
        self.assertEqual(resolve_catalog(page('0001000141424345'),{self.identifier}),{})
        self.assertEqual(resolve_catalog(page(self.identifier,'<img src="/oss/ccs/'+self.identifier+'/FFFD0001">'),{self.identifier}),{})
        self.assertEqual(resolve_catalog(data,set()),{})

    def test_duplicate_display_fields_and_bad_text_are_rejected(self):
        for data in (self.page(extra='<div id="Publisher">other</div>'),
                     self.page().replace('テスト'.encode(), '\ufffd'.encode()), b'\xff'):
            with self.assertRaises((ValueError, UnicodeError)):
                parse_detail(data, self.identifier)

    def test_catalog_binding_type_checks_and_returned_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.metadata(root)
            with self.assertRaisesRegex(ValueError, 'catalog'):
                TitleMetadata(path, 'c'*64)
            with self.assertRaisesRegex(ValueError, 'catalog'):
                TitleMetadata(path, 'a'*64, 'd'*64)
            metadata = TitleMetadata(path, 'a'*64)
            value = metadata.get(self.identifier)
            value['title'] = 'changed'
            self.assertEqual(metadata.get(self.identifier)['title'], 'テスト & 名前')
            for key, bad in (('points', True), ('owned', True)):
                row = parse_detail(self.page(), self.identifier)
                row[key] = bad
                with self.assertRaises(ValueError):
                    TitleMetadata(self.metadata(root, row), 'a'*64)

    def test_original_title_alias_is_searchable_without_claiming_price_or_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = TitleMetadata(self.metadata(Path(directory)), 'a'*64)
            catalog = Catalog([record(name='Romanized file name')], title_metadata=metadata)
            result = catalog.query(search='テスト')['items'][0]
            self.assertEqual(result['historical_metadata']['points'], 1000)
            self.assertIsNone(result['price'])
            self.assertIsNone(result['owned'])
            self.assertFalse(result['install_supported'])
            result['historical_metadata']['title'] = 'changed'
            self.assertEqual(catalog.query(search='テスト')['total'], 1)
            self.assertIn('Romanized file name', catalog.items[0]['names'])

    def test_historical_groupings_keep_unknown_titles_out_of_named_choices(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = TitleMetadata(self.metadata(Path(directory)), 'a'*64)
            catalog = Catalog([record(), record('0001000141424345', name='Unmatched')], title_metadata=metadata)
            self.assertEqual(catalog.facets('publisher'), [{'value': 'Example & Co', 'count': 1}])
            self.assertEqual(catalog.facets('display_genre'), [{'value': 'Action', 'count': 1}])
            self.assertEqual(catalog.facets('platform'), [{'value': 'Virtual Console Arcade', 'count': 1}])
            self.assertEqual(catalog.facets('publisher', category='Virtual Console'), [])
            self.assertEqual(catalog.query(publisher='Example & Co', display_genre='Action')['total'], 1)
            self.assertEqual(catalog.query(platform='Virtual Console Arcade')['total'], 1)
            self.assertEqual(catalog.query(platform='VCA')['total'], 1)
            self.assertEqual(catalog.query(publisher='Missing')['total'], 0)
            self.assertEqual(catalog.query()['total'], 2)
            for options in ({'publisher': ''}, {'display_genre': True}, {'platform': 'x'*121}):
                with self.assertRaises(ValueError):
                    catalog.query(**options)
