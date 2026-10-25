from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from jwc24.forecast import encode_lz10
from jwc24.lz11 import encode_lz11
from jwc24.nintendo_csdata import (
    CSDataFormatError, MAX_CSDATA_BYTES, MIN_CSDATA_BYTES,
    decompress_csdata, inspect_csdata,
)
from tools.inspect_nintendo_csdata import main


def synthetic_csdata(*, size=MIN_CSDATA_BYTES, reference=b'synthetic.invalid',
                     version=6, status=0):
    raw = bytearray(size)
    raw[2] = version
    struct.pack_into('>I', raw, 4, size)
    raw[0x28] = status
    raw[0x35:0x35 + len(reference)] = reference
    struct.pack_into('>I', raw, 8, zlib.crc32(raw))
    return bytes(raw)


def with_crc(raw):
    raw = bytearray(raw)
    raw[8:12] = bytes(4)
    struct.pack_into('>I', raw, 8, zlib.crc32(raw))
    return bytes(raw)


class NintendoCSDataTests(unittest.TestCase):
    def test_accepts_minimum_maximum_and_opaque_reference_without_claiming_records(self):
        for size in (MIN_CSDATA_BYTES, MAX_CSDATA_BYTES):
            with self.subTest(size=size):
                result = inspect_csdata(synthetic_csdata(size=size, reference=b'private-marker'))
                self.assertEqual(result.byte_length, size)
                self.assertEqual(result.reference, b'private-marker')
                self.assertNotIn('private-marker', repr(result))
                self.assertNotIn('private-marker', repr(result.metadata()))
                for name in ('record_semantics_checked', 'freshness_checked',
                             'wc24_authenticity_checked', 'native_download_or_ui_verified'):
                    self.assertFalse(result.metadata()[name])

    def test_crc_covers_header_and_opaque_tail_and_does_not_mutate_input(self):
        original = synthetic_csdata(size=400)
        for offset in (0, 3, 8, 0x35, 399):
            changed = bytearray(original)
            changed[offset] ^= 1
            snapshot = bytes(changed)
            with self.subTest(offset=offset), self.assertRaisesRegex(CSDataFormatError, 'CRC'):
                inspect_csdata(snapshot)
            self.assertEqual(bytes(changed), snapshot)

    def test_rejects_size_mismatch_and_every_short_input(self):
        raw = synthetic_csdata()
        for size in range(MIN_CSDATA_BYTES):
            with self.subTest(size=size), self.assertRaises(CSDataFormatError):
                inspect_csdata(raw[:size])
        with self.assertRaises(CSDataFormatError):
            inspect_csdata(raw + b'\0')
        with self.assertRaises(CSDataFormatError):
            inspect_csdata(bytes(MAX_CSDATA_BYTES + 1))

    def test_unsupported_format_status_and_unterminated_reference_are_explicit(self):
        for args in ({'version': 5}, {'version': 7}, {'status': 1}, {'reference': b'X' * 256}):
            with self.subTest(args=args), self.assertRaises(CSDataFormatError):
                inspect_csdata(synthetic_csdata(**args))

    def test_reference_is_bytes_not_assumed_utf8_or_authorized_url(self):
        result = inspect_csdata(synthetic_csdata(reference=b'\xffopaque'))
        self.assertEqual(result.reference, b'\xffopaque')
        self.assertFalse(result.metadata()['reference_url_or_host_authorized'])

    def test_lz10_lz11_and_extended_size_headers_match(self):
        raw = synthetic_csdata(size=800)
        for encode, kind in ((encode_lz10, 'lz10'), (encode_lz11, 'lz11')):
            encoded = encode(raw)
            extended = encoded[:1] + bytes(3) + len(raw).to_bytes(4, 'little') + encoded[4:]
            for payload in (encoded, extended):
                with self.subTest(kind=kind, extended=payload is extended):
                    self.assertEqual(decompress_csdata(payload), (raw, kind))
                    self.assertEqual(inspect_csdata(payload).byte_length, len(raw))

    def test_output_budget_is_checked_before_compressed_decoder(self):
        for kind in (0x10, 0x11):
            for expected in (0, MIN_CSDATA_BYTES - 1, MAX_CSDATA_BYTES + 1, 0xFFFFFFFF):
                payload = bytes([kind]) + bytes(3) + expected.to_bytes(4, 'little')
                with self.subTest(kind=kind, expected=expected), \
                     patch('jwc24.nintendo_csdata.decode_lz10', side_effect=AssertionError('decode before bounds')), \
                     patch('jwc24.nintendo_csdata.decode_lz11', side_effect=AssertionError('decode before bounds')):
                    with self.assertRaises(CSDataFormatError):
                        inspect_csdata(payload)

    def test_bad_type_truncation_and_negative_distance_are_rejected(self):
        for payload in (b'\x12\x36\x01\x00', b'\x11', b'\x10\x36\x01\x00',
                        b'\x11\x36\x01\x00\x80\x20\x00'):
            with self.subTest(payload=payload), self.assertRaises(CSDataFormatError):
                inspect_csdata(payload)

    def test_cli_is_bounded_read_only_and_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private-marker.dat'
            data = synthetic_csdata(reference=b'private-reference-marker')
            path.write_bytes(data)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())['reference_byte_length'], 24)
            self.assertNotIn('private', output.getvalue())
            self.assertEqual(path.read_bytes(), data)
        stream = io.BytesIO(bytes(MAX_CSDATA_BYTES * 3))
        with patch.object(Path, 'open', return_value=stream), \
             patch.object(stream, 'read', wraps=stream.read) as read, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['synthetic.dat']), 1)
            read.assert_called_once_with(MAX_CSDATA_BYTES * 2 + 9)


class NintendoCSDataNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import unicorn
        except ImportError:
            raise unittest.SkipTest('Unicorn is unavailable')
        source = Path('private/nintendo/v1792/0001-0000003e.app')
        if not source.is_file():
            raise unittest.SkipTest('Private original HATJ executable is unavailable')
        cls.source = source.read_bytes()

    def verify(self, payload, **kwargs):
        from tools.verify_nintendo_csdata import verify_csdata_native
        return verify_csdata_native(self.source, payload, **kwargs)

    def test_real_crc_version_and_reference_prefix_reach_construction_boundary(self):
        result = self.verify(synthetic_csdata())
        self.assertTrue(result['reached_reference_construction_boundary'])
        self.assertFalse(result['native_crc_mocked'])
        self.assertTrue(result['guard_checks_passed'])
        self.assertFalse(result['url_construction_or_full_load_verified'])

    def test_crc_version_and_reference_failures_match_supported_subset(self):
        corrupted = bytearray(synthetic_csdata()); corrupted[-1] ^= 1
        cases = (bytes(corrupted), synthetic_csdata(version=5),
                 synthetic_csdata(reference=b'X' * 256))
        for payload in cases:
            with self.subTest(case=cases.index(payload)):
                result = self.verify(payload)
                self.assertEqual(result['native_header_prefix_result'], 0)
                self.assertFalse(result['reached_reference_construction_boundary'])

    def test_native_early_acceptance_is_not_normal_data_acceptance(self):
        for payload in (synthetic_csdata(version=7), synthetic_csdata(status=1)):
            result = self.verify(payload)
            self.assertEqual(result['native_header_prefix_result'], 1)
            self.assertFalse(result['reached_reference_construction_boundary'])
            with self.assertRaises(CSDataFormatError):
                inspect_csdata(payload)

    def test_configured_reference_limit_is_separate_from_termination_capacity(self):
        result = self.verify(synthetic_csdata(reference=b'1234'), configured_reference_limit=3)
        self.assertEqual(result['native_header_prefix_result'], 0)
        self.assertTrue(self.verify(synthetic_csdata(reference=b'1234'), configured_reference_limit=4)
                        ['reached_reference_construction_boundary'])

    def test_native_declared_size_gate_and_upper_boundary(self):
        payload = bytearray(synthetic_csdata())
        struct.pack_into('>I', payload, 4, 0x135)
        result = self.verify(bytes(payload))
        self.assertEqual(result['native_header_prefix_result'], 0)
        self.assertTrue(self.verify(synthetic_csdata(size=MAX_CSDATA_BYTES))
                        ['reached_reference_construction_boundary'])

    def test_original_lz10_lz11_decompression_matches_independent_decoder(self):
        raw = synthetic_csdata(size=800)
        for encoder in (encode_lz10, encode_lz11):
            encoded = encoder(raw)
            for payload in (encoded, encoded[:1] + bytes(3) + len(raw).to_bytes(4, 'little') + encoded[4:]):
                result = self.verify(payload, decompress=True)
                self.assertTrue(result['native_decompression_matches_independent_decoder'])
                self.assertEqual(result['decompressed_bytes'], len(raw))
                self.assertTrue(result['guard_checks_passed'])


if __name__ == '__main__':
    unittest.main()
