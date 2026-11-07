"""Metadata-only resource checks, with optional pinned private original proofs."""
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from tools.verify_forecast_resources import (_archive_member, _texture_metadata, main,
                                             verify_membership, verify_selectors)


def texture_fixture(*, width=1, height=1, format_=5, pixels=56, palette=0):
    raw = bytearray(88)
    struct.pack_into('>5I', raw, 0, 0x0020AF30, 1, 12, 20, palette)
    struct.pack_into('>HHII', raw, 20, height, width, format_, pixels)
    return bytes(raw)


def archive_fixture(names=(b'TPLWeather.tpl.LZ',)):
    count = len(names) + 1
    strings = b'\0' + b''.join(name + b'\0' for name in names)
    files = 32 + count * 12 + len(strings)
    raw = bytearray(files + len(names))
    struct.pack_into('>4I', raw, 0, 0x55AA382D, 32, files - 32, files)
    struct.pack_into('>III', raw, 32, 0x01000000, 0, count)
    cursor = 1
    for index, name in enumerate(names, 1):
        struct.pack_into('>III', raw, 32 + index * 12, cursor, files + index - 1, 1)
        cursor += len(name) + 1
    raw[32 + count * 12:files] = strings
    raw[files:] = b'X' * len(names)
    return bytes(raw)


class ForecastResourcePublicTests(unittest.TestCase):
    def test_untrusted_identity_refused_before_execution_backend_import(self):
        with patch.dict('sys.modules', {'unicorn': None}):
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_selectors(b'private-marker')
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_membership(b'private-marker', b'private-marker')

    def test_cli_redacts_input_path_and_no_report_on_failure(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(Path, 'open', side_effect=OSError('private-marker')), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = main(['private-marker'] * 3)
        self.assertEqual(result, 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('private-marker', errors.getvalue())

    def test_archive_unique_exact_member_and_bounded_tables(self):
        self.assertEqual(_archive_member(archive_fixture()), (b'X', 2))
        for names in ((b'other',), (b'TPLWeather.tpl.LZ', b'TPLWeather.tpl.LZ')):
            with self.assertRaisesRegex(ValueError, 'one exact'):
                _archive_member(archive_fixture(names))
        for offset, value in ((4, 0xFFFFFFFF), (12, 34), (40, 0xFFFFFFFF), (48, 0xFFFFFF)):
            raw = bytearray(archive_fixture())
            struct.pack_into('>I', raw, offset, value)
            with self.assertRaises(ValueError):
                _archive_member(bytes(raw))

    def test_texture_tiled_padding_is_included_in_bounds_and_hash(self):
        for format_, expected in ((2, 32), (3, 32), (5, 32)):
            row = _texture_metadata(texture_fixture(format_=format_))[0]
            self.assertEqual(row['pixel_bytes'], expected)
            self.assertEqual(row['width'], 1)
            raw = bytearray(texture_fixture(format_=format_))
            raw[87] = 1
            self.assertNotEqual(_texture_metadata(bytes(raw))[0]['pixel_sha256'], row['pixel_sha256'])
        self.assertEqual(_texture_metadata(texture_fixture(width=8, height=5, format_=2, pixels=56) + bytes(32))[0]['pixel_bytes'], 64)

    def test_texture_refuses_overlap_out_of_range_dimensions_palette_and_format(self):
        fixtures = (texture_fixture(pixels=52), texture_fixture(pixels=0xFFFFFFFF),
                    texture_fixture(width=0), texture_fixture(height=513),
                    texture_fixture(format_=4), texture_fixture(palette=64),
                    texture_fixture()[:87])
        for raw in fixtures:
            with self.subTest(size=len(raw)):
                with self.assertRaises(ValueError):
                    _texture_metadata(raw)
        two = bytearray(164)
        struct.pack_into('>7I', two, 0, 0x0020AF30, 2, 12, 28, 0, 64, 0)
        struct.pack_into('>HHII', two, 28, 1, 1, 5, 100)
        struct.pack_into('>HHII', two, 64, 1, 1, 5, 132)
        self.assertEqual(len(_texture_metadata(bytes(two))), 2)
        duplicate_header, shared_pixels = bytearray(two), bytearray(two)
        struct.pack_into('>I', duplicate_header, 20, 28)
        struct.pack_into('>I', shared_pixels, 72, 100)
        for raw in (duplicate_header, shared_pixels):
            with self.assertRaisesRegex(ValueError, 'overlap'):
                _texture_metadata(bytes(raw))


class ForecastResourceOriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1] / (
            'private/forecast/snapshots/pre-jwc24-wad-install-20260802-054502/'
            'title-00010002-4841464a/content')
        if not all((cls.root / name).is_file() for name in ('title.tmd', '00000010.app', '0000000d.app')):
            raise unittest.SkipTest('Pinned private HAFJ original resource set unavailable')

    def test_original_tmd_archive_tpl_and_every_texture_boundary(self):
        report = verify_membership((self.root / 'title.tmd').read_bytes(),
                                   (self.root / '00000010.app').read_bytes())
        self.assertTrue(report['retained_tmd_hash_size_match'])
        self.assertFalse(report['nintendo_signature_or_independent_provenance_verified'])
        self.assertEqual(len(report['textures']), 27)
        self.assertEqual(report['textures'][4]['pixel_sha256'],
                         'f971aeb3c14d8aea0391bfd5b39a67b396d2b8bf5e788a03509a22729abccabd')
        self.assertTrue(report['all_texture_regions_bounded_and_disjoint'])
        self.assertFalse(any('pixels' in row or 'rgba' in row for row in report['textures']))

    def test_actual_original_selector_definitions_and_two_integer_substitution_blocks(self):
        if importlib.util.find_spec('unicorn') is None:
            self.skipTest('Optional native execution dependency unavailable')
        report = verify_selectors((self.root / '0000000d.app').read_bytes())
        self.assertEqual(report['mapped_selectors'], 59)
        self.assertEqual(report['original_substitution_cases'], 162)
        rows = {row['selector']: row['unflagged_texture_indices'] for row in report['definitions']}
        self.assertEqual({key: rows[key] for key in (1, 10, 19, 26, 33, 101)},
                         {1: [4], 10: [0], 19: [2], 26: [3], 33: [5], 101: [15]})
        self.assertEqual(report['nonzero_flag_texture_substitutions'], {'4': 1, '15': 11})
        self.assertTrue(report['source_and_guards_unchanged'])
        self.assertFalse(report['full_float_composition_executed'])
        self.assertFalse(report['gx_drawing_or_native_ui_executed'])
        self.assertFalse(report['provider_or_jma_semantic_mapping_verified'])


if __name__ == '__main__':
    unittest.main()
