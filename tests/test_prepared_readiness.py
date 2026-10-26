"""Preparation follows the same immutable publications as actual serving.

All schedules/articles and signing keys here are generated synthetic fixtures.
No real providers, credentials, sockets or profiles are used.
"""
import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from jwc24 import __main__ as cli
from jwc24.forecast import WII_EPOCH_UNIX
from jwc24.hbnj_publication import HBNJRouteSnapshot, load_hbnj_snapshot, publish_hbnj_snapshot
from jwc24.manifest import Asset
from jwc24.news_publication import build_news_publication, write_news_publication
from jwc24.readiness import inspect_readiness
from tests.test_hbnj_publication import fixture, write_fixture
from tests.test_hbnj_shared_server import hbnj_manifest
from tests.test_news import synthetic_news
from tests.test_wc24_delivery import manifest


def codes(report):
    return {issue['code'] for issue in report['issues']}


class HBNJPreparedReadinessTests(unittest.TestCase):
    now = 1_800_000_000

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        guide, payloads = write_fixture(cls.root / 'input', fixture(cls.now))
        cls.publication_root = cls.root / 'publication'
        publish_hbnj_snapshot(guide, payloads, cls.publication_root, now=cls.now,
                              rights_ref='synthetic-only', max_collection_age_seconds=3600)
        cls.snapshot = load_hbnj_snapshot(cls.publication_root, now=cls.now)

    def test_valid_snapshot_supplies_only_its_owned_tasks_and_does_not_mutate_files(self):
        value = hbnj_manifest(self.root)
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertIn('payload_missing', codes(inspect_readiness((value,), now=self.now)))
        result = inspect_readiness((value,), hbnj_snapshot=self.snapshot, now=self.now,
                                   max_payload_age_seconds=1)
        self.assertTrue(result['preflight_passed'])
        self.assertEqual(result['checks']['prepared_publications']['hbnj'], 'validated_current_snapshot')
        self.assertFalse(result['native_readiness_verified'])
        self.assertFalse(result['network_used'])
        self.assertFalse(result['profile_modified'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        with tempfile.TemporaryDirectory() as directory:
            other = manifest(Path(directory), 1, 'other.bin')
            other.tasks[0].payload.unlink()
            result = inspect_readiness((value, other), hbnj_snapshot=self.snapshot, now=self.now)
            self.assertIn('payload_missing', codes(result))
            self.assertEqual([i['channel'] for i in result['issues'] if i['code'] == 'payload_missing'],
                             ['SYNTHETIC'])
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertNotIn(self.snapshot.generation, json.dumps(result))

    def test_invalid_expired_wrong_owner_transport_and_conflicting_routes_fail(self):
        value = hbnj_manifest(self.root)
        cases = [((value,), object(), self.now, 'hbnj_snapshot_invalid'),
                 ((value,), HBNJRouteSnapshot(), self.now, 'hbnj_snapshot_invalid_or_expired'),
                 ((value,), self.snapshot, self.snapshot.expires_unix, 'hbnj_snapshot_invalid_or_expired'),
                 ((replace(value, title_id=1),), self.snapshot, self.now, 'hbnj_snapshot_owner_mismatch'),
                 ((replace(value, tasks=(replace(value.tasks[0], envelope='raw'), *value.tasks[1:])),),
                  self.snapshot, self.now, 'hbnj_snapshot_transport_mismatch')]
        with tempfile.TemporaryDirectory() as directory:
            other = manifest(Path(directory), 1, 'other.bin')
            other = replace(other, tasks=(replace(other.tasks[0], route='/other/epg.bin'),))
            cases.append(((value, other), self.snapshot, self.now, 'hbnj_snapshot_route_conflict'))
            for manifests, snapshot, now, expected in cases:
                with self.subTest(expected=expected):
                    report = inspect_readiness(manifests, hbnj_snapshot=snapshot, now=now)
                    self.assertIn(expected, codes(report))
                    self.assertFalse(report['preflight_passed'])

    def test_cli_loads_real_snapshot_without_listening_and_redacts_invalid_input(self):
        value = hbnj_manifest(self.root)
        command = ['jwc24', 'preflight', 'synthetic.json', '--hbnj-root', str(self.publication_root)]
        output = io.StringIO()
        with patch('sys.argv', command), patch.object(cli, 'load_manifest', return_value=value), \
                patch('time.time', return_value=self.now), patch.object(cli, 'serve') as serving, \
                contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(), 0)
            serving.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['checks']['prepared_publications']['hbnj'],
                         'validated_current_snapshot')
        output = io.StringIO()
        with patch('sys.argv', command), patch.object(cli, 'load_manifest', return_value=value), \
                patch('jwc24.hbnj_publication.load_hbnj_snapshot', side_effect=ValueError('secret-marker')), \
                contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(), 2)
        self.assertNotIn('secret-marker', output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL required for actual explicit-key verification')
class NewsPreparedReadinessTests(unittest.TestCase):
    now = WII_EPOCH_UNIX + 10000 * 60

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        private, cls.public = cls.root / 'generated.pem', cls.root / 'generated-public.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048',
                        '-out', str(private)], capture_output=True, check=True, timeout=30)
        subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(cls.public)],
                       capture_output=True, check=True, timeout=15)
        cls.news = build_news_publication(
            [synthetic_news()] * 24, private_key=private, public_key=cls.public,
            route_prefix='/v2/0/001', source_refs=['synthetic-no-provider'] * 24,
            rights_ref='synthetic-only', current_unix_timestamp=cls.now)
        cls.publication_root = cls.root / 'publication'
        write_news_publication(cls.publication_root, cls.news, current_unix_timestamp=cls.now)

    def test_news_window_and_manifest_conflicts_share_server_contract(self):
        value = manifest(self.root, 1, 'plain.bin')
        report = inspect_readiness((value,), news_publication=self.news, now=self.now)
        self.assertTrue(report['preflight_passed'])
        self.assertEqual(report['checks']['prepared_publications']['news'], 'validated_current_snapshot')
        self.assertEqual(report['checks']['news_native_subtask_registration'], 'not_implemented')
        self.assertFalse(report['native_readiness_verified'])
        self.assertIn('news_publication_expired', codes(inspect_readiness(
            (value,), news_publication=self.news, now=self.now + 100000 * 60)))
        self.assertIn('news_publication_invalid', codes(inspect_readiness(
            (value,), news_publication=object(), now=self.now)))
        for bad in (replace(value, tasks=(replace(value.tasks[0], route='/v2/0/001/anything'),)),
                    replace(value, tasks=(replace(value.tasks[0], filename='news.bin.00'),)),
                    replace(value, tasks=(), assets=(Asset('news.bin.23', value.tasks[0].payload, 'none', 'raw'),))):
            self.assertIn('news_publication_route_conflict', codes(inspect_readiness(
                (bad,), news_publication=self.news, now=self.now)))

    def test_cli_verifies_real_signed_publication_and_requires_explicit_key_pair(self):
        value = manifest(self.root, 1, 'plain.bin')
        command = ['jwc24', 'preflight', 'synthetic.json', '--news-root', str(self.publication_root),
                   '--news-public-key', str(self.public)]
        output = io.StringIO()
        with patch('sys.argv', command), patch.object(cli, 'load_manifest', return_value=value), \
                patch('time.time', return_value=self.now), patch.object(cli, 'serve') as serving, \
                contextlib.redirect_stdout(output):
            self.assertEqual(cli.main(), 0)
            serving.assert_not_called()
        self.assertTrue(json.loads(output.getvalue())['preflight_passed'])
        for option in ('--news-root', '--news-public-key'):
            output = io.StringIO()
            with patch('sys.argv', ['jwc24', 'preflight', 'synthetic.json', option, 'secret-marker']), \
                    patch.object(cli, 'load_manifest', return_value=value), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(), 2)
            self.assertNotIn('secret-marker', output.getvalue())

    def test_independent_bad_news_does_not_hide_valid_hbnj_or_missing_unowned_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            publish_hbnj_snapshot(guide, payloads, root / 'publication', now=self.now,
                                  rights_ref='synthetic-only', max_collection_age_seconds=3600)
            snapshot = load_hbnj_snapshot(root / 'publication', now=self.now)
            hbnj, other = hbnj_manifest(root), manifest(root, 1, 'other.bin')
            other.tasks[0].payload.unlink()
            report = inspect_readiness((hbnj, other), news_publication=object(),
                                       hbnj_snapshot=snapshot, now=self.now)
            self.assertEqual(codes(report), {'news_publication_invalid', 'payload_missing'})
            self.assertEqual(report['checks']['prepared_publications']['hbnj'], 'validated_current_snapshot')
