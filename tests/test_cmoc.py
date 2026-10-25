import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from jwc24.cmoc import CMOCFormatError, CMOCUnsupportedFormat, inspect_response
from tools.inspect_cmoc_response import main


def header():
    # Synthetic framing fixture; not an authentic or native-accepted response.
    return struct.pack('>HBBII', 0x4644, 1, 2, 0x12345678, 9) + bytes(20)


def record(tag, payload=b''):
    return struct.pack('>HHI', tag, 8 + len(payload), 0) + payload


class CMOCInspectionTests(unittest.TestCase):
    def test_native_size_includes_prefix_and_cursor_advances_exactly(self):
        result = inspect_response(header() + record(0x4142, b'12345') + record(0x4344))
        self.assertEqual([(item.offset, item.size) for item in result.records], [(32, 13), (45, 8)])
        self.assertEqual(result.header.word_4, 0x12345678)
        self.assertEqual(result.byte_length, 53)
        self.assertEqual(inspect_response(header()).records, ())

    def test_short_header_prefix_and_oversized_record_are_rejected(self):
        for data in (header()[:31], header() + bytes(7),
                     header() + struct.pack('>HHI', 1, 9, 0),
                     header() + struct.pack('>HHI', 1, 0xffff, 0)):
            with self.subTest(length=len(data)), self.assertRaises(CMOCFormatError):
                inspect_response(data)

    def test_no_progress_and_extended_records_cannot_loop_or_read_outside_buffer(self):
        with self.assertRaises(CMOCUnsupportedFormat):
            inspect_response(header() + bytes(8))
        for size in range(1, 8):
            with self.subTest(size=size), self.assertRaises(CMOCFormatError):
                inspect_response(header() + struct.pack('>HHI', 1, size, 0))

    def test_count_and_byte_limits_are_enforced(self):
        data = header() + record(1) + record(2)
        with self.assertRaises(CMOCFormatError):
            inspect_response(data, max_records=1)
        with self.assertRaises(CMOCFormatError):
            inspect_response(data, max_bytes=47)
        self.assertEqual(len(inspect_response(data, max_records=2, max_bytes=48).records), 2)

    def test_cli_metadata_omits_opaque_identifiers_and_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.bin'
            path.write_bytes(header() + record(1, b'private-mii-payload'))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path)]), 0)
            metadata = json.loads(output.getvalue())
            self.assertEqual(metadata['record_count'], 1)
            self.assertNotIn('private-mii-payload', output.getvalue())
            self.assertNotIn('12345678', output.getvalue())
            path.write_bytes(b'bad')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(path)]), 1)


if __name__ == '__main__':
    unittest.main()
