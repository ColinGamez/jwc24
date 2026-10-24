import unittest

from jwc24.wii_shop_browse import Catalog


def record(identifier='0001000141424344', name='Test', version=0, **changes):
    return dict({'title_id': identifier, 'name': name, 'title_version': version,
                 'catalog_id': identifier+str(version), 'title_id_status': 'source_metadata',
                 'region_label': 'Japan', 'category_label': 'WiiWare', 'is_demo': False,
                 'is_dlc': False, 'japan_browse_candidate': True,
                 'title_id_evidence': {'row': 2, 'sha256': 'fixture'}}, **changes)


class ShopBrowseTests(unittest.TestCase):
    def test_versioned_listings_group_without_auto_selection(self):
        result = Catalog([record(version=2), record()]).query()['items'][0]
        self.assertEqual(result['versions'], [0, 2])
        self.assertEqual(result['source_listing_count'], 2)
        self.assertTrue(result['variant_selection_required'])
        self.assertNotIn('selected_version', result)
        self.assertFalse(result['tmd_verified'])
        self.assertIsNone(result['owned'])

    def test_pagination_is_stable_across_source_order(self):
        rows = [record('000100010000000'+str(n), 'Game '+str(n)) for n in range(5)]
        a, b = Catalog(rows), Catalog(list(reversed(rows)))
        self.assertEqual(a.query(offset=2, limit=2), b.query(offset=2, limit=2))
        self.assertEqual(a.query(offset=2, limit=2)['next_offset'], 4)
        self.assertIsNone(a.query(offset=4, limit=2)['next_offset'])
        self.assertEqual(a.query(offset=99)['items'], [])

    def test_normalized_search_and_exact_id_filter(self):
        catalog = Catalog([record(name='ＡＢＣ テスト')])
        self.assertEqual(catalog.query(search='abc')['total'], 1)
        self.assertEqual(catalog.query(title_ids=['0001000141424344'])['total'], 1)
        self.assertEqual(catalog.query(title_ids=['0001000141424345'])['total'], 0)

    def test_demo_category_and_unresolved_records(self):
        catalog = Catalog([record(), record('0001000141424345', is_demo=True), record(title_id=None)])
        self.assertEqual(catalog.query(demos='only')['total'], 1)
        self.assertEqual(catalog.query(demos='exclude')['total'], 1)
        self.assertEqual(catalog.query(category='Virtual Console')['total'], 0)
        self.assertEqual(catalog.query()['unresolved_japan_listings'], 1)

    def test_conflicting_metadata_is_not_silently_collapsed(self):
        catalog = Catalog([record(), record(version=1, is_demo=True)])
        self.assertEqual(catalog.query()['total'], 0)
        self.assertEqual(len(catalog.query()['conflicting_title_ids']), 1)

    def test_query_bounds_and_missing_provenance(self):
        catalog = Catalog([record()])
        for options in ({'limit': 0}, {'limit': 51}, {'offset': True}, {'title_ids': ['1234']}, {'demos': 'unknown'}):
            with self.assertRaises(ValueError):
                catalog.query(**options)
        with self.assertRaises(ValueError):
            Catalog([record(title_id_evidence=None)])

    def test_returned_items_do_not_mutate_index_and_duplicate_sources_reject(self):
        catalog = Catalog([record()])
        item = catalog.query()['items'][0]
        item['listings'][0]['evidence']['row'] = 999
        self.assertEqual(catalog.query()['items'][0]['listings'][0]['evidence']['row'], 2)
        with self.assertRaises(ValueError):
            Catalog([record(), record('0001000141424345', catalog_id='00010001414243440')])
