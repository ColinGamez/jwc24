"""Explicit four-meaning replacement policy; no network or synthetic UI assets."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unittest

from jwc24.jma_conditions import (
    CLIENT_BYTES, CLIENT_SHA256, ConditionCatalog, ConditionCatalogEntry,
    JMAConditionUnavailable, JMAUnknownCondition, JMAUnsupportedCondition,
    SUPPORTED, _literal_entries, parse_condition_catalog, project_daily_condition,
)
from jwc24.jma_weather import FORECAST_PAGE, JMAError, SourceReceipt, parse_forecast
from tests.test_jma_weather import NOW, encoded, forecast_fixture, receipt, FORECAST_URL


def catalog():
    entries = tuple(ConditionCatalogEntry(code, code + '.svg', code + '.svg', code,
                                        label, 'Synthetic test label')
                    for code, (_, label) in SUPPORTED.items())
    entries += (ConditionCatalogEntry('350', '300.svg', '300.svg', '300',
                                      '\u96e8\u3067\u96f7\u3092\u4f34\u3046', 'RAIN AND THUNDER'),)
    return ConditionCatalog(entries, SourceReceipt(FORECAST_PAGE, CLIENT_SHA256,
                                                   CLIENT_BYTES, NOW, NOW))


def forecast(code='100', *, description='Source description with regional qualifications'):
    data = forecast_fixture()
    for report in data:
        area = report['timeSeries'][0]['areas'][0]
        area['weatherCodes'][0] = code
        if description is not ...:
            area['weathers'] = [description, None]
    body = encoded(data)
    return parse_forecast(body, receipt(FORECAST_URL, body))


def project(source=None, **changes):
    values = dict(report_index=1, series_index=0, area_code='130010', target_index=0,
                  catalog=catalog())
    values.update(changes)
    return project_daily_condition(forecast() if source is None else source, **values)


class JMAConditionTests(unittest.TestCase):
    def test_four_reviewed_meanings_use_distinct_original_graphical_selectors(self):
        for code, (selector, label) in SUPPORTED.items():
            value = project(forecast(code))
            self.assertEqual((value.dictionary_row.code_primary, value.dictionary_row.code_secondary,
                              value.dictionary_row.text), (int(code), selector, label))
            self.assertLess(value.dictionary_row.code_secondary, 0x8000)

    def test_exact_source_dates_area_description_and_both_receipts_survive(self):
        source, original_catalog = forecast(), catalog()
        value = project(source, catalog=original_catalog)
        report = source.reports[1]
        self.assertEqual(value.report_datetime, report.report_datetime)
        self.assertEqual(value.issued_utc, report.issued_utc)
        self.assertEqual(value.target_datetime, report.time_series[0].time_defines[0])
        self.assertEqual(value.valid_utc, report.time_series[0].valid_times_utc[0])
        self.assertEqual(value.raw_weather_description, 'Source description with regional qualifications')
        self.assertTrue(value.description_field_present)
        self.assertIs(value.forecast_receipt, source.receipt)
        self.assertIs(value.catalog_receipt, original_catalog.receipt)
        self.assertEqual(value.raw_weather_code, '100')
        self.assertEqual(value.area_code, '130010')

    def test_absent_empty_and_null_descriptions_remain_distinct(self):
        for description in (..., '', None):
            value = project(forecast(description=description))
            self.assertEqual(value.description_field_present, description is not ...)
            self.assertEqual(value.raw_weather_description, None if description is ... else description)

    def test_unknown_unsupported_and_missing_are_distinct_with_no_fallback(self):
        for code, error in (('350', JMAUnsupportedCondition), ('999', JMAUnknownCondition),
                            ('', JMAConditionUnavailable), (None, JMAConditionUnavailable)):
            with self.assertRaises(error):
                project(forecast(code))

    def test_explicit_selection_never_chooses_first_area_or_wraps_negative_indices(self):
        for changes in (dict(report_index=-1), dict(target_index=True), dict(series_index=1),
                        dict(target_index=9), dict(area_code='130020'), dict(report_index=99)):
            with self.subTest(changes=changes), self.assertRaises(JMAError):
                project(**changes)

    def test_ambiguous_or_altered_catalog_cannot_change_mapping_or_label(self):
        original = catalog()
        bad = (replace(original, entries=original.entries + (original.entries[0],)),
               replace(original, entries=('untyped',)),
               replace(original, entries=(replace(original.entries[0], japanese_label='Invented'),)))
        for value in bad:
            with self.assertRaises(JMAError):
                project(catalog=value)

    def test_literal_parser_is_data_only_bounded_and_rejects_duplicates(self):
        good = b'R.TELOPS={100:["100.svg","500.svg","100","X","CLEAR"]}'
        self.assertEqual(_literal_entries(good)[0].code, '100')
        bad = (good + good, good[:-1], good.replace(b'"X"', b'function(){return "X"}'),
               b'R.TELOPS={100:["a","b","c","d","e"],100:["a","b","c","d","e"]}',
               good.replace(b'"X"', b'"\\ud800"'), b'R.TELOPS={100:["a"]}',
               b'X' * (512 * 1024 + 1))
        for body in bad:
            with self.assertRaises(JMAError):
                _literal_entries(body)

    def test_altered_unreviewed_client_rejects_even_with_self_consistent_receipt(self):
        body = b'R.TELOPS={100:["100.svg","500.svg","100","X","CLEAR"]}'
        evidence = SourceReceipt(FORECAST_PAGE, hashlib.sha256(body).hexdigest(), len(body), NOW, NOW)
        with self.assertRaises(JMAError):
            parse_condition_catalog(body, evidence)


class JMAConditionCapturedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1] / 'private/forecast/jma-source-audit-20261028'
        if not (cls.root / 'forecast-page.body').is_file():
            raise unittest.SkipTest('Optional pinned historical JMA client capture unavailable')
        body = (cls.root / 'forecast-page.body').read_bytes()
        meta = json.loads((cls.root / 'forecast-page.json').read_text(encoding='utf-8'))
        evidence = SourceReceipt(meta['url'], meta['body_sha256'], meta['bytes'],
            datetime.fromtimestamp(meta['retrieved_start_utc'], timezone.utc),
            datetime.fromtimestamp(meta['retrieved_end_utc'], timezone.utc), meta['status'])
        cls.catalog = parse_condition_catalog(body, evidence)

    def test_all_118_actual_source_codes_are_supported_or_explicitly_unmapped(self):
        self.assertEqual(len(self.catalog.entries), 118)
        count = 0
        for entry in self.catalog.entries:
            if entry.code in SUPPORTED:
                self.assertEqual(project(forecast(entry.code), catalog=self.catalog).dictionary_row.text,
                                 entry.japanese_label)
                count += 1
            else:
                with self.assertRaises(JMAUnsupportedCondition):
                    project(forecast(entry.code), catalog=self.catalog)
        self.assertEqual(count, 4)

    def test_actual_historical_dated_forecast_projects_12_and_reports_21_unmapped(self):
        if not (self.root / 'forecast-tokyo.body').is_file():
            self.skipTest('Optional paired historical forecast capture unavailable')
        body = (self.root / 'forecast-tokyo.body').read_bytes()
        meta = json.loads((self.root / 'forecast-tokyo.json').read_text(encoding='utf-8'))
        evidence = SourceReceipt(meta['url'], meta['body_sha256'], meta['bytes'],
            datetime.fromtimestamp(meta['retrieved_start_utc'], timezone.utc),
            datetime.fromtimestamp(meta['retrieved_end_utc'], timezone.utc), meta['status'])
        source = parse_forecast(body, evidence)
        accepted = unsupported = 0
        for report_index, report in enumerate(source.reports):
            for series_index, series in enumerate(report.time_series):
                for area in series.areas:
                    codes = next((f for f in area.fields if f.name == 'weatherCodes'), None)
                    if codes is None:
                        continue
                    for target_index, code in enumerate(codes.values):
                        arguments = dict(report_index=report_index, series_index=series_index,
                                         area_code=area.code, target_index=target_index,
                                         catalog=self.catalog)
                        if code.raw in SUPPORTED:
                            projected = project_daily_condition(source, **arguments)
                            self.assertEqual(projected.report_datetime, report.report_datetime)
                            self.assertEqual(projected.target_datetime, series.time_defines[target_index])
                            self.assertEqual(projected.raw_weather_code, code.raw)
                            accepted += 1
                        else:
                            with self.assertRaises(JMAUnsupportedCondition):
                                project_daily_condition(source, **arguments)
                            unsupported += 1
        self.assertEqual((accepted, unsupported), (12, 21))


if __name__ == '__main__':
    unittest.main()
