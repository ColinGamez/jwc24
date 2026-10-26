"""Synthetic schedules test publication coherency, never provider availability."""
from datetime import datetime, timedelta, timezone
import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from jwc24.hbnj_publication import (HBNJPublicationError, HBNJSnapshotExpired,
                                   HBNJRouteSnapshot, load_hbnj_snapshot, publish_hbnj_snapshot)
from tools.pack_hbnj_guide import make_header, make_epg, make_string, station_maps
from tools import update_hbnj_daily
from jwc24 import hbnj_publication

JST = timezone(timedelta(hours=9))


def fixture(now, marker='A'):
    first = datetime.fromtimestamp(now, JST).replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [(first + timedelta(days=offset)).strftime('%Y%m%d') for offset in range(8)]
    areas, channels, programs, sources = [], [], [], []
    for index in range(54):
        channel = index + 1
        areas.append({'id': 1001 + index, 'name': f'Area {index}',
                      'prefecture_raw': 1, 'channel_ids': [channel]})
        channels.append({'id': channel, 'name': f'Synthetic {channel}'})
        for day in range(8):
            start = first + timedelta(days=day)
            programs.append({'id': channel * 100 + day, 'channel_id': channel,
                             'title': f'Synthetic {marker} {day}', 'description': f'Description {marker}',
                             'start': start.isoformat(), 'end': (start + timedelta(days=1)).isoformat(),
                             'genre_id': 1})
        sources.append({'area_id': 1001 + index, 'channels': 1, 'programs': 8,
                        'source_urls': ['https://synthetic.invalid/'] * 8,
                        'broadcast_dates': dates, 'daily_program_counts': [1] * 8})
    return {'format': 'jwc24_hbnj_guide_v1', 'status': 'ok', 'source': 'synthetic test',
            'days': 8, 'broadcast_date': dates[0], 'broadcast_end_date': dates[-1],
            'collected_at': datetime.fromtimestamp(now - 10, timezone.utc).isoformat(),
            'areas': areas, 'channels': channels, 'programs': programs, 'sources': sources}


def write_fixture(directory, document):
    root = Path(directory)
    guide, payloads = root / 'guide.json', root / 'payloads'
    root.mkdir(parents=True, exist_ok=True)
    payloads.mkdir()
    guide.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    channels, keys = station_maps(document['channels'])
    (payloads / 'header.hdpk').write_bytes(make_header(document, channels, keys))
    (payloads / 'epg.hdpk').write_bytes(make_epg(document, channels, keys))
    (payloads / 'string.hdpk').write_bytes(make_string(document, channels))
    for area in document['areas']:
        selected = {key: channels[key] for key in area['channel_ids']}
        part = dict(document, areas=[area], channels=list(selected.values()),
                    programs=[row for row in document['programs'] if row['channel_id'] in selected])
        out = payloads / 'areas' / str(area['id'])
        out.mkdir(parents=True)
        (out / 'epg.hdpk').write_bytes(make_epg(part, selected, keys))
        (out / 'string.hdpk').write_bytes(make_string(part, selected))
    return guide, payloads


