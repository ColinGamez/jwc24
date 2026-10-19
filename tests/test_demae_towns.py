from pathlib import Path
import tempfile
import unittest

from test_japan_post import source
from jwc24.japan_post import build_database
from jwc24.demae_towns import town_candidates
from tools.build_demae_town_fixture import build_towns
import xml.etree.ElementTree as ET
from jwc24.demae_area_registry import AreaRegistry, area_identity, assign_area_codes
from jwc24.demae_response import inspect_area_response, ResponseFormatError


class TownTests(unittest.TestCase):
    def test_duplicate_town_labels_keep_distinct_source_postcodes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'postal.sqlite'
            build_database(source(
                ('10201', '3700001', 'Gunma', 'Maebashi', 'Same Town'),
                ('10201', '3700002', 'Gunma', 'Maebashi', 'Same Town')), path)
            data, report = build_towns(path, '10201')
            rows = ET.fromstring(data).findall('areaList/container0/list/row')
            self.assertEqual(report['row_count'], 2)
            self.assertEqual([row.findtext('kanji2') for row in rows], ['Same Town'] * 2)
            self.assertEqual({row.findtext('zipCode') for row in rows}, {'3700001', '3700002'})
            self.assertEqual(len({row.findtext('areaCode') for row in rows}), 2)
            with self.assertRaises(ResponseFormatError):
                inspect_area_response(data.replace(b'3700001', b'370001'), variant='list')

    def test_unrepresentable_short_name_is_preserved_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'postal.sqlite'
            build_database(source(('10201', '3700001', '群馬県', '前橋市', '😀'),
                                  ('10201', '3700002', '群馬県', '前橋市', 'A')), path)
            rows = town_candidates(path, '10201')
            blocked = next(row for row in rows if row['name'] == '😀')
            self.assertFalse(blocked['label_eligible'])
            self.assertEqual(blocked['review_reason'], 'shift_jis_unrepresentable')
            data, report = build_towns(path, '10201')
            self.assertEqual(report['row_count'], 1)
            self.assertEqual(report['excluded'][0]['name'], '😀')

    def test_identity_ambiguity_and_display_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'postal.sqlite'
            build_database(source(*[('10201', '3700001', '群馬県', '前橋市', name)
                for name in ('A', 'B', '以下に掲載がない場合', '😀' * 16)]), path)
            rows = town_candidates(path, '10201')
            self.assertEqual(len({row['experimental_code'] for row in rows}), 4)
            self.assertTrue(all(len(row['experimental_code']) <= 15 for row in rows))
            self.assertEqual(sum(row['label_eligible'] for row in rows), 2)
            self.assertFalse(any(row['native_selectable'] for row in rows))
            self.assertEqual({row['review_reason'] for row in rows},
                             {None, 'municipality_default', 'label_exceeds_capacity'})
            self.assertEqual(rows, town_candidates(path, '10201'))
            data, report = build_towns(path, '10201')
            self.assertEqual(report['row_count'], 2)
            self.assertEqual(len(report['excluded']), 2)
            self.assertEqual([row.text for row in ET.fromstring(data).iter('isNextArea')], ['0', '0'])
            registry = AreaRegistry(assign_area_codes({}, [area_identity('10201', row['postal'], row['name']) for row in rows]))
            decimal_data, decimal_report = build_towns(path, '10201', registry=registry)
            self.assertTrue(decimal_report['decimal_registry_used'])
            codes = [row.text for row in ET.fromstring(decimal_data).iter('areaCode')]
            self.assertTrue(all(len(code) == 11 and code.isascii() and code.isdigit() for code in codes))
            self.assertEqual({registry.resolve(code)['town'] for code in codes}, {'A', 'B'})
            with self.assertRaises(ValueError):
                build_towns(path, '10201', registry=AreaRegistry({}))
            self.assertEqual(next(row['name'] for row in rows if row['native_label_units'] == 32), '😀' * 16)
            with self.assertRaises(ValueError):
                town_candidates(path, 'JP-10')
