"""Pinned original text consumers with synthetic strings, no publisher copy."""
import json
import os
from pathlib import Path
import struct
import unittest

from jwc24.news_records import encode_news_records
from tests.test_news_records import explicit_records
from tools.verify_news_article_text import verify_news_article_text


class ArticleTextInputTests(unittest.TestCase):
    def test_wrong_executable_rejects_before_optional_dependencies_without_echo(self):
        with self.assertRaises(ValueError) as caught:
            verify_news_article_text(b"private original", b"private article",
                                     expected_title="secret title", expected_body="secret body",
                                     expected_source_name="secret author", expected_copyright="secret license",
                                     glyph_width=8, font_height=16)
        self.assertNotIn("private", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))


class NativeArticleTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (Path(os.environ.get("APPDATA", ""))
                / "Dolphin Emulator/Wii/title/00010002/4841474a/content/0000000b.app")
        if not path.is_file():
            raise unittest.SkipTest("Optional private Japanese News v7 executable absent")
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("Optional original-code verification dependencies absent")
        cls.source = path.read_bytes()

    def verify(self, document=None, **overrides):
        document = explicit_records() if document is None else document
        article = document["articles"][0]
        selected = None if article["source_index"] is None else document["sources"][article["source_index"]]
        arguments = dict(expected_title=article["title"], expected_body=article["body"],
                         expected_source_name=None if selected is None else selected["name"],
                         expected_copyright=None if selected is None else selected["copyright"],
                         glyph_width=8, font_height=16)
        arguments.update(overrides)
        return verify_news_article_text(self.source, encode_news_records(document), **arguments)

    def test_full_constructor_separate_body_and_copyright_native_handoffs(self):
        result = self.verify()
        self.assertTrue(result["complete_constructor_finished"])
        self.assertTrue(result["title_body_copyright_wire_pointers_verified"])
        self.assertTrue(result["three_original_layout_suffix_handoffs_verified"])
        self.assertTrue(result["original_formatter_prefix_and_utf16_unit_walk_verified"])
        self.assertTrue(result["fixture_guards_and_unchanged_input_verified"])
        self.assertFalse(result["complete_ui_or_formatter_method_executed"])
        self.assertFalse(result["provider_attribution_or_rights_compliance_verified"])
        self.assertFalse(result["real_font_metrics_or_rendering_verified"])

    def test_literal_url_and_markup_are_retained_as_utf16_units_not_claimed_links(self):
        document = explicit_records()
        text = '試験本文\nhttps://example.invalid/license\n<a href="x">literal</a>\t\u00a0 🌏'
        document["articles"][0]["body"] = text
        document["sources"][0]["copyright"] = "Synthetic author / translator / license URL"
        result = self.verify(document)
        self.assertEqual(result["counts"]["glyph_unit_iterations"], len(text.encode("utf-16-be")) // 2)
        self.assertEqual(result["counts"]["line_feed_dispatches"], 2)
        self.assertEqual(result["counts"]["nonbreaking_space_conversions"], 1)
        self.assertEqual(result["counts"]["font_width_calls"], 63)
        self.assertEqual(result["counts"]["font_height_calls"], 65)
        self.assertTrue(result["exact_units_except_original_nbsp_conversion_verified"])
        self.assertFalse(result["literal_url_clickability_verified"])
        self.assertFalse(result["html_or_rich_article_support_verified"])
        report = json.dumps(result)
        for marker in ("example.invalid", "Synthetic author", "試験本文"):
            self.assertNotIn(marker, report)

    def test_line_breaks_tabs_nbsp_surrogates_and_empty_copyright(self):
        for text in ("試\n", "試\t", "試\u00a0", "🌏", "段落一。\n\n段落二。", "Ａ１A1\t字\u3000。"):
            with self.subTest(text_units=len(text.encode("utf-16-be")) // 2):
                document = explicit_records()
                document["articles"][0]["body"] = text
                document["sources"][0]["copyright"] = ""
                result = self.verify(document)
                self.assertEqual(result["counts"]["glyph_unit_iterations"], len(text.encode("utf-16-be")) // 2)
                self.assertEqual(result["counts"]["line_feed_dispatches"], text.count("\n"))
                self.assertEqual(result["counts"]["nonbreaking_space_conversions"], text.count("\u00a0"))

    def test_absent_source_remains_null_not_fabricated_attribution(self):
        document = explicit_records()
        document["sources"] = document["locations"] = document["images"] = []
        document["articles"][0].update(source_index=None, location_index=None, picture_timestamp=0, picture_index=None)
        result = self.verify(document)
        self.assertTrue(result["three_original_layout_suffix_handoffs_verified"])
        self.assertEqual(result["counts"]["allocations"], 3)

    def test_small_glyph_capacity_traps_original_native_write(self):
        document = explicit_records()
        document["articles"][0]["body"] = "Four"
        with self.assertRaisesRegex(ValueError, "write exceeds fixture bounds"):
            self.verify(document, glyph_capacity=2)

    def test_changed_body_expectation_and_invalid_wire_pointer_do_not_pass(self):
        document = explicit_records()
        with self.assertRaisesRegex(ValueError, "explicit synthetic expectation"):
            self.verify(document, expected_body="Different body")
        raw = bytearray(encode_news_records(document))
        offset = struct.unpack_from(">I", raw, 64)[0]
        struct.pack_into(">I", raw, offset + 40, len(raw) + 4)
        with self.assertRaisesRegex(ValueError, "outside synthetic input"):
            verify_news_article_text(self.source, bytes(raw),
                                     expected_title=document["articles"][0]["title"],
                                     expected_body=document["articles"][0]["body"],
                                     expected_source_name=document["sources"][0]["name"],
                                     expected_copyright=document["sources"][0]["copyright"],
                                     glyph_width=8, font_height=16)

    def test_explicit_font_policy_input_bounds_and_text_limits(self):
        for change in ({"glyph_width": True}, {"font_height": 0}, {"glyph_capacity": 0},
                       {"expected_body": "X" * 4097}, {"expected_body": "nul\0body"},
                       {"expected_copyright": None}):
            with self.subTest(fields=list(change)), self.assertRaises(ValueError):
                self.verify(**change)
        document = explicit_records()
        document["articles"][0]["body"] = "日本語。\n" * 100
        result = self.verify(document, glyph_width=12, font_height=24)
        self.assertEqual(result["counts"]["glyph_unit_iterations"], 500)
        self.assertEqual(result["counts"]["line_feed_dispatches"], 100)


if __name__ == "__main__":
    unittest.main()
