import unittest
from jwc24.demae_text import inspect_native_text, prepare_native_display


class NativeTextTests(unittest.TestCase):
    def test_explicit_punctuation_projection_preserves_original_and_rejects_other_glyphs(self):
        source = 'A～B'
        result = prepare_native_display(source)
        self.assertEqual(result['display_text'], 'A～B')
        self.assertEqual(result['substitutions'], 0)
        self.assertEqual(source, 'A～B')
        self.assertEqual(prepare_native_display('①')['display_text'], '①')
        self.assertIsNone(prepare_native_display('bad\x01')['display_text'])
    def test_codec_difference_and_normalization_are_diagnostics_only(self):
        value = '①'
        report = inspect_native_text(value)
        self.assertFalse(report['strict_shift_jis'])
        self.assertTrue(report['cp932'])
        self.assertTrue(report['nfkc_strict_shift_jis'])
        self.assertEqual(value, '①')
        emoji = inspect_native_text('😀')
        self.assertFalse(emoji['nfkc_strict_shift_jis'])
        self.assertEqual(emoji['unsupported_codepoints'], ['U+1F600'])
        self.assertTrue(inspect_native_text('a\x01')['xml_controls'])
        with self.assertRaises(ValueError):
            inspect_native_text('a' * 4097)
