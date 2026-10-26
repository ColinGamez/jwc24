"""Synthetic record encoding; no publisher copy, images or production feeds."""
import base64
import contextlib
from copy import deepcopy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import zlib

from jwc24.forecast import WII_EPOCH_UNIX
from jwc24.news import NewsFormatError, inspect_news, inspect_news_envelope
from jwc24.news_bundle import inspect_news_bundle
from jwc24.news_publication import build_news_publication, load_news_publication, write_news_publication
from jwc24.news_records import encode_news_records
from jwc24.news_server import create_news_server
from tools.build_news_records import main, write_record_build


def explicit_records():
    """All editorial/header choices explicit and synthetic; never a feed fallback."""
    return {
        'schema_version': 1, 'evidence_ref': 'urn:jwc24:synthetic:record-test',
        'rights_ref': 'urn:jwc24:synthetic:no-provider-content',
        'header': {'version': 512, 'updated_timestamp': 10000, 'close_timestamp': 11000,
                   'secondary_timestamp': 10000, 'country_code': 1, 'language_code': 0,
                   'supported_languages': [0], 'flags_45_46': [0, 0], 'byte_47': 30,
                   'opaque_21_23': '000000', 'opaque_92_95': '01e00000',
                   'server_message': None},
        'topics': [{'name': None, 'article_links': [[10000, 0x11223344]]},
                   {'name': 'Synthetic category', 'article_links': [[10000, 0x11223344]]}],
        'articles': [{'identifier': 0x11223344, 'source_index': 0, 'location_index': 0,
                      'picture_timestamp': 10000, 'picture_index': 0,
                      'published_timestamp': 9000, 'updated_timestamp': 9900,
                      'title': 'Synthetic headline \u65e5\u672c\u8a9e \U0001f30f',
                      'body': '  Synthetic body\n\u672c\u6587\t\U0001f30f  '}],
        'sources': [{'logo_flag': 1, 'position': 1, 'reserved_u16': 0, 'picture': None,
                     'name': 'Synthetic source', 'copyright': 'Synthetic credit'}],
        'locations': [{'name': 'Synthetic location', 'latitude_word': -32768,
                       'longitude_word': 32767, 'country_code': 1, 'region_code': 2,
                       'location_code': 3, 'zoom_byte': 6, 'opaque_padding': '123456'}],
        'images': [{'credit': 'Synthetic image credit', 'caption': 'Synthetic caption',
                    'picture': {'encoding': 'native-image-bytes',
                                'data_base64': base64.b64encode(b'synthetic-not-an-image').decode()}}],
        'headlines': ['Explicit synthetic ticker'],
    }


