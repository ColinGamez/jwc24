"""Independent complete streams and actual original incremental state checks."""
import importlib.util
from pathlib import Path
import unittest

from jwc24.cmoc_compression import inspect_compression
from jwc24.forecast import encode_lz10, decode_lz10
from jwc24.lz11 import encode_lz11, decode_lz11


def streams():
    examples = []
    for encoder, decoder in ((encode_lz10, decode_lz10), (encode_lz11, decode_lz11)):
        for plain in (bytes(range(64)), b'A' * 32, b'ABC' * 31, bytes(range(8)) * 24):
            packed = encoder(plain)
            assert decoder(packed) == plain
            examples.append((packed, plain))
    # Explicit distance-one overlapping references in every LZ11 length form.
    examples.extend((
        (b'\x10\x06\0\0\x40A\x20\0', b'A' * 6),
        (b'\x11\x07\0\0\x40A\x50\0', b'A' * 7),
        (b'\x11\x12\0\0\x40A\0\0\0', b'A' * 18),
        (b'\x11\x12\x01\0\x40A\x10\0\0\0', b'A' * 274),
        (b'\x10\0\0\0\x03\0\0\0\0ABC', b'ABC'),
        (b'\x11\0\0\0\x03\0\0\0\0ABC', b'ABC')))
    return tuple(examples)


def inspect(chunks, **changes):
    return inspect_compression(chunks=chunks, enabled=True, output_limit=0,
                               output_capacity=4096, **changes)


