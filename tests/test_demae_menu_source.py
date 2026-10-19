import unittest
from jwc24.demae_menu_source import parse_official_menu


def product(name='Real &amp; Named', price='&#xA5;1,218 ~', code='1602'):
    return (f'<div class="product-container"><a class="product-page-link" '
            f'href="/menu-pizza/{code}"><span class="menu-entry">{name}</span>'
            '<p class="menu-page-product-description">Source description</p></a>'
            f'<div><span class="size-price">{price}</span></div></div>')


class OfficialMenuSourceTests(unittest.TestCase):
    def test_source_labels_do_not_become_checkout_quotes(self):
        result = parse_official_menu(product().encode())
        row = result['products']['1602']
        self.assertEqual(row['name'], 'Real & Named')
        self.assertEqual(row['advertised_price_labels'], ['\u00a51,218 ~'])
        self.assertIsNone(row['exact_price_yen'])
        self.assertIsNone(row['delivery_eligibility'])
        self.assertFalse(row['orderable'])
        self.assertEqual(row['source_url'], 'https://www.dominos.jp/menu-pizza/1602')

    def test_identical_repeated_products_deduplicate(self):
        self.assertEqual(len(parse_official_menu((product()*2).encode())['products']), 1)
        with self.assertRaises(ValueError):
            parse_official_menu((product()+product(price='999')).encode())

    def test_incomplete_or_corrupt_snapshot_rejected(self):
        for data in (b'', product().encode()[:-6], product(name='').encode(),
                     product(name='\ufffd').encode()):
            with self.subTest(data=data[:15]), self.assertRaises(ValueError):
                parse_official_menu(data)

    def test_foreign_links_are_not_promoted_to_official_products(self):
        data = product().replace('/menu-pizza/1602', 'https://example.org/menu-pizza/1602')
        with self.assertRaises(ValueError):
            parse_official_menu(data.encode())
        with self.assertRaises(ValueError):
            parse_official_menu(product().encode(), source_url='https://example.org/menu')

    def test_nested_text_and_void_image_keep_product_association(self):
        data = product(name='<b>Real</b> Pizza').replace('<a ', '<img src="x"><a ')
        row = parse_official_menu(data.encode())['products']['1602']
        self.assertEqual(row['name'], 'Real Pizza')
        self.assertEqual(row['advertised_price_labels'], ['\u00a51,218 ~'])


if __name__ == '__main__':
    unittest.main()
