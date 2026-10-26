import contextlib
from dataclasses import FrozenInstanceError
import hashlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

from jwc24.wii_speak_version import (ExperimentalVersionReplay, WiiSpeakVersionError,
                                    inspect_version_capture, inspect_version_data)
from tools.inspect_wii_speak_version import main
from tools.verify_wii_speak_version import verify_version_reader


def capture():
    # Synthetic transport fixture, never a captured original service response.
    result = bytearray(328)
    result[:8] = b'Wc24\0\0\0\1'
    result[12] = 1
    result[64:320] = bytes([0xA5]) * 256
    result[320:] = b'opaque!!'
    return bytes(result)


class WiiSpeakVersionTests(unittest.TestCase):
    def test_explicit_decoded_words_and_uint32_limit(self):
        for version in (0, 1, 2, 3, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
            for limit in (0, 1, 0x3FFFFF, 0x400000, 0xFFFFFFFF):
                metadata = inspect_version_data(struct.pack('>II', version, limit)).metadata()
                self.assertEqual(metadata['newer_than_native_client_2'], version > 2)
                self.assertEqual(metadata['size_limit_bytes_native_u32'], (limit << 10) & 0xFFFFFFFF)
                self.assertEqual(metadata['size_limit_overflows_u32'], limit > 0x3FFFFF)
                self.assertFalse(metadata['native_payload_schema_validated'])

    def test_local_exact_length_and_type_policy(self):
        for value in (b'', bytes(7), bytes(9), bytearray(8), None):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(WiiSpeakVersionError):
                    inspect_version_data(value)
        for value in (b'', bytes(327), bytes(329), bytearray(capture())):
            with self.assertRaises(WiiSpeakVersionError):
                inspect_version_capture(value)

    def test_capture_shape_does_not_claim_crypto_or_native_success(self):
        data = capture()
        metadata = inspect_version_capture(data)
        self.assertEqual(metadata['sha256'], hashlib.sha256(data).hexdigest())
        for key in ('decrypted_body_checked', 'signature_checked',
                    'capture_authenticity_verified', 'native_ios_crypto_delivery_or_voice_verified'):
            self.assertFalse(metadata[key])
        # Neither an arbitrary signature nor opaque body authenticates a feed.
        for offset in (0, 4, 12):
            changed = bytearray(data)
            changed[offset] ^= 1
            with self.assertRaises(WiiSpeakVersionError):
                inspect_version_capture(bytes(changed))

    def test_explicit_replay_preserves_all_bytes_and_only_exact_route(self):
        data = capture()
        app = ExperimentalVersionReplay(data, expected_sha256=hashlib.sha256(data).hexdigest(),
                                        source_ref='private synthetic test', rights_ref='test fixture')
        self.assertEqual(app.get('/hcf/version.enc'), (200, 'application/octet-stream', data))
        for route in ('/', '/version.enc', '/hcf/version.enc?x=1', '/hcf/version.enc.00'):
            self.assertEqual(app.get(route)[0], 404)
        self.assertNotIn('synthetic', repr(app))
        self.assertNotIn('opaque!!', repr(app))
        self.assertFalse(app.metadata()['usable_native_version_service_verified'])
        with self.assertRaises(FrozenInstanceError):
            app._capture = b'changed'

    def test_replay_requires_matching_digest_and_explicit_bounded_references(self):
        kwargs = dict(expected_sha256=hashlib.sha256(capture()).hexdigest(),
                      source_ref='explicit source', rights_ref='explicit rights')
        for key, value in (('expected_sha256', '0' * 64), ('expected_sha256', True),
                           ('source_ref', ''), ('rights_ref', 'bad\nref'),
                           ('source_ref', 'x' * 2049)):
            with self.subTest(key=key):
                with self.assertRaises(WiiSpeakVersionError):
                    ExperimentalVersionReplay(capture(), **dict(kwargs, **{key: value}))

    def test_cli_reports_metadata_and_sanitized_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'explicit.bin'
            path.write_bytes(capture())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(['--capture', str(path)]), 0)
            self.assertNotIn('opaque!!', output.getvalue())
            self.assertIn('"signature_checked": false', output.getvalue())
            error = io.StringIO()
            path.write_bytes(bytes(1000))
            with contextlib.redirect_stderr(error):
                self.assertEqual(main(['--capture', str(path)]), 2)
            self.assertNotIn(str(path), error.getvalue())

    def test_native_source_rejected_before_optional_emulator_dependency(self):
        with self.assertRaises(ValueError):
            verify_version_reader(b'wrong original', b'')


class WiiSpeakNativeVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'private/channel_coverage_20261026/hcfj-v512/main.private.dol'
        if not path.is_file():
            raise unittest.SkipTest('Private Japanese HCFJ v512 application unavailable')
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native verification dependency unavailable')
        cls.source = path.read_bytes()

    def test_native_short_file_preserves_unwritten_constructor_tail(self):
        initial = struct.pack('>II', 2, 400)
        for size in range(9):
            data = b'\x7f' * size
            with self.subTest(size=size):
                result = verify_version_reader(self.source, data)
                self.assertEqual(result['status'], 0)
                self.assertEqual(result['destination_capacity'], 8)
                self.assertEqual(result['result_words'], list(struct.unpack('>II', data + initial[size:])))
                self.assertTrue(result['read_performed'])
                self.assertTrue(result['input_object_stack_guards_verified'])
                self.assertFalse(result['native_ios_crypto_delivery_or_voice_verified'])

    def test_native_oversize_stops_before_read_and_preserves_constructor(self):
        for size in (9, 16, 328, 8192):
            with self.subTest(size=size):
                result = verify_version_reader(self.source, bytes(size))
                self.assertEqual(result['status'], 0x16)
                self.assertEqual(result['result_words'], result['constructor_words'])
                self.assertFalse(result['read_performed'])
                # The original early return also bypasses close/unmount.
                self.assertNotIn('close_mock', result['events'])
                self.assertNotIn('unmount_mock', result['events'])

    def test_native_word_consumers_match_independent_inspector(self):
        pairs = [(value, 1) for value in (0, 1, 2, 3, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)]
        pairs += [(3, value) for value in (0, 0x3FFFFF, 0x400000, 0xFFFFFFFF)]
        for version, limit in pairs:
            with self.subTest(version=version, limit=limit):
                data = struct.pack('>II', version, limit)
                native = verify_version_reader(self.source, data)
                local = inspect_version_data(data).metadata()
                self.assertEqual(native['newer_than_client_2'], local['newer_than_native_client_2'])
                self.assertEqual(native['size_limit_bytes_u32'], local['size_limit_bytes_native_u32'])
                self.assertTrue(native['vf_allocator_and_sdk_services_mocked'])