class NewsRecordEncodingTests(unittest.TestCase):
    def test_all_tables_preserve_supplied_text_dates_and_opaque_bytes(self):
        spec = explicit_records()
        frozen = deepcopy(spec)
        raw = encode_news_records(spec)
        self.assertEqual(spec, frozen)
        item = inspect_news(raw)
        article = item.articles[0]
        self.assertEqual((item.topics, item.sources, item.locations, item.images, item.headlines),
                         (2, 1, 1, 1, 1))
        self.assertEqual(article.headline, spec['articles'][0]['title'])
        self.assertEqual(article.text, spec['articles'][0]['body'])
        self.assertEqual((article.published_timestamp, article.updated_timestamp), (9000, 9900))
        self.assertEqual(struct.unpack_from('>I', raw, 4)[0], len(raw))
        self.assertEqual(struct.unpack_from('>I', raw, 8)[0], zlib.crc32(raw[12:]))
        location_offset = struct.unpack_from('>I', raw, 80)[0]
        self.assertEqual(struct.unpack_from('>hh', raw, location_offset + 4), (-32768, 32767))
        self.assertEqual(raw[location_offset + 13:location_offset + 16], b'\x12\x34\x56')
        self.assertEqual(raw[47], 30)
        self.assertEqual(raw[92:96], b'\x01\xe0\0\0')
        for position in (56, 64, 72, 80, 88, 100):
            self.assertEqual(struct.unpack_from('>I', raw, position)[0] % 4, 0)
        self.assertNotIn('Synthetic', json.dumps(item.metadata()))

    def test_explicit_absences_and_supplied_source_picture(self):
        spec = explicit_records()
        spec['images'] = spec['locations'] = []
        spec['headlines'] = []
        spec['articles'][0].update(location_index=None, picture_timestamp=0, picture_index=None)
        spec['sources'][0].update(logo_flag=0, picture={
            'encoding': 'native-image-bytes', 'data_base64': base64.b64encode(b'explicit-source-image').decode()})
        raw = encode_news_records(spec)
        self.assertEqual(inspect_news(raw).articles[0].location_index, 0xFFFFFFFF)
        source_offset = struct.unpack_from('>I', raw, 72)[0]
        self.assertEqual(raw[source_offset], 0)
        self.assertEqual(struct.unpack_from('>I', raw, source_offset + 4)[0], 21)

    def test_message_is_only_emitted_when_explicitly_supplied(self):
        spec = explicit_records()
        self.assertEqual(struct.unpack_from('>I', encode_news_records(spec), 48)[0], 0)
        spec['header']['server_message'] = 'Explicit synthetic message'
        self.assertTrue(inspect_news(encode_news_records(spec)).server_message_present)

    def test_unknown_fields_missing_evidence_and_implicit_header_defaults_reject(self):
        for mutate in (lambda s: s.pop('rights_ref'), lambda s: s.update(evidence_ref=''),
                       lambda s: s['header'].pop('byte_47'),
                       lambda s: s['header'].update(guessed_genre='private-marker'),
                       lambda s: s['locations'][0].pop('opaque_padding'),
                       lambda s: s.update(schema_version=True)):
            spec = explicit_records()
            mutate(spec)
            with self.assertRaises(NewsFormatError) as caught:
                encode_news_records(spec)
            self.assertNotIn('private-marker', str(caught.exception))

    def test_missing_body_invalid_utf16_nul_and_native_body_limit_reject(self):
        for value in ('', '   ', 'private\0marker', '\ud800', 'x' * 10000, None):
            spec = explicit_records()
            spec['articles'][0]['body'] = value
            with self.subTest(kind=type(value).__name__), self.assertRaises(NewsFormatError):
                encode_news_records(spec)
        spec['articles'][0]['body'] = 'x' * 9999
        self.assertEqual(len(inspect_news(encode_news_records(spec)).articles[0].text), 9999)

    def test_local_references_duplicates_and_unsupported_image_shape_reject(self):
        mutations = (
            lambda s: s['articles'].append(deepcopy(s['articles'][0])),
            lambda s: s['articles'][0].update(source_index=2),
            lambda s: s['articles'][0].update(location_index=2),
            lambda s: s['articles'][0].update(picture_index=2),
            lambda s: s['articles'][0].update(picture_timestamp=0),
            lambda s: s['topics'][0].update(article_links=[[10000, 9]]),
            lambda s: s.update(topics=[]),
            lambda s: s['images'][0]['picture'].update(encoding='url'),
            lambda s: s['images'][0]['picture'].update(data_base64='not base64!'),
            lambda s: s['sources'][0].update(logo_flag=0),
        )
        for mutate in mutations:
            spec = explicit_records()
            mutate(spec)
            with self.assertRaises(NewsFormatError):
                encode_news_records(spec)

    def test_integer_language_coordinate_and_count_bounds_reject_without_wrapping(self):
        for mutate in (lambda s: s['header'].update(version=0x10000),
                       lambda s: s['header'].update(supported_languages=[0] * 16),
                       lambda s: s['header'].update(flags_45_46=[0, 2]),
                       lambda s: s['articles'][0].update(identifier=True),
                       lambda s: s['locations'][0].update(latitude_word=-32769),
                       lambda s: s.update(articles=[{}] * 4097)):
            spec = explicit_records()
            mutate(spec)
            with self.assertRaises(NewsFormatError):
                encode_news_records(spec)

    def test_cross_snapshot_references_resolve_only_in_complete_explicit_bundle(self):
        first = explicit_records()
        second = explicit_records()
        second['header'].update(updated_timestamp=10001, secondary_timestamp=10001)
        second['topics'][0]['article_links'] = [[10000, 0x11223344], [10001, 0x11223344]]
        second['topics'][1]['article_links'] = [[10001, 0x11223344]]
        # Its actual image remains in the explicitly supplied earlier snapshot.
        raw_first, raw_second = encode_news_records(first), encode_news_records(second)
        result = inspect_news_bundle([raw_first] + [raw_second] * 23)
        self.assertEqual(result.distinct_snapshots, 2)
        self.assertGreater(result.cross_buffer_image_references, 0)
        with self.assertRaises(NewsFormatError):
            inspect_news_bundle([raw_second] * 24)


