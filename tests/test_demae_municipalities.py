import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from test_japan_post import source
from jwc24.japan_post import build_database
from tools.build_demae_municipality_fixtures import build_municipalities


class MunicipalityFixtureTests(unittest.TestCase):
    def test_unique_municipalities_and_safe_native_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'postal.sqlite'
            build_database(source(('10201', '3700001', '群馬県', '前橋市', 'A'),
                                  ('10201', '3700002', '群馬県', '前橋市', 'B'),
                                  ('10202', '3700003', '群馬県', '高崎市', 'C')), database)
            data, report = build_municipalities(database, 'JP-10')
            self.assertEqual(report['row_count'], 2)
            root = ET.fromstring(data)
            self.assertEqual([row.text for row in root.iter('areaCode')],
                             ['M10201', 'M10202'])
            self.assertIn(b'<![CDATA[', data)
            with self.assertRaises(ValueError):
                build_municipalities(database, 'JP-48')
