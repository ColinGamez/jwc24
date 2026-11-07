"""Actual XML slots -> independent C/F values, without identity/time invention."""
from dataclasses import replace
from datetime import date, datetime
import json
from pathlib import Path
import unittest

from jwc24.jma_measurements import ROUNDING
from jwc24.jma_weather import JMAError
from jwc24.jma_xml_projection import project_xml_temperature
from jwc24.jma_xml_temperatures import XMLDocumentReceipt, parse_daily_temperatures
from tests.test_jma_xml_temperatures import edit, first_temperature, parse


def project(source=None, **changes):
    args = dict(series_index=0, station_code='00001', ref_id='1',
                expected_role='daytime_maximum', expected_date=date(2026, 1, 2), rounding=ROUNDING)
    args.update(changes)
    return project_xml_temperature(parse() if source is None else source, **args)


def token(value):
    return parse(edit(lambda root: setattr(first_temperature(root), 'text', value)))


def change_selected(source, mutator):
    series = source.series[0]
    point = series.points[0]
    prop = point.properties[0]
    prop = replace(prop, values=(mutator(prop.values[0]),))
    point = replace(point, properties=(prop,) + point.properties[1:])
    return replace(source, series=(replace(series, points=(point,)),))


class XMLProjectionTests(unittest.TestCase):
    def test_actual_roles_use_refid_not_monotonic_order_or_ordinal_low_high_pairs(self):
        high = project()
        low = project(ref_id='3', expected_role='morning_minimum', expected_date=date(2026, 1, 3))
        self.assertEqual((high.temperature_celsius, high.temperature_fahrenheit), (0, 32))
        self.assertEqual((low.temperature_celsius, low.temperature_fahrenheit), (-2, 28))
        general = project(ref_id='2', expected_role='maximum_temperature')
        self.assertIsNone(general.native_daily_role)
        self.assertEqual((general.temperature_celsius, general.temperature_fahrenheit), (-128, -128))
        self.assertIn('general_maximum_is_not_a_native_daily_extremum', general.unavailable_reasons)
        with self.assertRaises(JMAError):
            project(ref_id='2', expected_role='morning_minimum')

    def test_each_unit_rounds_from_original_decimal_and_overflow_rejects(self):
        for value, expected in (('20.5', (21, 69)), ('-0.5', (-1, 31)),
                                ('-1.5', (-2, 29)), ('-40', (-40, -40)),
                                ('18.0000000000000000001', (18, 64))):
            result = project(token(value))
            self.assertEqual((result.temperature_celsius, result.temperature_fahrenheit), expected)
            self.assertEqual(result.source_value.raw, value)
        for value in ('100', '-128', '1000001'):
            with self.assertRaises(JMAError):
                project(token(value))

    def test_full_source_identity_values_and_all_provider_dates_remain(self):
        source = parse()
        value = project(source)
        self.assertIs(value.source, source)
        self.assertIs(value.source_receipt, source.receipt)
        self.assertIs(value.station, source.series[0].points[0])
        self.assertIs(value.source_value, source.series[0].points[0].properties[0].values[0])
        self.assertEqual((value.report_datetime, value.control_datetime, value.target_datetime),
                         (source.report_datetime, source.control_datetime, source.target_datetime))
        self.assertEqual((value.issued_utc, value.transmitted_utc),
                         (source.issued_utc, source.transmitted_utc))
        self.assertFalse(hasattr(value, 'native_location'))
        self.assertFalse(hasattr(value, 'source_age_accepted'))

    def test_source_status_kind_offices_and_header_qualifiers_do_not_disappear(self):
        source = replace(parse(), status='Synthetic exercise status', info_type='Synthetic cancellation',
                         publishing_office='Synthetic publishing office',
                         header_metadata_json='{"source_qualifier":"preserved"}')
        result = project(source)
        self.assertIs(result.source, source)
        self.assertEqual(result.source.status, source.status)
        self.assertEqual(result.source.info_type, source.info_type)
        self.assertEqual(result.source.header_metadata_json, source.header_metadata_json)
        self.assertEqual(result.source.series[0].source_group_type, source.series[0].source_group_type)
        # Field conversion is not whole-source eligibility or publication.
        self.assertFalse(hasattr(result, 'source_eligibility_accepted'))

    def test_unknown_unit_type_or_qualifier_is_unavailable_not_unqualified_celsius(self):
        def unit(root):
            first_temperature(root).set('unit', 'Unknown unit')
        def kind(root):
            first_temperature(root).set('type', 'Unknown type')
        def qualifier(root):
            first_temperature(root).set('condition', 'Unknown qualifier')
        for mutator, reason in ((unit, 'unreviewed_temperature_unit'),
                                (kind, 'unreviewed_temperature_type'),
                                (qualifier, 'qualified_or_inconsistent_temperature_attributes')):
            source = parse(edit(mutator))
            value = project(source)
            self.assertIn(reason, value.unavailable_reasons)
            self.assertEqual((value.temperature_celsius, value.temperature_fahrenheit), (-128, -128))
            self.assertIs(value.source_value, source.series[0].points[0].properties[0].values[0])

    def test_missing_or_unknown_tokens_never_become_a_zero_reading(self):
        for raw in (None, '', 'unknown', 'NaN'):
            value = project(token(raw))
            self.assertTrue(value.unavailable_reasons)
            self.assertEqual((value.temperature_celsius, value.temperature_fahrenheit), (-128, -128))

    def test_reviewed_description_attribute_survives_as_separate_source_display_metadata(self):
        description = 'Original source display description'
        source = parse(edit(lambda root: first_temperature(root).set('description', description)))
        result = project(source)
        self.assertEqual(result.temperature_celsius, 0)
        self.assertFalse(result.unavailable_reasons)
        self.assertIn(('description', description), result.source_value.attributes)

    def test_malformed_period_dates_or_reference_binding_reject(self):
        source = parse()
        for change in (dict(duration='PT24H'), dict(datetime='2026-01-02T00:00:00+09:00'),
                       dict(valid_utc=datetime(2026, 1, 2, 9))):
            selected = source.series[0].time_definitions[0]
            altered = replace(selected, **change)
            series = replace(source.series[0], time_definitions=(altered,) + source.series[0].time_definitions[1:])
            changed = replace(source, series=(series,))
            changed = change_selected(changed, lambda value: replace(value, target=altered))
            with self.subTest(change=change), self.assertRaises(JMAError):
                project(changed)
        with self.assertRaises(JMAError):
            project(change_selected(source, lambda value: replace(value, numeric_value=99)))

    def test_explicit_selection_no_first_station_fallback_or_boolean_indices(self):
        for changes in (dict(series_index=True), dict(station_code='00002'), dict(ref_id='99'),
                        dict(expected_role='Invented role'), dict(expected_date=date(2026, 1, 3)),
                        dict(rounding='nearest'), dict(series_index=-1)):
            with self.subTest(changes=changes), self.assertRaises(JMAError):
                project(**changes)
        source = parse()
        series = replace(source.series[0], points=source.series[0].points * 2)
        with self.assertRaises(JMAError):
            project(replace(source, series=(series,)))


