import importlib.util
from pathlib import Path
import unittest


@unittest.skipUnless(importlib.util.find_spec('unicorn'), 'Optional Unicorn dependency')
class NativeXmlTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'private/demae/fixtures/HCHJ-local-api.dol'
        if not path.exists():
            self.skipTest('Private native parser source unavailable')
        self.source = path.read_bytes()

    def test_explicit_empty_fields_preserve_sibling_rows_and_bounded_stack(self):
        from tools.verify_demae_xml_parser import verify
        xml = b'<response>'+b'<row><empty></empty></row>'*236+b'</response>'
        state = verify(self.source, xml)
        self.assertTrue(state['completed'])
        self.assertEqual(state['return_value'], 1)
        self.assertFalse(state['stack_overflow'])
        self.assertEqual(state['max_stack_bytes'], 4*0x1E0)
        nodes = state['nodes']
        response = nodes[nodes[state['root']]['children'][0]]
        self.assertEqual(len(response['children']), 236)
        for child in response['children']:
            row = nodes[child]
            self.assertEqual(row['name'], b'row')
            self.assertEqual([nodes[n]['name'] for n in row['children']], [b'empty'])

    def test_old_self_closing_response_reproduces_native_stack_exhaustion(self):
        from tools.verify_demae_xml_parser import verify
        state = verify(self.source, b'<response>'+b'<row><empty /></row>'*40+b'</response>')
        self.assertTrue(state['stack_overflow'])
        self.assertFalse(state['completed'])
        self.assertGreater(state['max_stack_bytes'], 0x4000)

    def test_tree_verifier_checks_cdata_text_and_empty_siblings(self):
        from tools.verify_demae_xml_parser import verify_tree
        from tools.build_demae_area_fixture import native_xml
        import xml.etree.ElementTree as ET
        root = ET.Element('response')
        for value in ('店舗情報', 'A&B < C'):
            row = ET.SubElement(root, 'row')
            ET.SubElement(row, 'name').text = value
            ET.SubElement(row, 'paymentList')
            ET.SubElement(ET.SubElement(row, 'shopStatus'), 'status')
        state = verify_tree(self.source, native_xml(root))
        self.assertTrue(state['completed'])
        self.assertLess(state['max_stack_bytes'], 0x4000)
