from pathlib import Path
import struct
import unittest

from jwc24.demae import PostalFormatError, lookup_processed_postal
from tools.verify_demae_postal_lookup import verify


def row(code, name='test', strings=None):
    values = strings if strings is not None else (name, '', '')
    return struct.pack('>I', code) + b''.join(
        value.encode('utf-16-be') + b'\0\0' for value in values)


class PostalLookupTests(unittest.TestCase):
    def test_exact_wins_in_either_order(self):
        for data in (row(3770800)+row(3770813), row(3770813)+row(3770800)):
            self.assertEqual(lookup_processed_postal(data, 3770813).kind, 'exact')

    def test_first_exact_and_last_fallback(self):
        data = row(3770800, 'first')+row(3770800, 'last')
        self.assertEqual(lookup_processed_postal(data, 3770813).record.strings[0], 'last')
        data = row(3770813, 'first')+row(3770813, 'last')
        self.assertEqual(lookup_processed_postal(data, 3770813).record.strings[0], 'first')

    def test_zero_bucket_and_absent(self):
        self.assertEqual(lookup_processed_postal(row(0), 99).kind, 'alternative')
        self.assertEqual(lookup_processed_postal(row(0), 0).kind, 'exact')
        for data in (b'', row(1234567)):
            self.assertIsNone(lookup_processed_postal(data, 3770813).record)

    def test_utf16_capacity_counts_surrogate_pairs(self):
        values = ('a'*31, '\U0001f363'*15+'a', '町'*63)
        self.assertEqual(lookup_processed_postal(row(1, strings=values), 1).record.strings, values)
        for values in [('a'*32, '', ''), ('', '\U0001f363'*16, ''), ('', '', '町'*64)]:
            with self.assertRaises(PostalFormatError):
                lookup_processed_postal(row(1, strings=values), 1)

    def test_validates_tail_query_and_download_bound(self):
        for data in (row(1)+b'!', b'\0'*0x40002):
            with self.assertRaises(PostalFormatError):
                lookup_processed_postal(data, 1)
        for query in (True, -1, 10000000, '3770813', None):
            with self.assertRaises(PostalFormatError):
                lookup_processed_postal(b'', query)

    def test_native_consumer_matches_synthetic_cases(self):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        source = path.read_bytes()
        cases = [(b'', 1), (row(2), 1), (row(0), 99), (row(0), 0),
                 (row(3770800)+row(3770813), 3770813),
                 (row(3770813)+row(3770800), 3770813),
                 (row(3770800, 'first')+row(3770800, 'last'), 3770813),
                 (row(3770813, 'first')+row(3770813, 'last'), 3770813),
                 (row(1, strings=('群馬県', '\U0001f363'*15+'a', '町'*63)), 1)]
        for data, query in cases:
            with self.subTest(query=query, length=len(data)):
                report = verify(source, data, query)
                self.assertFalse(report['native_lookup_mocked'])


if __name__ == '__main__':
    unittest.main()
