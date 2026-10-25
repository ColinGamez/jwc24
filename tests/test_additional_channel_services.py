"""Synthetic audit guards and optional owned-package provenance checks."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from jwc24.lz11 import encode_lz11
from tools.audit_additional_channel_services import CHANNELS, application_image, checked_content, audit_package


class ChannelServiceAuditTests(unittest.TestCase):
    def test_application_header_bounds_are_checked_before_decompression(self):
        payload = b'synthetic application bytes'
        self.assertEqual(application_image({1: encode_lz11(payload)}), payload)
        for body in (b'', b'\x11\0\0\0', b'\x11\0\0\0\xff\xff\xff\x7f',
                     b'\x11\x01\0\0', b'not compressed'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                application_image({1: body})

    def test_content_path_and_digest_checks_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = '0001-00000001.app'
            payload = b'synthetic extracted content'
            (root/name).write_bytes(payload)
            row = {'file': name, 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
            self.assertEqual(checked_content(root, row), payload)
            for bad in ({**row, 'file': '../outside.app'}, {**row, 'file': '/outside.app'},
                        {**row, 'sha256': '0'*64}, {**row, 'size': len(payload)+1}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    checked_content(root, bad)

    def test_owned_packages_match_every_tmd_content_without_signature_claim(self):
        base = Path('private/channel_coverage_20261026')
        if not all((base/spec.extracted/'manifest.json').is_file()
                   and (Path('Stock WADs')/spec.filename).is_file() for spec in CHANNELS):
            self.skipTest('Private owned packages and independently extracted contents required')
        results = [audit_package(Path('Stock WADs')/spec.filename, base/spec.extracted, spec)
                   for spec in CHANNELS]
        self.assertEqual(sum(len(row['verified_contents']) for row in results), 34)
        for row in results:
            self.assertTrue(row['ticket_tmd_title_identity_matches'])
            self.assertTrue(row['all_content_sizes_and_sha1_match_tmd'])
            self.assertFalse(row['nintendo_signature_verified'])
            self.assertFalse(row['original_program_or_script_executed'])
            self.assertFalse(row['network_or_device_state_accessed'])
        affinity = results[0]['selected_bundled_resources']
        self.assertEqual(affinity[0]['content_index'], 6)
        self.assertEqual(affinity[0]['bytes'], 20580)


if __name__ == '__main__':
    unittest.main()
