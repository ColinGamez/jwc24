import unittest
from jwc24.demae_area_registry import AreaRegistry, area_identity, assign_area_codes


class RegistryTests(unittest.TestCase):
    def test_reverse_lookup_and_invalid_source_identity(self):
        identity = area_identity('10201', '3700001', 'A')
        snapshot = AreaRegistry({identity: '10000000000'})
        self.assertEqual(snapshot.resolve('10000000000'),
                         {'municipality': '10201', 'postal': '3700001', 'town': 'A'})
        self.assertIsNone(snapshot.resolve('99999999999'))
        for identity in ('not JSON', '["a","b"]', '["a","b",1]'):
            with self.assertRaises(ValueError):
                AreaRegistry({identity: '10000000000'})

    def test_stability_ambiguity_and_retired_ids(self):
        a = area_identity('10201', '3700001', 'A')
        b = area_identity('10201', '3700001', 'B')
        original = assign_area_codes({}, [b, a, a])
        self.assertNotEqual(original[a], original[b])
        updated = assign_area_codes(original, [a, 'new'])
        self.assertEqual(updated[a], original[a])
        self.assertEqual(updated[b], original[b])
        self.assertGreater(int(updated['new']), max(map(int, original.values())))
        self.assertEqual(original, assign_area_codes({}, [a, b]))

    def test_rejects_invalid_registry_and_exhaustion(self):
        for previous in ([], {'a': '1'}, {'a': 'T-abc'},
                         {'a': '10000000000', 'b': '10000000000'}):
            with self.assertRaises(ValueError):
                assign_area_codes(previous, ['new'])
        with self.assertRaises(ValueError):
            assign_area_codes({'old': '99999999999'}, ['new'])
