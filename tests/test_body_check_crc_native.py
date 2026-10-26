"""CRC leaf verification and metadata-only CLI failures; no health/save fixtures."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.inspect_body_check_dataset import main
from tools.verify_body_check_header_crc import synthetic_crc_cases, verify_header_crc


class BodyCheckInspectionPrivacyTests(unittest.TestCase):
    def test_oserror_path_and_contents_are_not_printed(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-health-path-marker')), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertEqual(main(['private-health-path-marker.dat']), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(errors.getvalue(), 'Cannot inspect dataset: input unavailable or unsupported plaintext header\n')
        self.assertNotIn('private-health', errors.getvalue())

    def test_corrupt_present_input_remains_a_failure_with_fixed_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private-health-path-marker.dat'
            path.write_bytes(b'private-health-payload')
            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(main([str(path)]), 1)
            self.assertEqual(output.getvalue(), '')
            self.assertNotIn('private-health', errors.getvalue())
            self.assertEqual(path.read_bytes(), b'private-health-payload')

    def test_wrong_native_source_is_rejected_without_echo_or_engine_requirement(self):
        with self.assertRaisesRegex(ValueError, '^Body Check Japanese v256 executable fingerprint mismatch$'):
            verify_header_crc(b'private-original-source-marker', synthetic_crc_cases())


class BodyCheckNativeCRCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependency unavailable')
        path = Path('private/body_check/v256/0001-0000000e.dol')
        if not path.is_file():
            raise unittest.SkipTest('Private original HFNJ v256 decoded executable unavailable')
        cls.source = path.read_bytes()

    def test_67_original_crc_comparisons_match_independent_header_checksum(self):
        result = verify_header_crc(self.source, synthetic_crc_cases())
        self.assertEqual(result['synthetic_crc_cases'], 67)
        self.assertTrue(result['native_crc_matches_zlib'])
        self.assertTrue(result['bounded_input_and_original_table_reads'])
        self.assertTrue(result['input_guards_verified'])
        self.assertFalse(result['native_crc_stubbed'])
        self.assertFalse(result['native_memory_writes_attempted'])
        self.assertFalse(result['native_dataset_loader_executed'])
        self.assertFalse(result['dataset_records_or_authentication_verified'])

    def test_harness_rejects_non_twelve_byte_and_unbounded_case_sets(self):
        for cases in ([], [bytes(11)], [bytes(13)], ['private-marker'], [bytes(12)] * 257):
            with self.subTest(count=len(cases)), self.assertRaises(ValueError) as caught:
                verify_header_crc(self.source, cases)
            self.assertNotIn('private-marker', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
