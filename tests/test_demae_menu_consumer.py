from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from tools.verify_demae_menu_consumer import verify


class NativeMenuConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1]/'private/demae/fixtures/HCHJ-local-api.dol'
        if not path.is_file():
            raise unittest.SkipTest('Private native executable unavailable')
        cls.source = path.read_bytes()

    def document(self, count=2):
        root = ET.Element('response')
        for number in range(count):
            row = ET.SubElement(root, 'row')
            for key, value in {'menuCode': f'M{number}', 'linkTitle': 'Menu',
                               'enabledLink': '1' if number else '0', 'name': '\u6d77\u9bae',
                               'info': 'Source observation', 'setNum': '0',
                               'lunchMenuList': ''}.items():
                ET.SubElement(row, key).text = value
        ET.SubElement(ET.SubElement(root, 'apiStatus'), 'code').text = '0'
        return root

    def check(self, root):
        return verify(self.source, ET.tostring(root))

    def test_native_control_flow_preserves_rows_and_flags_with_mocked_models(self):
        report = self.check(self.document())
        self.assertTrue(report['accepted'])
        self.assertEqual([r['menuCode'] for r in report['inserted_rows']], ['M0', 'M1'])
        self.assertEqual([r['enabledLink'] for r in report['inserted_rows']], [0, 1])
        self.assertEqual(report['inserted_rows'][1]['name'], '\u6d77\u9bae')
        self.assertTrue(report['native_model_mocked'])
        self.assertFalse(report['native_rendering_verified'])

    def test_each_missing_required_field_and_status_order_fails(self):
        for field in ('menuCode', 'linkTitle', 'enabledLink', 'name', 'info', 'setNum', 'lunchMenuList'):
            root = self.document()
            root[0].remove(root[0].find(field))
            with self.subTest(field=field):
                self.assertFalse(self.check(root)['accepted'])
        root = self.document()
        status = root[-1]
        root.remove(status)
        root.insert(0, status)
        self.assertFalse(self.check(root)['accepted'])
        self.assertFalse(self.check(self.document(0))['accepted'])

    def test_fingerprint_and_uncovered_lunch_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(b'wrong executable', b'<response></response>')
        root = self.document()
        ET.SubElement(root[0].find('lunchMenuList'), 'isLunchTimeMenu').text = '1'
        with self.assertRaisesRegex(ValueError, 'non-lunch'):
            self.check(root)
