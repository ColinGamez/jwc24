import unittest
from jwc24.restaurant_catalog import parse_osm_restaurants


class RestaurantCatalogTests(unittest.TestCase):
    def test_locations_do_not_become_delivery_offers(self):
        data = {'elements': [{'type': 'way', 'id': 7, 'center': {'lat': 36.3, 'lon': 139},
                             'tags': {'amenity': 'restaurant', 'name': 'Test', 'name:ja': '店舗', 'delivery': 'yes'}}]}
        row = parse_osm_restaurants(data)[0]
        self.assertEqual(row['name'], '店舗')
        self.assertEqual(row['id'], 'osm:way:7')
        self.assertIsNone(row['delivery_available'])
        self.assertIsNone(row['menu_items'])
        self.assertFalse(row['ordering_supported'])

    def test_duplicates_invalid_coordinates_and_missing_names(self):
        good = {'type': 'node', 'id': 1, 'lat': 36, 'lon': 139,
                'tags': {'amenity': 'cafe', 'name': 'Cafe'}}
        bad = dict(good, id=2, lat=float('nan'))
        unnamed = dict(good, id=3, tags={'amenity': 'cafe'})
        self.assertEqual(len(parse_osm_restaurants({'elements': [good, good, bad, unnamed]})), 1)

    def test_partial_overpass_result_is_not_published_as_complete(self):
        for data in ({'remark': 'timeout', 'elements': []}, {}, {'elements': None}):
            with self.assertRaises(ValueError):
                parse_osm_restaurants(data)
