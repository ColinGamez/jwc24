import unittest
import xml.etree.ElementTree as ET
from tools.build_demae_directory_shops import build_directory_shops


class DirectoryShopTests(unittest.TestCase):
    def row(self):
        return {'id': 'hotpepper:J000000001', 'name': 'Real source name',
                'address': 'Real source address',
                'catchphrase': 'Real source description', 'genre': '\u548c\u98df'}

    def test_directory_rows_do_not_invent_payment_prices_or_provider_hours(self):
        data = build_directory_shops([self.row()], '04')
        root = ET.fromstring(data)
        shop = root.find('./container0/CategoryList/row/ShopList/row')
        self.assertEqual(shop.findtext('name'), self.row()['name'])
        self.assertIn(self.row()['catchphrase'], shop.findtext('catchphrase'))
        self.assertIn(self.row()['address'], shop.findtext('catchphrase'))
        self.assertIn('Powered by', shop.findtext('catchphrase'))
        self.assertEqual(shop.findtext('activate'), 'stop')
        self.assertEqual(len(shop.find('paymentList')), 0)
        self.assertIsNone(shop.find('.//isOpen'))
        self.assertIsNone(shop.find('minPrice'))
        self.assertIsNone(shop.find('waitTime'))
        self.assertEqual(root[-1].tag, 'apiStatus')
        self.assertIn(b'<![CDATA[Real source name]]>', data)

    def test_wrong_category_duplicate_missing_text_and_xml_injection_rejected(self):
        for rows, code in [([self.row()], '05'), ([self.row()]*2, '04'),
                           ([dict(self.row(), address='')], '04'),
                           ([dict(self.row(), catchphrase='long source text '*30)], '04'),
                           ([dict(self.row(), name='bad]]>text')], '04'),
                           ([dict(self.row(), name='\U0001f600')], '04')]:
            with self.subTest(code=code, count=len(rows)), self.assertRaises(ValueError):
                build_directory_shops(rows, code)

    def test_missing_optional_description_preserves_real_name_and_address(self):
        for description in ('', None):
            root = ET.fromstring(build_directory_shops([dict(self.row(), catchphrase=description)], '04'))
            body = root.findtext('.//ShopList/row/catchphrase')
            self.assertIn(self.row()['name'], body)
            self.assertIn(self.row()['address'], body)
            self.assertNotIn('None', body)

    def test_excessive_preview_requires_explicit_selection(self):
        rows = [dict(self.row(), id=f'hotpepper:J{n:09d}') for n in range(26)]
        with self.assertRaises(ValueError):
            build_directory_shops(rows, '04')
        root = ET.fromstring(build_directory_shops(rows, '04', max_restaurants=1000))
        self.assertEqual(len(root.findall('.//ShopList/row')), 26)
