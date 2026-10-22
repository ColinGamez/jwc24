import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.inspect_demae_address_save import inspect_contract, inspect_metadata, main


class AddressSaveTests(unittest.TestCase):
    def test_metadata_does_not_decode_or_report_personal_fields(self):
        secret = 'PRIVATE NAME AND ADDRESS'
        data = secret.encode('utf-16-be').ljust(0x4000, b'\0')
        report = inspect_metadata(data)
        self.assertTrue(report['matches_observed_sample_size'])
        self.assertFalse(report['save_decoded'])
        self.assertFalse(report['personal_fields_reported'])
        self.assertFalse(report['native_acceptance_verified'])
        self.assertNotIn(secret, json.dumps(report))

    def test_magic_and_size_are_observations_not_validation(self):
        report = inspect_metadata(b'PDFF')
        self.assertTrue(report['starts_with_post_transform_magic'])
        self.assertFalse(report['matches_observed_sample_size'])
        self.assertFalse(report['checksum_verified'])
        self.assertFalse(report['native_acceptance_verified'])

    def test_invalid_inputs_rejected(self):
        for data in (b'', b'x'*(1024*1024+1), 'text', bytearray(b'PDFF')):
            with self.subTest(kind=type(data).__name__):
                with self.assertRaises(ValueError):
                    inspect_metadata(data)
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            inspect_contract(b'wrong executable')

    def test_native_trace(self):
        source = Path(__file__).resolve().parents[1]/'private/demae/v2/main.decompressed.dol'
        if not source.is_file():
            self.skipTest('Private helper executable unavailable')
        report = inspect_contract(source.read_bytes())
        self.assertEqual(report['transform_buffer_bytes'], 16384)
        self.assertEqual(report['caller_key_bits'], 256)
        self.assertEqual(report['post_transform_magic'], 'PDFF')
        self.assertTrue(report['helper_success_required'])
        self.assertTrue(report['static_trace_only'])

    def test_cli_success_and_failure_do_not_echo_input_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'save.dat'
            path.write_bytes(b'PRIVATE-FIELD'.ljust(16384, b'\0'))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(path)]), 0)
            self.assertNotIn('PRIVATE-FIELD', output.getvalue())
            self.assertEqual(json.loads(output.getvalue())['metadata']['size'], 16384)
            path.write_bytes(b'')
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(main([str(path)]), 1)
            self.assertNotIn(str(path), errors.getvalue())