class CompressionTests(unittest.TestCase):
    def test_complete_lz10_lz11_literal_and_all_reference_length_forms(self):
        for packed, plain in streams():
            with self.subTest(size=len(packed)):
                result = inspect((packed,))
                self.assertEqual(result.output, plain)
                self.assertEqual(result.steps[-1].sdk_return, 0)
                self.assertEqual(result.steps[-1].return_value, len(plain))

    def test_sdk_can_resume_negative_partial_header_and_split_reference_state(self):
        for packed, plain in streams():
            for cut in range(1, len(packed)):
                result = inspect((packed[:cut], packed[cut:]), application=False)
                self.assertEqual(result.output, plain)
                self.assertEqual(result.steps[-1].remaining, 0)
        result = inspect((b'\x10\x03', b'\0\0\0ABC'), application=False)
        self.assertEqual(result.steps[0].sdk_return, -1)
        self.assertEqual(result.steps[0].header_remaining, 6)
        self.assertEqual(result.steps[0].remaining, 3)
        self.assertEqual(result.output, b'ABC')

    def test_application_requires_full_initial_header_backing(self):
        for chunks in ((b'\x10\x03', b'\0\0\0ABC'), (b'\x10\0\0\0', b'\x03\0\0\0\0ABC'), (b'',)):
            with self.assertRaises(ValueError):
                inspect(chunks)

    def test_output_limit_count_mismatch_and_late_error_after_writes(self):
        packed = b'\x10\x03\0\0\0ABC'
        capped = inspect_compression(chunks=(packed,), enabled=True, output_limit=2, output_capacity=2)
        self.assertEqual(capped.output, b'AB')
        self.assertEqual((capped.steps[0].return_value, len(capped.steps[0].written)), (3, 2))
        rejected = inspect((packed + bytes(33), b'ignored after completion'))
        self.assertEqual(rejected.output, b'ABC')
        self.assertEqual((rejected.steps[0].return_value, rejected.steps[0].sdk_return), (0, -3))
        self.assertEqual(rejected.steps[0].cached_remaining, 3)
        self.assertEqual(rejected.steps[1].sdk_return, None)
        self.assertEqual(rejected.steps[1].written, b'')
        for padding in (0, 1, 16, 32):
            self.assertEqual(inspect((packed + bytes(padding),)).steps[0].return_value, 3)

    def test_truncated_literals_and_overshooting_reference_keep_written_bytes_and_state(self):
        partial = inspect((b'\x10\x03\0\0\0AB',))
        self.assertEqual(partial.output, b'AB')
        self.assertEqual((partial.steps[0].return_value, partial.steps[0].remaining), (2, 1))
        bad = inspect((b'\x10\x04\0\0\x40A\x20\0',))
        self.assertEqual(bad.output, b'A')
        self.assertEqual((bad.steps[0].sdk_return, bad.steps[0].return_value), (-4, 0))
        self.assertEqual((bad.steps[0].remaining, bad.steps[0].cached_remaining), (3, 4))

    def test_malformed_header_resume_keeps_raw_application_underflow_separate_from_sdk(self):
        chunks = (b'\x20\x03\0\0', b'\x10\x05\0\0', b'\0ABCDE')
        result = inspect(chunks)
        self.assertEqual([s.return_value for s in result.steps], [0, 0xFFFFFFFE, 5])
        self.assertEqual([s.sdk_return for s in result.steps], [-1, 5, 0])
        self.assertEqual([s.cached_remaining for s in result.steps], [3, 5, 0])
        self.assertEqual([len(s.written) for s in result.steps], [0, 0, 5])
        self.assertEqual(result.output, b'ABCDE')

    def test_disabled_copy_and_privacy_no_implicit_compression_detection(self):
        result = inspect_compression(chunks=(b'private-marker', b'!'), enabled=False,
                                     output_limit=0, output_capacity=32)
        self.assertEqual(result.output, b'private-marker!')
        self.assertEqual([s.return_value for s in result.steps], [14, 1])
        self.assertTrue(all(s.sdk_return is None for s in result.steps))
        self.assertNotIn('private-marker', repr(result))
        self.assertNotIn('private-marker', str(result.metadata()))
        self.assertFalse(result.metadata()['resource_envelope_verified'])

    def test_explicit_bounds_invalid_tokens_and_history_reject_without_padding(self):
        good = dict(chunks=(b'\x10\x03\0\0\0ABC',), enabled=True,
                    output_limit=0, output_capacity=4096)
        for change in (dict(chunks=[]), dict(chunks=(b'',) * 65), dict(chunks=(bytes(4097),)),
                       dict(enabled=1), dict(output_limit=True), dict(output_limit=-1),
                       dict(output_capacity=0), dict(application=1),
                       dict(enabled=False, application=False), dict(output_capacity=2),
                       dict(chunks=(b'\x10\x03\0\0\x80\0\0',))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                inspect_compression(**(good | change))
        for kind in (0x20, 0x12):
            result = inspect((bytes((kind, 3, 0, 0)),))
            self.assertEqual(result.steps[0].sdk_return, -1)
            self.assertEqual(result.output, b'')


class CompressionNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('private/cmoc/v512/0001-0000000c.app')
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese CMOC v512 executable unavailable')
        if any(importlib.util.find_spec(name) is None for name in ('unicorn', 'capstone')):
            raise unittest.SkipTest('Optional native verification dependencies unavailable')
        cls.source = path.read_bytes()

    def test_each_input_cut_including_partial_headers_and_reference_tokens(self):
        from tools.verify_cmoc_compression import verify_compression
        for packed, _ in streams():
            header = 8 if packed[1:4] == bytes(3) else 4
            for application in (False, True):
                first = header if application else 1
                for cut in range(first, len(packed) + 1):
                    with self.subTest(application=application, cut=cut, size=len(packed)):
                        result = verify_compression(self.source, chunks=(packed[:cut], packed[cut:]),
                            enabled=True, output_limit=0, output_capacity=4096, application=application)
                        self.assertTrue(result['input_and_stack_guards_verified'])
                        self.assertFalse(result['decoder_stubs_used'])

    def test_original_malformed_truncated_limits_padding_and_disabled_paths(self):
        from tools.verify_cmoc_compression import verify_compression
        base = dict(enabled=True, output_limit=0, output_capacity=4096)
        packed = b'\x10\x03\0\0\0ABC'
        cases = [dict(chunks=(packed + bytes(n),)) for n in (0, 1, 16, 32, 33)]
        cases += [dict(chunks=(packed,), output_limit=2, output_capacity=2),
                  dict(chunks=(b'\x10\x04\0\0\x40A\x20\0',)),
                  dict(chunks=(b'\x10\x04\0\0\x40A\x20\0',), output_limit=3),
                  dict(chunks=(packed[:7],)), dict(chunks=(packed[:4], b'', packed[4:], b''))]
        # Keep explicit invalid kind cases separate from the ordinary fixtures.
        cases.extend(dict(chunks=(bytes((kind, 3, 0, 0)),)) for kind in (0x20, 0x12))
        cases.extend((dict(chunks=(b'raw bytes', b'continue'), enabled=False),
                      dict(chunks=(packed + bytes(33), b'ignored')), dict(chunks=())))
        for change in cases:
            with self.subTest(change=change):
                verify_compression(self.source, **(base | change))

    def test_actual_backing_guards_prevent_short_headers_bad_history_and_output_overflow(self):
        from tools.verify_cmoc_compression import _execute
        base = dict(enabled=True, limit=0, capacity=4096, application=True)
        for change in (dict(chunks=(b'\x10\x03',)), dict(chunks=(b'\x10\0\0\0',)),
                       dict(chunks=(b'\x10\x03\0\0\x80\0\0',)),
                       dict(chunks=(b'\x10\x03\0\0\0ABC',), capacity=2)):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'Unexpected (read|write)'):
                _execute(self.source, **(base | change))

    def test_actual_malformed_header_resume_unsigned_application_count_and_signed_sdk(self):
        from tools.verify_cmoc_compression import verify_compression
        chunks = (b'\x20\x03\0\0', b'\x10\x05\0\0', b'\0ABCDE')
        for application, supplied in ((True, chunks[:2]), (True, chunks), (False, chunks)):
            result = verify_compression(self.source, chunks=supplied, enabled=True,
                output_limit=0, output_capacity=4096, application=application)
            if application:
                self.assertEqual(result['steps'][1]['return_value'], 0xFFFFFFFE)
            self.assertEqual(result['steps'][1]['sdk_return'], 5)
            self.assertEqual(result['steps'][1]['written_size'], 0)


if __name__ == '__main__':
    unittest.main()