class ActualXMLProjectionTests(unittest.TestCase):
    def test_both_genuine_morning_reports_keep_12_extrema_and_four_general_slots_separate(self):
        folder = Path(__file__).resolve().parents[1] / 'private/forecast/jma-shape-audit-20261107'
        names = ('tokyo-05', 'tokyo-11')
        if not all((folder / (name + suffix)).is_file() for name in names for suffix in ('.body', '.json')):
            self.skipTest('Optional private genuine morning VPFD51 captures unavailable')
        for name in names:
            meta = json.loads((folder / (name + '.json')).read_bytes())
            receipt = XMLDocumentReceipt(meta['url'], meta['body_sha256'], meta['body_bytes'],
                datetime.fromisoformat(meta['retrieved_start_utc']), datetime.fromisoformat(meta['retrieved_end_utc']),
                meta['status'])
            source = parse_daily_temperatures((folder / (name + '.body')).read_bytes(), receipt)
            converted = retained = 0
            for index, series in enumerate(source.series):
                for point in series.points:
                    for prop in point.properties:
                        for raw in prop.values:
                            result = project_xml_temperature(source, series_index=index,
                                station_code=point.station_code, ref_id=raw.ref_id,
                                expected_role=raw.semantic_role, expected_date=raw.target.target_date_jst,
                                rounding=ROUNDING)
                            self.assertIs(result.source_value, raw)
                            self.assertEqual(result.report_datetime, source.report_datetime)
                            self.assertEqual(result.source_series_index, 2)
                            if raw.semantic_role == 'maximum_temperature':
                                retained += 1
                                self.assertIsNone(result.native_daily_role)
                                self.assertEqual(result.temperature_celsius, -128)
                            else:
                                converted += 1
                                self.assertEqual(result.temperature_celsius, raw.numeric_value)
                                self.assertFalse(result.unavailable_reasons)
            self.assertEqual((converted, retained), (12, 4))


if __name__ == '__main__':
    unittest.main()
