import unittest

from jwc24.demae_area_code import normalize_area_code


class AreaCodeTests(unittest.TestCase):
    def test_native_normalization_and_reader_boundary(self):
        self.assertEqual(normalize_area_code('123'), '00000000123')
        self.assertEqual(normalize_area_code('00000000123'), '00000000123')
        self.assertEqual(normalize_area_code('0'), '00000000000')
        self.assertEqual(normalize_area_code('99999999999'), '99999999999')
        for value in ('T-123', '100000000000', '-1', '+1', '１２３', '1.0', '', 123, ' 1'):
            with self.assertRaises(ValueError):
                normalize_area_code(value)
