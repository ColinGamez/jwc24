import unittest
import xml.etree.ElementTree as ET
from tools.build_demae_category_fixture import build_categories
from tools.build_demae_area_fixture import native_xml
from jwc24.demae_response import inspect_area_response, ResponseFormatError


class CategoryTests(unittest.TestCase):
    def test_explicit_empty_result_preserves_group_and_status(self):
        data = build_categories([], allow_empty=True)
        self.assertEqual(inspect_area_response(data, variant='categories')['category_count'], 0)
        root = ET.fromstring(data)
        self.assertIsNotNone(root.find('container0/CategoryList'))
        self.assertEqual(root[-1].tag, 'apiStatus')

    def test_ordering_and_cdata_contract(self):
        data = build_categories(['TEST-FOOD', 'TEST-CAFE'])
        self.assertEqual(inspect_area_response(data, variant='categories')['category_count'], 2)
        root = ET.fromstring(data)
        status = root[-1]
        root.remove(status)
        root.insert(0, status)
        with self.assertRaises(ResponseFormatError):
            inspect_area_response(native_xml(root), variant='categories')

    def test_invalid_codes_and_duplicate_rows(self):
        for codes in ([], ['A', 'A'], ['A' * 16], ['a&b']):
            with self.assertRaises(ValueError):
                build_categories(codes)
        root = ET.fromstring(build_categories(['A', 'B']))
        list(root.iter('CategoryCode'))[-1].text = 'A'
        with self.assertRaises(ResponseFormatError):
            inspect_area_response(native_xml(root), variant='categories')
