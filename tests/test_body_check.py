import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from jwc24.body_check import BodyCheckFormatError, MAX_DATASET_BYTES, inspect_dataset
from tools.inspect_body_check_dataset import main


def synthetic_header():
    # Framing fixture only; no health records or authentic native dataset.
    covered = b'abcdefghijkl'
    return struct.pack('>I', zlib.crc32(covered)) + covered


class BodyCheckInspectionTests(unittest.TestCase):
    def test_header_crc_and_maximum_length(self):
        data = synthetic_header()
        self.assertEqual(inspect_dataset(data).byte_length, 16)
        maximum = data + bytes(MAX_DATASET_BYTES - len(data))
        self.assertEqual(inspect_dataset(maximum).byte_length, MAX_DATASET_BYTES)

    def test_checksum_and_each_covered_byte_corruption_are_rejected(self):
        for offset in range(16):
            data = bytearray(synthetic_header())
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(BodyCheckFormatError):
                inspect_dataset(bytes(data))

    def test_payload_changes_are_not_claimed_to_be_verified(self):
        first = inspect_dataset(synthetic_header() + b'opaque-one')
        second = inspect_dataset(synthetic_header() + b'opaque-two')
        self.assertEqual(first.metadata(), second.metadata())
        for field in ('payload_integrity_checked', 'record_semantics_checked',
                      'rsa_authenticity_checked'):
            self.assertIs(first.metadata()[field], False)

    def test_every_truncated_header_and_oversize_are_rejected(self):
        for length in range(16):
            with self.subTest(length=length), self.assertRaises(BodyCheckFormatError):
                inspect_dataset(synthetic_header()[:length])
        with self.assertRaises(BodyCheckFormatError):
            inspect_dataset(synthetic_header() + bytes(MAX_DATASET_BYTES - 15))

    def test_cli_exposes_metadata_only_and_handles_bad_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.dat'
            path.write_bytes(synthetic_header() + b'private-health-payload')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path)]), 0)
            metadata = json.loads(output.getvalue())
            self.assertEqual(metadata['checksum_covered_length'], 12)
            self.assertNotIn('private-health-payload', output.getvalue())
            self.assertNotIn('abcdefghijkl', output.getvalue())
            path.write_bytes(b'bad')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(path)]), 1)

    def test_cli_read_is_bounded_even_for_growing_or_huge_inputs(self):
        stream = io.BytesIO(synthetic_header() + bytes(MAX_DATASET_BYTES * 2))
        with patch.object(Path, 'open', return_value=stream), \
                patch.object(stream, 'read', wraps=stream.read) as read, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['synthetic.dat']), 1)
            read.assert_called_once_with(MAX_DATASET_BYTES + 1)


if __name__ == '__main__':
    unittest.main()
