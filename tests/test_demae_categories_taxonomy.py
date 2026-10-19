import unittest
from jwc24.demae_categories import native_categories, exact_genre_mapping


class TaxonomyTests(unittest.TestCase):
    def test_native_identity_and_no_guessed_fallback(self):
        rows = native_categories()
        self.assertEqual([row['code'] for row in rows], [f'{n:02d}' for n in range(1, 12)])
        self.assertEqual(exact_genre_mapping('和食'), '04')
        self.assertEqual(exact_genre_mapping('中華'), '05')
        self.assertEqual(exact_genre_mapping('居酒屋'), '11')
        self.assertEqual(exact_genre_mapping('イタリアン・フレンチ'), '06')
        self.assertEqual(exact_genre_mapping('カフェ・スイーツ'), '10')
        self.assertIsNone(exact_genre_mapping('unrecognized source genre'))
        self.assertIsNone(exact_genre_mapping('G001'))
        rows[0]['name'] = 'changed'
        self.assertEqual(native_categories()[0]['name'], 'ピザ')