class HBNJPublicationTests(unittest.TestCase):
    now = 1_800_000_000

    def publish(self, guide, payloads, output, **kwargs):
        return publish_hbnj_snapshot(guide, payloads, output, now=self.now,
                                     rights_ref='synthetic fixture rights',
                                     max_collection_age_seconds=3600, **kwargs)

    def test_unprepared_snapshot_cannot_claim_validation_or_serve(self):
        empty = HBNJRouteSnapshot()
        for action in (empty.metadata, lambda: empty.raw_payload('/header.bin', now=self.now)):
            with self.assertRaisesRegex(HBNJPublicationError, 'validated loaded'):
                action()

    def test_initial_metadata_containment_checked_before_reading_redirected_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            report = self.publish(guide, payloads, root / 'out')
            original_resolve = Path.resolve
            outside = root / 'outside-private.json'
            for target in (root / 'out/current.json',
                           root / 'out' / report['generation'] / 'manifest.json',
                           root / 'out' / report['generation'] / 'guide.json'):
                def redirected(path, *args, **kwargs):
                    return outside if path == target else original_resolve(path, *args, **kwargs)
                with self.subTest(target=target.name), \
                        patch.object(Path, 'resolve', new=redirected), \
                        patch.object(hbnj_publication, '_read', wraps=hbnj_publication._read) as reader:
                    with self.assertRaisesRegex(HBNJPublicationError, 'escaped'):
                        load_hbnj_snapshot(root / 'out', now=self.now)
                    self.assertNotIn(outside, [call.args[0] for call in reader.call_args_list])

    def test_old_marker_does_not_permanently_block_an_os_locked_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            out = root / 'out'
            out.mkdir()
            (out / '.publish.lock').write_bytes(b'old crashed marker')
            self.publish(guide, payloads, out)
            self.assertTrue((out / '.publication.lock').is_file())
            load_hbnj_snapshot(out, now=self.now)

    def test_all_regions_load_as_one_immutable_raw_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            report = self.publish(guide, payloads, root / 'out')
            snapshot = load_hbnj_snapshot(root / 'out', now=self.now)
            self.assertEqual(report['routes'], 109)
            self.assertTrue(report['runtime_snapshot_activation_required'])
            for identifier in range(1001, 1055):
                for route, filename in [('epg.bin', 'epg.hdpk'), ('str.bin', 'string.hdpk')]:
                    self.assertEqual(snapshot.raw_payload(f'/{identifier}/{route}', now=self.now),
                                     (payloads / 'areas' / str(identifier) / filename).read_bytes())
            self.assertIsNone(snapshot.raw_payload('/epg.bin', now=self.now))
            self.assertIsNone(snapshot.raw_payload('/1055/epg.bin', now=self.now))
            self.assertEqual(snapshot.raw_payload('/header.bin', now=self.now),
                             (payloads / 'header.hdpk').read_bytes())
            self.assertNotIn('Synthetic', repr(snapshot))
            self.assertFalse(snapshot.metadata()['transport_crypto_or_native_delivery_verified'])
            with self.assertRaises(TypeError):
                snapshot._routes['/header.bin'] = b'replaced'

    def test_pointer_switch_does_not_mix_existing_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = write_fixture(root / 'first', fixture(self.now, 'A'))
            second = write_fixture(root / 'second', fixture(self.now, 'B'))
            self.publish(*first, root / 'out')
            old = load_hbnj_snapshot(root / 'out', now=self.now)
            self.publish(*second, root / 'out')
            new = load_hbnj_snapshot(root / 'out', now=self.now)
            self.assertNotEqual(old.generation, new.generation)
            for identifier in (1001, 1016, 1054):
                path = f'/{identifier}/str.bin'
                self.assertNotEqual(old.raw_payload(path, now=self.now), new.raw_payload(path, now=self.now))
                self.assertEqual(old.raw_payload(path, now=self.now),
                                 (first[1] / 'areas' / str(identifier) / 'string.hdpk').read_bytes())

    def test_failed_validation_preserves_pointer_and_removes_owned_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            self.publish(guide, payloads, root / 'out')
            before = (root / 'out/current.json').read_bytes()
            (payloads / 'areas/1054/string.hdpk').write_bytes(b'broken')
            with self.assertRaisesRegex(HBNJPublicationError, 'validation failed'):
                self.publish(guide, payloads, root / 'out')
            self.assertEqual((root / 'out/current.json').read_bytes(), before)
            self.assertFalse(list((root / 'out').glob('.stage-*')))
            self.assertFalse((root / 'out/.publish.lock').exists())

    def test_pointer_replace_failure_leaves_previous_complete_generation_live(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            self.publish(guide, payloads, root / 'out')
            before = (root / 'out/current.json').read_bytes()
            import os
            replace = os.replace
            def fail_pointer(source, destination):
                if Path(destination).name == 'current.json':
                    raise OSError('synthetic failure')
                return replace(source, destination)
            with patch('jwc24.hbnj_publication.os.replace', side_effect=fail_pointer):
                with self.assertRaises(OSError):
                    self.publish(guide, payloads, root / 'out')
            self.assertEqual((root / 'out/current.json').read_bytes(), before)
            load_hbnj_snapshot(root / 'out', now=self.now)
            self.assertFalse(list((root / 'out').glob('.pointer-*')))

    def test_loader_rejects_file_tampering_and_escaping_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            report = self.publish(guide, payloads, root / 'out')
            (root / 'out' / report['generation'] / 'areas/1001/epg.hdpk').write_bytes(b'tampered')
            with self.assertRaisesRegex(HBNJPublicationError, 'integrity'):
                load_hbnj_snapshot(root / 'out', now=self.now)
            (root / 'out/current.json').write_text('{"schema_version":1,"generation":"../input"}')
            with self.assertRaisesRegex(HBNJPublicationError, 'pointer'):
                load_hbnj_snapshot(root / 'out', now=self.now)

    def test_wall_clock_expiry_during_validation_does_not_switch_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            self.publish(guide, payloads, root / 'out')
            before = (root / 'out/current.json').read_bytes()
            with patch('jwc24.hbnj_publication.time.time', side_effect=[self.now, self.now + 4000]):
                with self.assertRaises(HBNJSnapshotExpired):
                    publish_hbnj_snapshot(guide, payloads, root / 'out',
                                           rights_ref='synthetic fixture', max_collection_age_seconds=3600)
            self.assertEqual((root / 'out/current.json').read_bytes(), before)

    def test_collection_time_is_not_program_time_and_no_retiming(self):
        for kind in ('old_collection', 'future_collection', 'old_schedule', 'wrong_program_zone'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                document = fixture(self.now - 20 * 86400 if kind == 'old_schedule' else self.now)
                if kind == 'old_collection':
                    document['collected_at'] = datetime.fromtimestamp(self.now - 3600, timezone.utc).isoformat()
                elif kind == 'future_collection':
                    document['collected_at'] = datetime.fromtimestamp(self.now + 1, timezone.utc).isoformat()
                elif kind == 'old_schedule':
                    document['collected_at'] = datetime.fromtimestamp(self.now, timezone.utc).isoformat()
                else:
                    document['programs'][0]['start'] = document['programs'][0]['start'].replace('+09:00', '+00:00')
                guide, payloads = write_fixture(root / 'input', document)
                before = guide.read_bytes()
                with self.assertRaises(HBNJPublicationError):
                    self.publish(guide, payloads, root / 'out')
                self.assertEqual(guide.read_bytes(), before)
                self.assertFalse((root / 'out/current.json').exists())

    def test_snapshot_fails_closed_at_exact_source_expiry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide, payloads = write_fixture(root / 'input', fixture(self.now))
            self.publish(guide, payloads, root / 'out')
            snapshot = load_hbnj_snapshot(root / 'out', now=self.now)
            self.assertIsNotNone(snapshot.raw_payload('/header.bin', now=snapshot.expires_unix - 1))
            with self.assertRaises(HBNJSnapshotExpired):
                snapshot.raw_payload('/header.bin', now=snapshot.expires_unix)
            with self.assertRaises(HBNJSnapshotExpired):
                load_hbnj_snapshot(root / 'out', now=snapshot.expires_unix)

    def test_offline_updater_runs_complete_pipeline_without_collector_or_legacy_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = int(time.time())
            guide, _ = write_fixture(root / 'input', fixture(now))
            legacy = root / 'legacy-current'
            legacy.mkdir()
            (legacy / 'epg.hdpk').write_bytes(b'prior generation')
            output = io.StringIO()
            with patch.object(update_hbnj_daily, 'PRIVATE', root / 'staging'), \
                    patch.object(update_hbnj_daily, 'CURRENT', legacy), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(update_hbnj_daily.main([
                    '--coherent', '--guide-file', str(guide), '--output-root', str(root / 'out'),
                    '--rights-ref', 'synthetic fixture', '--max-collection-age-seconds', '3600']), 0)
            self.assertEqual((legacy / 'epg.hdpk').read_bytes(), b'prior generation')
            self.assertEqual(len(list(legacy.iterdir())), 1)
            self.assertIn('runtime_snapshot_activation_required', output.getvalue())
            load_hbnj_snapshot(root / 'out', now=now)

    def test_argument_free_updater_preserves_legacy_daily_call_with_mock_collector(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = fixture(int(time.time()))
            original_run, collection_calls = update_hbnj_daily.run, []
            def synthetic_collection(*arguments):
                if arguments[0] == 'tools/collect_hbnj_all.py':
                    collection_calls.append(arguments)
                    Path(arguments[arguments.index('--out') + 1]).write_text(json.dumps(document), encoding='utf-8')
                else:
                    original_run(*arguments)
            output = io.StringIO()
            with patch.object(update_hbnj_daily, 'PRIVATE', root / 'private'), \
                    patch.object(update_hbnj_daily, 'CURRENT', root / 'current'), \
                    patch.object(update_hbnj_daily, 'SNAPSHOTS', root / 'snapshots'), \
                    patch.object(update_hbnj_daily, 'run', side_effect=synthetic_collection), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(update_hbnj_daily.main([]), 0)
            self.assertEqual(len(collection_calls), 1)
            self.assertEqual(len(list((root / 'current').rglob('*.hdpk'))), 111)
            self.assertEqual(len(list((root / 'private').glob('jwc24-all-*.json'))), 1)
            self.assertFalse((root / 'snapshots').exists())
            self.assertIn('legacy_per_file_experiment', output.getvalue())
            self.assertIn('"coherent_generation_published": false', output.getvalue())

    def test_coherent_mode_requires_evidence_before_collection(self):
        for arguments in (['--coherent'], ['--coherent', '--rights-ref', 'explicit'],
                          ['--legacy', '--rights-ref', 'explicit']):
            with self.subTest(arguments=arguments), patch.object(update_hbnj_daily, 'run') as runner, \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    update_hbnj_daily.main(arguments)
                runner.assert_not_called()