class NewsRecordBuildTests(unittest.TestCase):
    def test_atomic_new_build_records_exact_private_evidence_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'generation'
            spec = explicit_records()
            document = json.dumps(spec).encode()
            result = write_record_build(document, destination)
            raw = (destination / 'news.raw').read_bytes()
            manifest = json.loads((destination / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['payload_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(manifest['specification_sha256'], hashlib.sha256(document).hexdigest())
            self.assertEqual(manifest['evidence_ref'], spec['evidence_ref'])
            self.assertEqual(manifest['rights_ref'], spec['rights_ref'])
            self.assertFalse(result['signed_or_activated'])
            self.assertNotIn(spec['evidence_ref'], json.dumps(result))
            with self.assertRaises(NewsFormatError):
                write_record_build(document, destination)
            self.assertEqual(raw, (destination / 'news.raw').read_bytes())

    def test_bad_specification_or_failed_rename_never_publishes_partial_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for data in (b'{}', b'{"a":1,"a":2}', b'{"a":NaN}', bytes([0xFF])):
                with self.assertRaises(NewsFormatError):
                    write_record_build(data, root / 'generation')
                self.assertEqual(list(root.iterdir()), [])
            with patch('tools.build_news_records.os.rename', side_effect=OSError('private marker')):
                with self.assertRaises(OSError):
                    write_record_build(json.dumps(explicit_records()).encode(), root / 'generation')
            self.assertEqual(list(root.iterdir()), [])

    def test_cli_failure_has_no_source_path_or_content(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(main(['--input', 'private-path-marker', '--output-dir', 'unused']), 1)
        self.assertEqual(out.getvalue(), '')
        self.assertNotIn('private-path-marker', err.getvalue())


@unittest.skipUnless(shutil.which('openssl'), 'Explicit generated signing keys require OpenSSL')
class NewsRecordsToPublicationTests(unittest.TestCase):
    def test_records_build_sign_publish_reload_and_binary_http_preserve_actual_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private, public = root / 'private.pem', root / 'public.pem'
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                            'rsa_keygen_bits:2048', '-out', str(private)], check=True,
                           capture_output=True, timeout=30)
            subprocess.run(['openssl', 'pkey', '-in', str(private), '-pubout', '-out', str(public)],
                           check=True, capture_output=True, timeout=15)
            spec = explicit_records()
            raw = encode_news_records(spec)
            now = WII_EPOCH_UNIX + 10000 * 60
            publication = build_news_publication(
                [raw] * 24, private_key=private, public_key=public, route_prefix='/v2/0/001',
                source_refs=[spec['evidence_ref']] * 24, rights_ref=spec['rights_ref'],
                current_unix_timestamp=now)
            write_news_publication(root / 'publication', publication, current_unix_timestamp=now)
            loaded = load_news_publication(root / 'publication', public_key=public,
                                           current_unix_timestamp=now)
            listener = create_news_server(('127.0.0.1', 0), loaded, clock=lambda: now)
            worker = threading.Thread(target=listener.serve_forever, daemon=True)
            worker.start()
            connection = http.client.HTTPConnection('127.0.0.1', listener.server_port, timeout=5)
            try:
                connection.request('GET', '/v2/0/001/news.bin.00')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                encoded = response.read()
                self.assertEqual(encoded, loaded.payloads[0])
                article = inspect_news_envelope(encoded).articles[0]
                self.assertEqual(article.text, spec['articles'][0]['body'])
                self.assertEqual((article.published_timestamp, article.updated_timestamp), (9000, 9900))
            finally:
                connection.close()
                listener.shutdown()
                listener.server_close()
                worker.join(5)
            self.assertFalse(worker.is_alive())


class NewsRecordNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (Path(os.environ.get('APPDATA', ''))
                / 'Dolphin Emulator/Wii/title/00010002/4841474a/content/0000000b.app')
        if not path.is_file():
            raise unittest.SkipTest('Private original Japanese News v7 executable unavailable')
        try:
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional original-code verification dependency unavailable')
        cls.source = path.read_bytes()

    def test_original_complete_validator_accepts_generated_all_table_records_without_pruning(self):
        from tools.verify_news_native import verify_news_buffers
        absent_media = explicit_records()
        absent_media.update(sources=[], locations=[], images=[], headlines=[])
        absent_media['articles'][0].update(source_index=None, location_index=None,
                                           picture_timestamp=0, picture_index=None)
        for spec in (explicit_records(), absent_media):
            raw = encode_news_records(spec)
            result = verify_news_buffers(self.source, [raw] * 24)
            self.assertEqual(result['status'], 0)
            self.assertEqual(result['mutated_slots'], [])
            self.assertTrue(result['input_and_stack_guards_verified'])


if __name__ == '__main__':
    unittest.main()
