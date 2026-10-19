import csv
import io
from pathlib import Path
import tempfile
import unittest

from jwc24.japan_post import areas, build_database, lookup, records


def source(*entries):
    output = io.StringIO()
    writer = csv.writer(output)
    for municipality, postal, prefecture, city, town in entries:
        writer.writerow([municipality, '', postal, '', '', '', prefecture, city, town,
                         '0', '0', '0', '0', '0', '0'])
    return output.getvalue().encode('utf-8')


class JapanPostTests(unittest.TestCase):
    def test_navigation_preserves_postal_ambiguity_and_leading_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'postal.sqlite'
            row = ('01101', '0010001', '北海道', '札幌市中央区', '北一条')
            summary = build_database(source(row, row, (*row[:4], '北二条'),
                ('10201', '3700000', '群馬県', '前橋市', '以下に掲載がない場合')), database)
            self.assertEqual(summary, {'records': 3, 'prefectures': 2})
            self.assertEqual(len(lookup(database, '0010001')), 2)
            self.assertEqual(areas(database)[0]['id'], 'JP-01')
            self.assertEqual(areas(database, 'JP-01'), [{'id': '01101', 'name': '札幌市中央区'}])
            self.assertEqual(len(areas(database, '01101')), 2)
            self.assertEqual(areas(database, '10201')[0]['kind'], 'municipality_default')
            self.assertEqual(lookup(database, '9999999'), [])
            with self.assertRaises(ValueError):
                build_database(source(row), database)

    def test_rejects_malformed_identifiers_and_input(self):
        for municipality, postal in [('00001', '0010001'), ('48001', '0010001'),
                                    ('01101', '００１０００１'), ('01101', '10001')]:
            with self.assertRaises(ValueError):
                list(records(source((municipality, postal, 'a', 'b', 'c'))))
        with self.assertRaises(ValueError):
            list(records(b'a,b,c\n'))
        for value in [None, 1234567, '1234567 OR 1=1', '１２３４５６７']:
            with self.assertRaises(ValueError):
                lookup('missing.sqlite', value)
        for value in ['JP-00', 'JP-48', "01101' OR 1=1", 1101]:
            with self.assertRaises(ValueError):
                areas('missing.sqlite', value)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'missing.sqlite'
            with self.assertRaises(Exception):
                lookup(database, '0010001')
            self.assertFalse(database.exists())
