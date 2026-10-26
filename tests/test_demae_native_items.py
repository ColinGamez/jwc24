"""Conservative candidate gate; synthetic menu facts never reach a service."""
import unittest
from xml.etree import ElementTree as ET

from jwc24.demae_native_items import inspect_native_item_candidate, NativeItemShapeError
from tools.build_demae_area_fixture import native_xml
from tests.test_demae_item_model_flow import item_fixture


class NativeItemCandidateTests(unittest.TestCase):
    def inspect(self, root=None, **options):
        return inspect_native_item_candidate(native_xml(item_fixture() if root is None else root),
                                             menu_code=options.get('menu_code', 'SYN-MENU'))

    def test_complete_shape_stays_distinct_from_provider_evidence_and_orderability(self):
        result = self.inspect(item_fixture(items=2))
        self.assertEqual((result.items, result.variants), (2, 4))
        self.assertFalse(result.provider_evidence_verified)
        self.assertFalse(result.current_orderability_verified)
        self.assertFalse(result.native_rendering_verified)
        self.assertNotIn('SYN-MENU', repr(result))
        self.assertNotIn('SYN-PRODUCT', repr(result))

    def test_explicit_zero_prices_are_structural_facts_without_orderability(self):
        root = item_fixture()
        root.find('./List/container0/item/price').text = '0'
        root.find('./List/container0/item/sizeList/variant0/price').text = '0'
        result = self.inspect(root)
        self.assertEqual((result.items, result.variants), (1, 2))
        self.assertFalse(result.current_orderability_verified)
        root.find('./List/container0/item/sizeList/variant0/price').text = '00'
        with self.assertRaises(NativeItemShapeError):
            self.inspect(root)

    def test_parent_and_variant_identity_ambiguity_is_rejected_without_value_echo(self):
        root = item_fixture()
        root.find('./List/container0/item/sizeList/variant1/itemCode').text = 'SYN-VARIANT-0-0'
        with self.assertRaises(NativeItemShapeError) as caught:
            self.inspect(root)
        self.assertNotIn('SYN-VARIANT', str(caught.exception))
        root = item_fixture(items=2)
        root.find('./List/container1/item/itemCode').text = 'SYN-PRODUCT-0'
        with self.assertRaises(NativeItemShapeError):
            self.inspect(root)

    def test_selected_menu_count_and_container_order_must_agree(self):
        with self.assertRaises(NativeItemShapeError):
            self.inspect(menu_code='another-menu')
        for update in ('count', 'name', 'status_order'):
            root = item_fixture()
            if update == 'count':
                root.find('Count').text = '2'
            elif update == 'name':
                root.find('./List/container0').tag = 'container1'
            else:
                status = root.find('apiStatus')
                root.remove(status)
                root.insert(0, status)
            with self.subTest(update=update), self.assertRaises(NativeItemShapeError):
                self.inspect(root)

    def test_incomplete_size_price_or_stock_facts_cannot_be_filled_in(self):
        roots = []
        for tag in ('sizeList', 'price', 'isSoldout'):
            root = item_fixture()
            if tag == 'sizeList':
                root.find('./List/container0/item/sizeList').clear()
            else:
                variant = root.find('./List/container0/item/sizeList/variant1')
                variant.remove(variant.find(tag))
            roots.append(root)
        for value in ('unknown', '01', ''):
            root = item_fixture()
            root.find('./List/container0/item/sizeList/variant0/isSoldout').text = value
            roots.append(root)
        for value in ('1,280', '1280\u5186', '00', '01280', '1000001'):
            root = item_fixture()
            root.find('./List/container0/item/sizeList/variant0/price').text = value
            roots.append(root)
        for root in roots:
            with self.subTest(xml=native_xml(root)), self.assertRaises(NativeItemShapeError):
                self.inspect(root)

    def test_native_lexical_form_and_error_status_are_separate_required_gates(self):
        root = item_fixture()
        plain_text = ET.tostring(root, encoding='utf-8')
        with self.assertRaises(NativeItemShapeError):
            inspect_native_item_candidate(plain_text, menu_code='SYN-MENU')
        root.find('./apiStatus/code').text = '13'
        with self.assertRaises(NativeItemShapeError):
            self.inspect(root)
        data = native_xml(item_fixture()).replace(b'</sizeList>', b'<unexpected/></sizeList>')
        with self.assertRaises(NativeItemShapeError):
            inspect_native_item_candidate(data, menu_code='SYN-MENU')

    def test_xml_and_text_limits_reject_corrupt_or_unrepresentable_input(self):
        data = native_xml(item_fixture())
        for candidate in (b'', b'x'*65537, b'<!DOCTYPE x>'+data, b'\xff'+data,
                          data.replace(b'<response>', b'<response xmlns="urn:wrong">'),
                          data.replace(b'SYN-MENU', '\U0001f600'.encode())):
            with self.subTest(size=len(candidate)), self.assertRaises(NativeItemShapeError):
                inspect_native_item_candidate(candidate, menu_code='SYN-MENU')
        root = item_fixture()
        root.find('./List/container0/name').text = 'x'*129
        with self.assertRaises(NativeItemShapeError):
            self.inspect(root)


if __name__ == '__main__':
    unittest.main()
