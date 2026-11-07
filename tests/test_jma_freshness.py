"""Separate weather clocks/cache ages; no network, original software or retiming."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from jwc24.jma_associations import parse_associations
from jwc24.jma_freshness import JMAAgePolicy, check_jma_age
from jwc24.jma_weather import (
    BASE, JMAError, SourceReceipt, parse_forecast, parse_latest_time,
    parse_observations, parse_station, point_url,
)
from tests.test_jma_associations import catalog_values, forecast_values
from tests.test_jma_weather import station_fixture


NOW = datetime(2026, 1, 2, 9, tzinfo=timezone.utc)
KEY = "20260102174000"


def receipt(url, body, ended=NOW - timedelta(minutes=1)):
    return SourceReceipt.from_body(url, body, ended - timedelta(seconds=1), ended)


def inputs(key=KEY):
    def encoded(value):
        return json.dumps(value, ensure_ascii=False).encode('utf-8')
    body = encoded(forecast_values())
    forecast = parse_forecast(body, receipt(BASE + '/bosai/forecast/data/forecast/130000.json', body))
    body = b'2026-01-02T17:50:00+09:00'
    latest = parse_latest_time(body, receipt(BASE + '/bosai/amedas/data/latest_time.txt', body))
    body = encoded(station_fixture())
    station = parse_station(body, receipt(BASE + '/bosai/amedas/const/amedastable.json', body), '44132')
    body = encoded({key: {'prefNumber': 44, 'observationNumber': 132,
                         'temp': [2, 0], 'wind': [1, 0], 'windDirection': [4, 0]}})
    observations = parse_observations(body, receipt(point_url('44132', latest), body), station, latest)
    paths = ('forecast_area', 'week_area', 'week_area05', 'week_area_name')
    pairs = []
    for name, value in zip(paths, catalog_values()):
        body = encoded(value)
        pairs.extend((body, receipt(BASE + '/bosai/forecast/const/' + name + '.json', body)))
    return forecast, observations, parse_associations(*pairs)


def policy(**changes):
    values = dict(observation_seconds=1800, forecast_issue_seconds=12 * 3600,
                  national_latest_seconds=1800, metadata_cache_seconds=86400,
                  station_lag_seconds=1200)
    values.update(changes)
    return JMAAgePolicy(**values)


def check(values=None, **changes):
    options = dict(report_indices=(0, 1), observation_key_jst=KEY, now=NOW, policy=policy())
    options.update(changes)
    return check_jma_age(*(inputs() if values is None else values), **options)


class JMAFreshnessTests(unittest.TestCase):
    def test_distinct_issue_observation_national_and_cache_clocks(self):
        value = check()
        rows = {r.role: r for r in value.checks}
        self.assertEqual(rows['forecast_report:0'].age_seconds, 3600)
        self.assertEqual(rows['forecast_report:1'].age_seconds, 7 * 3600)
        self.assertEqual(rows['station_observation'].age_seconds, 1200)
        self.assertEqual(rows['national_latest'].age_seconds, 600)
        self.assertTrue(all(r.age_seconds == 60 for r in value.checks if r.time_basis == 'metadata_retrieval'))
        self.assertEqual(value.station_lag_seconds, 600)
        self.assertEqual(value.earliest_expiry_utc, NOW + timedelta(minutes=10))

    def test_twelve_hour_forecast_allowance_never_accepts_stale_current_reading(self):
        with self.assertRaisesRegex(JMAError, 'station_observation.*stale'):
            check(inputs('20260102172000'), observation_key_jst='20260102172000',
                  policy=policy(station_lag_seconds=3600))
        # The older weekly report is valid under its separate twelve-hour policy.
        self.assertEqual(check().forecast_report_indices, (0, 1))

    def test_each_deadline_is_strict_and_publication_cannot_extend_it(self):
        with self.assertRaisesRegex(JMAError, 'station_observation.*stale'):
            check(now=NOW + timedelta(minutes=10))
        with self.assertRaisesRegex(JMAError, 'forecast_report:1.*stale'):
            check(policy=policy(forecast_issue_seconds=7 * 3600))
        with self.assertRaisesRegex(JMAError, 'metadata:stations.*stale'):
            check(policy=policy(metadata_cache_seconds=60))
        with self.assertRaisesRegex(JMAError, 'national_latest.*stale'):
            check(policy=policy(national_latest_seconds=600))

    def test_metadata_retrieval_never_replaces_weather_time(self):
        forecast, obs, cat = inputs()
        old = replace(forecast.reports[0], report_datetime='2025-12-30T17:00:00+09:00',
                      issued_utc=datetime(2025, 12, 30, 8, tzinfo=timezone.utc))
        forecast = replace(forecast, reports=(old, forecast.reports[1]))
        with self.assertRaisesRegex(JMAError, 'forecast_report:0.*stale'):
            check((forecast, obs, cat))

    def test_raw_and_parsed_weather_dates_must_agree(self):
        forecast, obs, cat = inputs()
        changed = replace(forecast.reports[0], issued_utc=NOW - timedelta(minutes=1))
        with self.assertRaisesRegex(JMAError, 'raw issue date'):
            check((replace(forecast, reports=(changed, forecast.reports[1])), obs, cat))
        latest = replace(obs.national_latest, time_utc=NOW - timedelta(minutes=1))
        with self.assertRaisesRegex(JMAError, 'national raw date'):
            check((forecast, replace(obs, national_latest=latest), cat))
        record = replace(obs.records[0], observed_utc=NOW - timedelta(minutes=1))
        with self.assertRaisesRegex(JMAError, 'observation key'):
            check((forecast, replace(obs, records=(record,)), cat))

    def test_future_retrieval_and_provider_dates_reject(self):
        forecast, obs, cat = inputs()
        future = replace(forecast.receipt, retrieved_end_utc=NOW + timedelta(seconds=1))
        with self.assertRaisesRegex(JMAError, 'retrieval'):
            check((replace(forecast, receipt=future), obs, cat))
        report = replace(forecast.reports[0], report_datetime='2026-01-02T18:00:00+09:00', issued_utc=NOW)
        with self.assertRaisesRegex(JMAError, 'provider time'):
            check((replace(forecast, reports=(report, forecast.reports[1])), obs, cat))

    def test_station_lag_is_separate_from_absolute_observation_age(self):
        with self.assertRaisesRegex(JMAError, 'lag policy'):
            check(policy=policy(station_lag_seconds=600))
        # This constraint compares actual station/national times, not fetch time.
        self.assertEqual(check(now=NOW + timedelta(minutes=1)).station_lag_seconds, 600)

    def test_explicit_report_and_record_selection_has_no_newest_default(self):
        only = check(report_indices=(1,))
        self.assertEqual([r.role for r in only.checks if r.time_basis == 'provider_issue'], ['forecast_report:1'])
        for selection in ((), (0, 0), (True,), (-1,), (2,), [0]):
            with self.subTest(selection=selection), self.assertRaises(JMAError):
                check(report_indices=selection)
        for key in ('latest', '20260102173000', True):
            with self.subTest(key=key), self.assertRaises(JMAError):
                check(observation_key_jst=key)
        forecast, obs, cat = inputs()
        with self.assertRaisesRegex(JMAError, 'ambiguous'):
            check((forecast, replace(obs, records=obs.records * 2), cat))

    def test_source_window_office_and_metadata_dependencies_are_bound(self):
        forecast, obs, cat = inputs()
        with self.assertRaisesRegex(JMAError, 'office'):
            check((replace(forecast, office_code='100000'), obs, cat))
        with self.assertRaisesRegex(JMAError, 'source window'):
            check((forecast, replace(obs, station=replace(obs.station, code='99999')), cat))
        with self.assertRaisesRegex(JMAError, 'incomplete'):
            check((forecast, obs, replace(cat, receipts=cat.receipts[:3])))
        with self.assertRaises(JMAError):
            check((forecast, obs, replace(cat, receipts=(None,) * 4)))

    def test_optional_condition_and_identity_metadata_have_own_cache_expiry(self):
        body = b'synthetic metadata'
        extra = tuple(receipt(BASE + path, body, NOW - timedelta(hours=1)) for path in (
            '/bosai/forecast/', '/bosai/common/const/area.json'))
        value = check(additional_metadata_receipts=extra, policy=policy(metadata_cache_seconds=3700))
        self.assertEqual(len(value.checks), 11)
        self.assertEqual(value.earliest_expiry_utc, NOW + timedelta(seconds=100))
        with self.assertRaisesRegex(JMAError, 'metadata:forecast_client.*stale'):
            check(additional_metadata_receipts=extra, policy=policy(metadata_cache_seconds=3600))
        with self.assertRaisesRegex(JMAError, 'duplicated'):
            check(additional_metadata_receipts=(extra[0], extra[0]))
        with self.assertRaisesRegex(JMAError, 'reviewed dependency'):
            check(additional_metadata_receipts=(inputs()[0].receipt,))

    def test_policy_has_no_implicit_thresholds_and_rejects_invalid_values(self):
        with self.assertRaises(TypeError):
            JMAAgePolicy()
        for name in ('observation_seconds', 'forecast_issue_seconds', 'national_latest_seconds',
                     'metadata_cache_seconds', 'station_lag_seconds'):
            for value in (0, -1, True, 0.5, None, 366 * 86400 + 1):
                with self.subTest(name=name, value=value), self.assertRaises(JMAError):
                    policy(**{name: value})
        with self.assertRaises(JMAError):
            check(now=NOW.replace(tzinfo=None))

    def test_receipt_metadata_and_output_limits_remain_explicit(self):
        forecast, obs, cat = inputs()
        for change in ({'http_status': 302}, {'body_bytes': True}, {'body_sha256': 'bad'},
                       {'retrieved_start_utc': NOW}):
            with self.subTest(change=change), self.assertRaises(JMAError):
                check((replace(forecast, receipt=replace(forecast.receipt, **change)), obs, cat))
        result = check().metadata()
        self.assertFalse(result['native_clock_used_as_source_time'])
        self.assertFalse(result['source_receipts_independently_authenticated'])
        self.assertFalse(result['all_payload_source_dependencies_verified'])
        self.assertFalse(result['native_payload_generated_or_published'])
        json.dumps(result, allow_nan=False)


class HistoricalJMAFreshnessTests(unittest.TestCase):
    def test_actual_dated_bundle_can_be_checked_historically_but_not_retimed_current(self):
        root = Path(__file__).resolve().parents[1] / 'private/forecast'
        first, added = root / 'jma-source-audit-20261028', root / 'jma-association-audit-20261028'
        sources = [(first, n) for n in ('forecast-tokyo', 'amedas-latest', 'amedas-stations',
                   'amedas-point', 'forecast-area-metadata', 'area-metadata', 'forecast-page')]
        sources += [(added, n) for n in ('week_area', 'week_area05', 'week_area_name')]
        if not all((p / (n + '.body')).is_file() and (p / (n + '.json')).is_file() for p, n in sources):
            self.skipTest('historical private JMA source bundle unavailable')
        captured = {}
        for path, name in sources:
            body = (path / (name + '.body')).read_bytes()
            meta = json.loads((path / (name + '.json')).read_bytes())
            def instant(value):
                return datetime.fromtimestamp(value, timezone.utc) if type(value) in (int, float) else datetime.fromisoformat(value)
            r = SourceReceipt(meta['url'], meta['body_sha256'], meta.get('body_bytes', meta.get('bytes')),
                              instant(meta['retrieved_start_utc']), instant(meta['retrieved_end_utc']), meta['status'])
            captured[name] = body, r
        forecast = parse_forecast(*captured['forecast-tokyo'])
        latest = parse_latest_time(*captured['amedas-latest'])
        station_code = captured['amedas-point'][1].url.split('/')[-2]
        station = parse_station(*captured['amedas-stations'], station_code)
        observations = parse_observations(*captured['amedas-point'], station, latest)
        assoc = parse_associations(*(x for n in ('forecast-area-metadata', 'week_area', 'week_area05', 'week_area_name') for x in captured[n]))
        extra = tuple(captured[n][1] for n in ('area-metadata', 'forecast-page'))
        historical_now = max(r.retrieved_end_utc for _, r in captured.values()) + timedelta(seconds=1)
        explicit = policy(observation_seconds=7200, national_latest_seconds=7200)
        selected = observations.records[-1]
        result = check_jma_age(forecast, observations, assoc, report_indices=(0, 1),
            observation_key_jst=selected.source_time_key_jst, now=historical_now, policy=explicit,
            additional_metadata_receipts=extra)
        self.assertEqual(result.checks[0].basis_utc, forecast.reports[0].issued_utc)
        self.assertEqual(next(c for c in result.checks if c.role == 'station_observation').basis_utc, selected.observed_utc)
        self.assertGreater(result.earliest_expiry_utc, historical_now)
        with self.assertRaisesRegex(JMAError, 'stale'):
            check_jma_age(forecast, observations, assoc, report_indices=(0, 1),
                observation_key_jst=selected.source_time_key_jst,
                now=datetime(2026, 11, 7, tzinfo=timezone.utc), policy=explicit,
                additional_metadata_receipts=extra)


if __name__ == '__main__':
    unittest.main()
