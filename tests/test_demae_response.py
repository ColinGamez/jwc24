import unittest
import xml.etree.ElementTree as ET
from jwc24.demae_response import MAX_XML_BYTES, ResponseFormatError, inspect_area_response
from tools.build_demae_area_fixture import build_fixture, build_root_fixture, build_postal_fallback_fixture, build_auth_fixture, build_document_fixture, native_xml


def document(body='<kanji1>群馬県</kanji1><kanji2>高崎市</kanji2><kanji3>非公開住所</kanji3>'):
    return native_xml(ET.fromstring('<response><apiStatus><code>0</code></apiStatus>'
            '<areaCount>2</areaCount><areaList>' + body + '</areaList></response>'))


ROW = '<row><kanji2/><areaCode>TEST</areaCode><isNextArea>0</isNextArea><display>0</display></row>'


class ResponseTests(unittest.TestCase):
    def test_empty_fields_use_explicit_closing_tags_for_native_parser(self):
        xml = build_fixture()
        self.assertIn(b'<kanji3></kanji3>', xml)
        self.assertNotIn(b'/>', xml)
        for empty in (b'<kanji3/>', b'<kanji3 />'):
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(xml.replace(b'<kanji3></kanji3>', empty, 1), variant='list')
    def test_root_selection_uses_direct_code_elements_and_segment_labels(self):
        xml = build_root_fixture()
        self.assertEqual(inspect_area_response(xml, variant='root')['row_count'], 47)
        rows = ET.fromstring(xml).find('areaList')
        self.assertEqual(rows[0].tag, 'TEST-JP-01')
        self.assertTrue(all(len(row) == 1 and row[0].tag == 'segment' for row in rows))
        for bad in (build_fixture(), xml.replace(b'segment', b'wrong'),
                    xml.replace(b'TEST-JP-02', b'TEST-JP-01')):
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(bad, variant='root')

    def test_native_values_require_nonempty_cdata_and_serializer_rejects_terminator(self):
        xml = build_document_fixture()
        with self.assertRaises(ResponseFormatError):
            inspect_area_response(xml.replace(b'<![CDATA[0]]>', b'0'), variant='documents')
        with self.assertRaises(ResponseFormatError):
            inspect_area_response(xml.replace(b'<![CDATA[0]]>', b'<![CDATA[]]>'), variant='documents')
        node = ET.Element('response')
        node.text = 'bad]]>text'
        with self.assertRaises(ValueError):
            native_xml(node)
    def test_document_template_required_containers_text_and_version(self):
        xml = build_document_fixture()
        report = inspect_area_response(xml, variant='documents')
        self.assertEqual(report['document_count'], 3)
        self.assertEqual(report['version'], 1)
        for bad in (xml.replace(b'container2', b'wrong'),
                    xml.replace(b'<version><![CDATA[1', b'<version><![CDATA[-1'),
                    xml.replace(b'<![CDATA[LOCAL TEST. Orders are not sent.]]>', b'', 1)):
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(bad, variant='documents')

    def test_auth_key_required_and_not_reported(self):
        xml = build_auth_fixture()
        report = inspect_area_response(xml, variant='auth')
        self.assertNotIn('OFFLINE-TEST-TOKEN', str(report))
        for bad in (xml.replace(b'OFFLINE-TEST-TOKEN', b''),
                    xml.replace(b'<authKey>', b'<wrong>').replace(b'</authKey>', b'</wrong>'),
                    xml.replace(b'<code><![CDATA[0', b'<code><![CDATA[13')):
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(bad, variant='auth')

    def test_postal_fallback_direct_status_and_no_selected_area_required(self):
        xml = build_postal_fallback_fixture()
        self.assertEqual(inspect_area_response(xml, variant='postal-fallback')['api_code'], 13)
        self.assertEqual(inspect_area_response(xml.replace(b'CDATA[13]', b'CDATA[14]'), variant='postal-fallback')['api_code'], 14)
        for bad in (xml.replace(b'CDATA[13]', b'CDATA[0]'),
                    xml.replace(b'<apiStatus>', b'<nested><apiStatus>').replace(b'</apiStatus>', b'</apiStatus></nested>')):
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(bad, variant='postal-fallback')

    def test_prefecture_fixture_rows_and_missing_conditional_fields(self):
        xml = build_fixture()
        report = inspect_area_response(xml, variant='list')
        self.assertEqual(report['row_count'], 47)
        self.assertEqual(report['area_codes_over_15_utf8_bytes'], 0)
        for bad in (xml.replace(b'<kanji3></kanji3>', b'', 1),
                    xml.replace(b'<display><![CDATA[1]]></display>', b'', 1),
                    xml.replace(b'<kanji3></kanji3>', b'<kanji3>text</kanji3>', 1)):
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(bad, variant='list')
        # Empty primary text follows the traced fallback branch.
        xml = xml.replace('<kanji2><![CDATA[北海道]]></kanji2>'.encode(), b'<kanji2></kanji2>', 1).replace(b'<kanji3></kanji3>', b'', 1)
        self.assertEqual(inspect_area_response(xml, variant='list')['row_count'], 47)

    def test_hierarchy_metadata_does_not_disclose_address(self):
        result = inspect_area_response(document())
        self.assertEqual(result['declared_area_count'], 2)
        self.assertNotIn('非公開住所', str(result))
        with self.assertRaises(ResponseFormatError):
            inspect_area_response(b'<offlineFixture>' + document() + b'</offlineFixture>')

    def test_recursive_status_and_list_partial_hierarchy(self):
        xml = document('<container0><kanji1>群馬県</kanji1><list>'+ROW+ROW+'</list></container0>').replace(b'<code><![CDATA[0]]></code>', b'<nested><code><![CDATA[0]]></code></nested>')
        self.assertEqual(inspect_area_response(xml, variant='list')['variant'], 'list')
        with self.assertRaises(ResponseFormatError):
            inspect_area_response(xml, variant='address')

    def test_list_containers_and_positive_count(self):
        body = '<container0><kanji1>群馬県</kanji1><list>'+ROW+'</list></container0><container1><segment>あ</segment><list>'+ROW+'</list></container1>'
        self.assertEqual(inspect_area_response(document(body), variant='list')['declared_area_count'], 2)
        for xml in (document(body).replace(b'<areaCount><![CDATA[2', b'<areaCount><![CDATA[0'),
                    document(body).replace('<segment><![CDATA[あ]]></segment>'.encode(), b''),
                    document(body).replace(b'<areaCount><![CDATA[2', b'<areaCount><![CDATA[1'),
                    document(body).replace(b'<areaCount><![CDATA[2', b'<areaCount><![CDATA[3'),
                    document('<kanji1>群馬県</kanji1>')):
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(xml, variant='list')

    def test_bad_status_hierarchy_counts_entities_encoding_and_limits(self):
        cases = [document().replace(b'<code><![CDATA[0', b'<code><![CDATA[99'),
                 document().replace(b'<areaCount><![CDATA[2', b'<areaCount><![CDATA[-1'),
                 document().replace(b'<areaCount><![CDATA[2', b'<areaCount><![CDATA[2147483648'),
                 document().replace(b'<kanji1>', b'<wrong>').replace(b'</kanji1>', b'</wrong>'),
                 b'<!DOCTYPE root [<!ENTITY x "expanded">]>' + document(),
                 document().decode().encode('utf-16'), b'x' * (MAX_XML_BYTES + 1),
                 b'<root>' + b'<x>' * 40 + b'</x>' * 40 + b'</root>',
                 document().replace(b'</apiStatus>', b'<code>0</code></apiStatus>')]
        for xml in cases:
            with self.subTest(length=len(xml)), self.assertRaises(ResponseFormatError):
                inspect_area_response(xml)
        with self.assertRaises(ResponseFormatError):
            inspect_area_response(document(), http_status=500)
