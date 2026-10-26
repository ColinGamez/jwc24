"""Explicit signed News publication with generated keys and synthetic articles."""
import contextlib
from dataclasses import replace
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from jwc24.forecast import WII_EPOCH_UNIX
from jwc24.news import inspect_news_envelope
from jwc24.news_publication import (NewsPublicationError, build_news_publication,
                                    load_news_publication, prepare_news_publication,
                                    write_news_publication)
from jwc24.news_server import NewsApplication, create_news_server
from tests.test_news import change_word, synthetic_news
from tools.news_service import main


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL is required for explicit-key signing tests')
class NewsPublicationTests(unittest.TestCase):
    now = WII_EPOCH_UNIX + 10000 * 60
    refs = tuple(f'urn:jwc24:synthetic-test:slot-{slot:02d}' for slot in range(24))
    rights = 'urn:jwc24:synthetic-test:no-provider-content'

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='jwc24-news-publication-test-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.private_key = Path(cls.directory.name) / 'generated-private.pem'
        cls.public_key = Path(cls.directory.name) / 'generated-public.pem'
        cls.other_private = Path(cls.directory.name) / 'other-private.pem'
        cls.other_public = Path(cls.directory.name) / 'other-public.pem'
        for private, public in ((cls.private_key, cls.public_key), (cls.other_private, cls.other_public)):
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048',
                            '-out', str(private)], capture_output=True, check=True, timeout=30)
            subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public)],
                           capture_output=True, check=True, timeout=15)
        cls.publication = cls.build([synthetic_news()] * 24)

    @classmethod
    def build(cls, buffers, **overrides):
        options = dict(private_key=cls.private_key, public_key=cls.public_key,
                       route_prefix='/v2/0/001', source_refs=cls.refs, rights_ref=cls.rights,
                       current_unix_timestamp=cls.now)
        options.update(overrides)
        return build_news_publication(buffers, **options)

    def prepare(self, payloads, **overrides):
        options = dict(public_key=self.public_key, route_prefix='/v2/0/001',
                       source_refs=self.refs, rights_ref=self.rights, current_unix_timestamp=self.now)
        options.update(overrides)
        return prepare_news_publication(payloads, **options)

    def write(self, root, publication=None):
        return write_news_publication(root, publication or self.publication,
                                       current_unix_timestamp=self.now)

    def load(self, root, **overrides):
        options = dict(public_key=self.public_key, current_unix_timestamp=self.now)
        options.update(overrides)
        return load_news_publication(root, **options)

    def generation(self, root):
        return root / json.loads((root / 'current.json').read_text())['generation']

    def test_build_signs_real_envelope_without_rewriting_native_text_or_time(self):
        result = self.publication
        inspection = inspect_news_envelope(result.payloads[0])
        self.assertEqual(inspection.updated_timestamp, 10000)
        self.assertEqual(inspection.articles[0].text, 'Synthetic article body \u672c\u6587')
        self.assertNotEqual(result.payloads[0][64:320], bytes(256))
        report = result.metadata()
        self.assertTrue(report['signatures_verified_against_supplied_key'])
        self.assertTrue(report['cross_buffer_references_checked'])
        self.assertFalse(report['rights_independently_verified'])
        self.assertFalse(report['installed_client_trust_verified'])
        self.assertFalse(report['time_slot_mapping_or_24_hour_coverage_verified'])
        self.assertNotIn('Synthetic', repr(result))
        self.assertNotIn(self.rights, json.dumps(report))

    def test_preexisting_signed_inputs_verify_against_only_the_explicit_key(self):
        self.assertEqual(self.prepare(self.publication.payloads).payloads, self.publication.payloads)
        with self.assertRaisesRegex(NewsPublicationError, 'signature'):
            self.prepare(self.publication.payloads, public_key=self.other_public)
        with self.assertRaisesRegex(NewsPublicationError, 'signature'):
            self.prepare([bytes(320) + value[320:] for value in self.publication.payloads])
        with self.assertRaisesRegex(NewsPublicationError, 'signature'):
            self.build([synthetic_news()] * 24, public_key=self.other_public)

    def test_copied_or_replaced_publication_cannot_bypass_preparation(self):
        altered = replace(self.publication, payloads=tuple(bytes(321) for _ in range(24)))
        with self.assertRaises(NewsPublicationError):
            NewsApplication(altered)
        with self.assertRaises(NewsPublicationError):
            altered.metadata()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(NewsPublicationError):
                self.write(directory, altered)
            self.assertFalse((Path(directory) / 'current.json').exists())

    def test_invalid_or_incoherent_raw_inputs_stop_before_signing(self):
        with patch('jwc24.news_publication.subprocess.run', side_effect=AssertionError('signing invalid input')):
            with self.assertRaises(NewsPublicationError):
                self.build([synthetic_news(reference_time=9999)] * 24)
            with self.assertRaises(NewsPublicationError):
                self.build([synthetic_news()] * 24, rights_ref='')

    def test_streaming_inputs_are_rejected_before_iteration_or_signing(self):
        def streaming():
            raise AssertionError('Streaming native inputs must not be consumed')
            yield b''
        with patch('jwc24.news_publication.subprocess.run', side_effect=AssertionError('signing a stream')):
            with self.assertRaises(NewsPublicationError):
                self.build(streaming())
            with self.assertRaises(NewsPublicationError):
                self.prepare(streaming())

    def test_temporary_signing_key_mode_and_cleanup(self):
        run = subprocess.run
        seen = []

        def inspect_key(arguments, **kwargs):
            if '-sign' in arguments:
                path = Path(arguments[arguments.index('-sign') + 1])
                seen.append(path)
                if os.name != 'nt':
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            return run(arguments, **kwargs)

        with patch('jwc24.news_publication.subprocess.run', side_effect=inspect_key):
            self.build([synthetic_news()] * 24)
        self.assertTrue(seen)
        self.assertTrue(all(not path.exists() for path in seen))

    def test_missing_source_rights_or_mismatched_prefix_cannot_publish(self):
        for options in ({'source_refs': []}, {'source_refs': [''] * 24},
                        {'rights_ref': ''}, {'route_prefix': '/v2/1/001'},
                        {'route_prefix': '/v2/0/002'}, {'route_prefix': '/v2/0/001?secret'}):
            with self.subTest(options=options), self.assertRaises(NewsPublicationError):
                self.prepare(self.publication.payloads, **options)

    def test_current_windows_reject_future_expired_and_fail_closed_at_serving(self):
        with self.assertRaises(NewsPublicationError):
            self.prepare(self.publication.payloads, current_unix_timestamp=self.now - 60)
        with self.assertRaises(NewsPublicationError):
            self.prepare(self.publication.payloads, current_unix_timestamp=self.now + 1001 * 60)
        self.assertTrue(self.publication.is_current(self.now + 1000 * 60))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(NewsPublicationError):
                write_news_publication(directory, self.publication,
                                       current_unix_timestamp=self.now + 1001 * 60)
            self.assertFalse((Path(directory) / 'current.json').exists())

    def test_roundtrip_publishes_all24_signed_files_in_one_private_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root)
            loaded = self.load(root)
            self.assertEqual(loaded.payloads, self.publication.payloads)
            self.assertEqual(loaded.source_refs, self.refs)
            self.assertEqual(loaded.rights_ref, self.rights)
            generation = self.generation(root)
            self.assertEqual(len(list(generation.glob('news.bin.*'))), 24)
            self.assertEqual(list(root.glob('.staging-news-*')), [])
            self.assertEqual(list(root.glob('.pointer-news-*')), [])

    def test_failed_staging_or_pointer_replace_preserves_previous_complete_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root)
            previous = (root / 'current.json').read_bytes()
            original = os.replace
            for stage in ('generation', 'pointer'):
                def replace(source, target):
                    if (stage == 'pointer') == (Path(target).name == 'current.json'):
                        raise OSError('synthetic publication failure')
                    original(source, target)
                with self.subTest(stage=stage), patch('jwc24.news_publication.os.replace', side_effect=replace):
                    with self.assertRaises(OSError):
                        self.write(root)
                self.assertEqual((root / 'current.json').read_bytes(), previous)
                self.assertEqual(self.load(root).payloads, self.publication.payloads)
                self.assertEqual(list(root.glob('.staging-news-*')), [])
                self.assertEqual(list(root.glob('.pointer-news-*')), [])

    def test_modified_payload_missing_slot_and_wrong_public_key_fail_reload(self):
        for mutation in ('damage', 'missing', 'key'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write(root)
                first = self.generation(root) / 'news.bin.00'
                if mutation == 'damage':
                    first.write_bytes(b'private-altered-content')
                elif mutation == 'missing':
                    first.unlink()
                with self.assertRaises(NewsPublicationError):
                    self.load(root, public_key=self.other_public if mutation == 'key' else self.public_key)

    def test_manifest_traversal_reordering_and_duplicate_fields_are_rejected(self):
        for mutation in ('traversal', 'reorder', 'duplicate'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write(root)
                path = self.generation(root) / 'manifest.json'
                document = json.loads(path.read_text())
                if mutation == 'traversal':
                    document['files'][0]['filename'] = '../private.pem'
                elif mutation == 'reorder':
                    document['files'].reverse()
                if mutation == 'duplicate':
                    path.write_text('{"schema_version":1,"schema_version":1}')
                else:
                    path.write_text(json.dumps(document))
                with self.assertRaises(NewsPublicationError):
                    self.load(root)

    def test_adapter_serves_exact_subtasks_and_never_invents_an_unsuffixed_snapshot(self):
        application = NewsApplication(self.publication, clock=lambda: self.now)
        for slot in range(24):
            self.assertEqual(application.get(f'/v2/0/001/news.bin.{slot:02d}'),
                             (200, 'application/octet-stream', self.publication.payloads[slot]))
        for target in ('/v2/0/001/news.bin', '/v2/0/001/news.bin.24', '/v2/0/001/news.bin.0',
                       '/v2/0/002/news.bin.00', '/v2/0/001/news.bin.00?secret', '../news.bin.00'):
            self.assertEqual(application.get(target)[0], 404)
        expired = NewsApplication(self.publication, clock=lambda: self.now + 1001 * 60)
        self.assertEqual(expired.get('/v2/0/001/news.bin.00'), (503, 'application/octet-stream', b''))

    def test_actual_loopback_http_preserves24_signed_bodies_and_content_lengths(self):
        server = create_news_server(('127.0.0.1', 0), self.publication, clock=lambda: self.now)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(*server.server_address, timeout=5)
            try:
                for slot in range(24):
                    connection.request('GET', f'/v2/0/001/news.bin.{slot:02d}')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(int(response.getheader('Content-Length')), len(self.publication.payloads[slot]))
                    self.assertEqual(response.read(), self.publication.payloads[slot])
            finally:
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_cli_build_from_explicit_config_is_bounded_and_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_path = root / 'private-raw.bin'
            raw_path.write_bytes(synthetic_news())
            document = {'schema_version': 1, 'route_prefix': '/v2/0/001', 'rights_ref': self.rights,
                        'inputs': [{'slot': slot, 'path': raw_path.name, 'source_ref': self.refs[slot]}
                                   for slot in range(24)]}
            config = root / 'private-config.json'
            config.write_text(json.dumps(document))
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch('jwc24.news_publication.time.time', return_value=self.now):
                self.assertEqual(main(['build', '--config', str(config), '--private-key', str(self.private_key),
                                       '--public-key', str(self.public_key), '--output', str(root / 'published')]), 0)
            result = json.loads(output.getvalue())
            self.assertTrue(result['publication_written'])
            self.assertNotIn('private-', output.getvalue())
            self.assertNotIn('Synthetic', output.getvalue())
            self.assertEqual(raw_path.read_bytes(), synthetic_news())
            self.assertEqual(self.load(root / 'published').payloads, self.publication.payloads)


if __name__ == '__main__':
    unittest.main()
