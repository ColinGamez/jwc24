import unittest
from jwc24.demae_catalog_categories import classify_restaurants


class CatalogCategoryTests(unittest.TestCase):
    def test_unknown_genres_preserved_without_other_fallback(self):
        result = classify_restaurants([{'id': 'a', 'genre': '和食'},
                                       {'id': 'b', 'genre': 'unrecognized source genre'}, {'id': 'c'}])
        self.assertEqual(result['categories']['04']['restaurant_ids'], ['a'])
        self.assertEqual(result['categories']['11']['restaurant_ids'], [])
        self.assertEqual(result['unmapped_restaurant_ids'], ['b', 'c'])
        self.assertFalse(result['ordering_supported'])
        with self.assertRaises(ValueError):
            classify_restaurants([{'id': 'a'}, {'id': 'a'}])
