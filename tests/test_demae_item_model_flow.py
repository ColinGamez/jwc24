"""Stock-native item/variant/basket-identity checks; synthetic offline data only."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from tools.build_demae_area_fixture import native_xml
from tools.verify_demae_item_model_flow import verify_item_flow


def item_fixture(*, items=1, stocks=('0', '1')):
    root = ET.Element('response')
    ET.SubElement(root, 'Count').text = str(items)
    listing = ET.SubElement(root, 'List')
    for index in range(items):
        container = ET.SubElement(listing, 'container'+str(index))
        ET.SubElement(container, 'name').text = '\u5408\u6210\u54c1'+str(index)
        item = ET.SubElement(container, 'item')
        for key, value in {'menuCode': 'SYN-MENU', 'itemCode': 'SYN-PRODUCT-'+str(index),
                'price': '1280', 'info': 'synthetic fixture', 'size': '\u666e\u901a',
                'image': 'synthetic-image.jpg', 'isSoldout': '0'}.items():
            ET.SubElement(item, key).text = value
        sizes = ET.SubElement(item, 'sizeList')
        for number, stock in enumerate(stocks):
            row = ET.SubElement(sizes, 'variant'+str(number))
            for key, value in {'itemCode': 'SYN-VARIANT-'+str(index)+'-'+str(number),
                    'size': '\u5c0f' if number == 0 else '\u5927',
                    'price': str(1280+number*700), 'isSoldout': stock}.items():
                ET.SubElement(row, key).text = value
    ET.SubElement(ET.SubElement(root, 'apiStatus'), 'code').text = '0'
    return root


class NativeItemFlowTests(unittest.TestCase):
    def source(self):
        path = Path('private/demae/frontend-v512/0001-00000001.decompressed.dol')
        if not path.is_file():
            self.skipTest('Private stock HCHJ v512 application required')
        return path.read_bytes()

    def run_fixture(self, root=None, **options):
        return verify_item_flow(self.source(), native_xml(item_fixture() if root is None else root), **options)

    def test_original_consumer_to_owned_variants_to_basket_code_matching(self):
        with patch('socket.socket', side_effect=AssertionError('Native item test opened a socket')):
            result = self.run_fixture(item_fixture(items=2), basket_codes=[
                (0, 'SYN-VARIANT-0-1'), (1, 'SYN-VARIANT-1-0'), (0, 'SYN-ABSENT')])
        self.assertTrue(result['accepted'])
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(result['items'][0]['name'], '\u5408\u6210\u54c10')
        sizes = result['items'][0]['sizeList']
        self.assertEqual([row['price'] for row in sizes], ['1,280\u5186', '1,980\u5186'])
        self.assertEqual([row['native_soldout_flag'] for row in sizes], [False, True])
        self.assertEqual(result['native_indexed_variant_identity_checks'], 4)
        self.assertEqual([row['selected_variant_index'] for row in result['native_basket_code_matches']], [1, 0, None])
        self.assertEqual([row['matched_count'] for row in result['native_basket_code_matches']], [1, 1, 0])
        self.assertTrue(result['xml_payload_overwrite_preserves_owned_model'])
        self.assertTrue(result['object_heap_stack_and_write_bounds_verified'])
        self.assertFalse(result['native_model_mocked'])
        self.assertFalse(result['native_price_formatter_mocked'])
        self.assertFalse(result['native_stock_comparison_mocked'])
        self.assertFalse(result['xml_bytes_native_parsed'])
        self.assertFalse(result['basket_record_parsed_or_submitted'])
        self.assertFalse(result['current_availability_or_orderability_verified'])

    def test_missing_required_size_fields_and_empty_variant_list_reject(self):
        root = item_fixture(stocks=('0',))
        variants = []
        empty = deepcopy(root)
        empty.find('./List/container0/item/sizeList').clear()
        variants.append(empty)
        for name in ('itemCode', 'price', 'isSoldout'):
            changed = deepcopy(root)
            row = changed.find('./List/container0/item/sizeList/variant0')
            row.remove(row.find(name))
            variants.append(changed)
        for variant in variants:
            with self.subTest(xml=native_xml(variant)):
                result = self.run_fixture(variant)
                self.assertFalse(result['accepted'])
                self.assertEqual(result['items'], [])

    def test_explicit_zero_prices_use_the_original_formatter_unchanged(self):
        root = item_fixture()
        root.find('./List/container0/item/price').text = '0'
        root.find('./List/container0/item/sizeList/variant0/price').text = '0'
        result = self.run_fixture(root)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['items'][0]['price'], '0\u5186')
        self.assertEqual(result['items'][0]['sizeList'][0]['price'], '0\u5186')
        self.assertFalse(result['native_price_formatter_mocked'])

    def test_missing_later_price_breaks_size_loop_and_retains_only_preceding_rows(self):
        root = item_fixture()
        later = root.find('./List/container0/item/sizeList/variant1')
        later.remove(later.find('price'))
        result = self.run_fixture(root)
        self.assertTrue(result['accepted'])
        self.assertEqual(len(result['items'][0]['sizeList']), 1)
        self.assertEqual(result['items'][0]['sizeList'][0]['itemCode'], 'SYN-VARIANT-0-0')

    def test_duplicate_variant_codes_are_first_match_and_need_a_producer_guard(self):
        root = item_fixture()
        root.find('./List/container0/item/sizeList/variant1/itemCode').text = 'SYN-VARIANT-0-0'
        result = self.run_fixture(root, basket_codes=[(0, 'SYN-VARIANT-0-0')])
        self.assertTrue(result['accepted'])
        self.assertEqual(len(result['items'][0]['sizeList']), 2)
        self.assertEqual(result['native_basket_code_matches'][0]['selected_variant_index'], 0)

    def test_exact_one_stock_flag_is_not_general_boolean_coercion(self):
        stocks = ('0', '1', '01', 'true', 'unknown')
        result = self.run_fixture(item_fixture(stocks=stocks))
        self.assertTrue(result['accepted'])
        self.assertEqual([row['native_soldout_flag'] for row in result['items'][0]['sizeList']],
                         [False, True, False, False, False])

    def test_mocked_empty_payload_retains_native_default_soldout(self):
        root = item_fixture(stocks=('',))
        result = self.run_fixture(root)
        self.assertEqual(result['items'][0]['sizeList'][0]['isSoldout'], '1')
        self.assertTrue(result['items'][0]['sizeList'][0]['native_soldout_flag'])
        self.assertTrue(result['xml_lookup_storage_payload_wrappers_and_status_mocked'])

    def test_variant_and_item_node_allocation_failure_do_not_insert_partial_item(self):
        for options in ({'fail_variant_node': 1}, {'fail_variant_node': 3}, {'fail_item_node': 1}):
            with self.subTest(options=options):
                result = self.run_fixture(**options)
                self.assertFalse(result['accepted'])
                self.assertEqual(result['items'], [])

    def test_second_item_failure_retains_first_owned_item_without_rollback_claim(self):
        result = self.run_fixture(item_fixture(items=2), fail_item_node=2)
        self.assertFalse(result['accepted'])
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['itemCode'], 'SYN-PRODUCT-0')
        self.assertEqual(len(result['items'][0]['sizeList']), 2)

    def test_stock_source_and_offline_input_guards(self):
        with self.assertRaises(ValueError):
            verify_item_flow(b'not-the-stock-application', b'<response></response>')
        source = self.source()
        for xml in (b'', b'x'*65537, b'<!DOCTYPE r><response></response>', b'<response/>'):
            with self.subTest(xml=xml[:30]), self.assertRaises(ValueError):
                verify_item_flow(source, xml)
        for options in ({'fail_item_node': True}, {'fail_variant_node': 0},
                        {'basket_codes': [(0, 'a\0b')]}, {'basket_codes': [(True, 'x')]}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_fixture(**options)


if __name__ == '__main__':
    unittest.main()
