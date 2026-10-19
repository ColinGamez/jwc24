from copy import deepcopy
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from tools.build_demae_menu_fixture import build_menu_categories
from tools.verify_demae_menu_consumer import verify
from tools.verify_demae_xml_parser import verify_tree


class MenuFixtureTests(unittest.TestCase):
    def menu(self):
        return {'source_url': 'https://demae-can.com/shop/menu/123',
                'restaurant': {'restaurant_id': 'hotpepper:J000000001'},
                'items': [{'category': c} for c in ('\u6d77\u9bae', 'Sides', '\u6d77\u9bae')]}

    def test_stable_branch_bound_category_mapping_and_native_parser_consumer(self):
        menu = self.menu()
        xml, entries = build_menu_categories(menu)
        self.assertEqual([e['source_category'] for e in entries], ['\u6d77\u9bae', 'Sides'])
        self.assertEqual(ET.fromstring(xml)[-1].tag, 'apiStatus')
        self.assertNotIn(b'/>', xml)
        reordered = deepcopy(menu)
        reordered['items'].reverse()
        self.assertEqual(build_menu_categories(reordered)[1], entries)
        other = deepcopy(menu)
        other['source_url'] = 'https://demae-can.com/shop/menu/456'
        self.assertNotEqual(build_menu_categories(other)[1][0]['menu_code'], entries[0]['menu_code'])
        source = Path(__file__).resolve().parents[1]/'private/demae/fixtures/HCHJ-local-api.dol'
        if source.is_file():
            data = source.read_bytes()
            verify_tree(data, xml)
            result = verify(data, xml)
            self.assertTrue(result['accepted'])
            self.assertEqual([r['menuCode'] for r in result['inserted_rows']], [e['menu_code'] for e in entries])
            self.assertEqual([r['name'] for r in result['inserted_rows']], [e['source_category'] for e in entries])

    def test_unsupported_source_text_is_not_rewritten_or_dropped(self):
        menu = self.menu()
        menu['items'].append({'category': '\U0001f600'})
        with self.assertRaises(UnicodeEncodeError):
            build_menu_categories(menu)
        menu['items'] = []
        with self.assertRaises(ValueError):
            build_menu_categories(menu)
