from pathlib import Path
import unittest

from tools.verify_demae_postal_header import verify


class PostalHeaderTests(unittest.TestCase):
    def test_fingerprint_required(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            verify(bytes(1024))

    def test_original_gate_with_synthetic_headers(self):
        path = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not path.is_file():
            self.skipTest('Private helper executable unavailable')
        report = verify(path.read_bytes())
        self.assertEqual(report['synthetic_cases'], 266)
        self.assertFalse(report['native_gate_mocked'])
        self.assertFalse(report['offset_bounds_checked_by_native_gate'])
        self.assertFalse(report['download_transport_verified'])


if __name__ == '__main__':
    unittest.main()
