import contextlib
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24.forecast_freshness import ForecastSourceError, check_forecast_sources
from tools import check_forecast_sources as cli


class ForecastFreshnessTests(unittest.TestCase):
    now = 1_800_000_000

    def fixture(self):
        # Schema-light synthetic rows exercise this acquisition boundary only.
        # Existing binary builders separately validate weather field schemas.
        row = {'country_code': 1, 'region_code': 10, 'location_code': 2,
               'local_unix_timestamp': self.now + 9 * 3600}
        documents = {name: json.dumps([row] if name != 'compact' else []).encode()
                     for name in ('current', 'long', 'compact')}
        entry = {'key': [1, 10, 2], 'source_sha256': 'a' * 64,
                 'source_ref': 'synthetic private capture', 'time_basis': 'provider_observation',
                 'source_time_utc': self.now - 100, 'retrieved_utc': self.now - 1,
                 'valid_until_utc': self.now + 1000}
        receipts = {'schema_version': 1, 'rights_ref': 'synthetic fixture rights',
                    'provider_times_retimed': False, 'reference_weather_substituted': False,
                    'datasets': {name: {'normalized_sha256': hashlib.sha256(value).hexdigest(),
                                        'entries': [deepcopy(entry)] if name != 'compact' else []}
                                 for name, value in documents.items()}}
        return documents, receipts

    def check(self, documents, receipts):
        return check_forecast_sources(documents, receipts, now=self.now, max_source_age_seconds=3600)

    def test_utc_source_time_is_separate_from_retrieval_and_local_clock(self):
        documents, receipts = self.fixture()
        report = self.check(documents, receipts)
        self.assertEqual(report['oldest_source_age_seconds'], 100)
        self.assertEqual(report['rows'], {'current': 1, 'long': 1, 'compact': 0})
        self.assertFalse(report['provider_timestamp_extraction_independently_verified'])
        self.assertFalse(report['native_clock_fields_used_as_source_times'])
        self.assertFalse(report['native_payload_generated_or_published'])
        self.assertNotIn('synthetic private', json.dumps(report))

    def test_new_fetch_or_envelope_does_not_make_old_source_fresh(self):
        documents, receipts = self.fixture()
        rows = json.loads(documents['current'])
        rows[0]['local_unix_timestamp'] = self.now + 9 * 3600
        documents['current'] = json.dumps(rows).encode()
        receipts['datasets']['current']['normalized_sha256'] = hashlib.sha256(documents['current']).hexdigest()
        entry = receipts['datasets']['current']['entries'][0]
        entry['source_time_utc'] = self.now - 3600
        entry['retrieved_utc'] = self.now
        with self.assertRaisesRegex(ForecastSourceError, 'stale'):
            self.check(documents, receipts)

    def test_fresh_source_receipt_accepts_independently_rebuilt_native_local_clock(self):
        documents, receipts = self.fixture()
        rows = json.loads(documents['current'])
        rows[0]['local_unix_timestamp'] += 100
        documents['current'] = json.dumps(rows).encode()
        receipts['datasets']['current']['normalized_sha256'] = hashlib.sha256(documents['current']).hexdigest()
        report = self.check(documents, receipts)
        self.assertEqual(report['oldest_source_age_seconds'], 100)
        self.assertFalse(report['native_clock_fields_used_as_source_times'])
        self.assertNotIn('normalized_record_times_match_receipts', report)

    def test_parse_time_historical_substitution_and_retime_attestations_fail(self):
        for kind in ('parse_time', 'reference_weather_substituted', 'provider_times_retimed'):
            documents, receipts = self.fixture()
            if kind == 'parse_time':
                receipts['datasets']['current']['entries'][0]['time_basis'] = 'parse_time'
            else:
                receipts[kind] = True
            with self.subTest(kind=kind), self.assertRaises(ForecastSourceError):
                self.check(documents, receipts)

    def test_source_receipts_do_not_accept_native_offset_or_old_attestation_fields(self):
        for kind in ('utc_offset_minutes', 'normalization_retimed'):
            documents, receipts = self.fixture()
            if kind == 'utc_offset_minutes':
                receipts['datasets']['current']['entries'][0][kind] = 540
            else:
                receipts[kind] = receipts.pop('provider_times_retimed')
            with self.subTest(kind=kind), self.assertRaises(ForecastSourceError):
                self.check(documents, receipts)

    def test_future_expired_missing_and_unbound_receipts_fail(self):
        for kind in ('future_issue', 'future_fetch', 'expired', 'missing', 'digest', 'duplicate'):
            documents, receipts = self.fixture()
            dataset = receipts['datasets']['current']
            entry = dataset['entries'][0]
            if kind == 'future_issue':
                entry['source_time_utc'] = self.now + 1
            elif kind == 'future_fetch':
                entry['retrieved_utc'] = self.now + 1
            elif kind == 'expired':
                entry['valid_until_utc'] = self.now
            elif kind == 'missing':
                dataset['entries'] = []
            elif kind == 'digest':
                dataset['normalized_sha256'] = '0' * 64
            else:
                dataset['entries'].append(deepcopy(entry))
            with self.subTest(kind=kind), self.assertRaises(ForecastSourceError):
                self.check(documents, receipts)

    def test_duplicate_json_fields_and_nonfinite_numbers_reject(self):
        documents, receipts = self.fixture()
        for data in (b'[{"country_code":1,"country_code":2}]', b'[NaN]'):
            changed = dict(documents, current=data)
            with self.assertRaises(ForecastSourceError):
                self.check(changed, receipts)

    def test_cli_checks_explicit_files_and_sanitizes_failure(self):
        documents, receipts = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in documents.items():
                (root / f'{name}.json').write_bytes(value)
            (root / 'receipts.json').write_text(json.dumps(receipts))
            arguments = [item for name in ('current', 'long', 'compact', 'receipts')
                         for item in (f'--{name}', str(root / f'{name}.json'))]
            arguments += ['--max-source-age-seconds', '3600']
            output = io.StringIO()
            with patch.object(cli.time, 'time', return_value=self.now), contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(arguments), 0)
            self.assertIn('source_ages_checked_against_supplied_receipts', output.getvalue())
            (root / 'current.json').write_bytes(b'[]')
            errors = io.StringIO()
            with patch.object(cli.time, 'time', return_value=self.now), contextlib.redirect_stderr(errors):
                self.assertEqual(cli.main(arguments), 2)
            self.assertNotIn(str(root), errors.getvalue())
            self.assertEqual((root / 'current.json').read_bytes(), b'[]')
