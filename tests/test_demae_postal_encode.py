import unittest

from jwc24.demae import PostalFormatError, PostalRecord, inspect_postal_records
from jwc24.demae_postal_encode import encode_processed_records, postal_bucket


class PostalEncodingTests(unittest.TestCase):
    def test_roundtrip_and_native_bucket_boundaries(self):
        rows = (PostalRecord(3700001, ('群馬県', '高崎市', '町')),)
        self.assertEqual(inspect_postal_records(encode_processed_records(rows, bucket=370)), rows)
        self.assertEqual([postal_bucket(n) for n in (0, 99999, 100000, 9999999)],
                         [0, 0, 10, 990])

    def test_rejects_ambiguous_or_cross_bucket_records(self):
        row = PostalRecord(3700001, ('a', 'b', 'c'))
        for rows, bucket in [((row, row), 370), ((row,), 360)]:
            with self.assertRaises(PostalFormatError):
                encode_processed_records(rows, bucket=bucket)

    def test_utf16_capacity_and_malformed_unicode(self):
        for text in ('a' * 32, '😀' * 16, '\ud800', 'a\0b'):
            with self.assertRaises(PostalFormatError):
                encode_processed_records((PostalRecord(1, (text, '', '')),))
        encode_processed_records((PostalRecord(1, ('😀' * 15 + 'a', '', '')),))

    def test_rejects_oversized_bucket(self):
        rows = (PostalRecord(n, ('a' * 31, 'b' * 31, 'c' * 63)) for n in range(2000))
        with self.assertRaises(PostalFormatError):
            encode_processed_records(rows, bucket=0)


if __name__ == '__main__':
    unittest.main()
