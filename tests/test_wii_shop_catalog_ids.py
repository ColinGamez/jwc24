import unittest

from jwc24.wii_shop_catalog_ids import enrich


class ShopCatalogIdTests(unittest.TestCase):
    def row(self, **changes):
        return dict({'filename': 'Test (Japan).wad', 'row': 2,
                     'title_id': '0001000154455354', 'version': '0', 'region': 'Japan'}, **changes)

    def record(self):
        return {'filename': 'Test (Japan).wad', 'region_label': 'Japan', 'title_id': None}

    def test_exact_mapping_preserves_provenance_and_zero_version(self):
        original = self.record()
        result = enrich([original], [self.row()], {'sha256': 'fixture', 'columns': 'A:D'})[0]
        self.assertEqual(result['title_version'], 0)
        self.assertEqual(result['title_id_status'], 'source_metadata')
        self.assertEqual(result['title_id_evidence']['row'], 2)
        self.assertFalse(result['tmd_verified'])
        self.assertFalse(result['install_supported'])
        self.assertIsNone(original['title_id'])

    def test_duplicate_filename_does_not_choose_first(self):
        result = enrich([self.record()], [self.row(), self.row(row=3)], {})[0]
        self.assertIsNone(result['title_id'])
        self.assertEqual(result['title_id_unresolved_reason'], 'ambiguous_filename')

    def test_bad_id_version_and_region_leave_unresolved(self):
        for change in ({'title_id': 'ABCD'}, {'version': '65536'}, {'version': '=1+1'}, {'region': 'USA'}):
            with self.subTest(change=change):
                self.assertIsNone(enrich([self.record()], [self.row(**change)], {})[0]['title_id'])

    def test_filename_match_is_exact_not_fuzzy(self):
        result = enrich([self.record()], [self.row(filename='Test.wad')], {})[0]
        self.assertEqual(result['title_id_unresolved_reason'], 'filename_not_found')
