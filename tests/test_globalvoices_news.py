"""Synthetic source stories are test-only; no provider story corpus is shipped."""
from __future__ import annotations

import contextlib
import dataclasses
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24 import globalvoices_news as gv
from tools.inspect_globalvoices_news import load_capture, main

NOW = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)
URL = "https://jp.globalvoices.org/2026/11/01/42/"
GUID = "https://jp.globalvoices.org/?p=42"
TITLE = "合成テスト専用の記事"
CORE = ('<p>最初の段落。<strong>強調</strong><br>改行後。</p>'
        '<h3>試験見出し</h3><p><a href="https://example.org/source">資料へのリンク</a></p>'
        '<blockquote cite="https://example.org/quote">試験用の引用。</blockquote>'
        '<figure><img src="https://example.org/photo.jpg" alt="合成写真" />'
        '<figcaption>写真のクレジット。</figcaption></figure>'
        '<iframe src="https://example.org/video" title="合成動画"></iframe>'
        '<div class="contributors">校正：<a href="https://jp.globalvoices.org/author/test-proof/">Test Proof</a></div>')


def fixture(core=CORE, *, page_extra="", feed_core=None, language="ja"):
    credits = ('<div class="contributor-name"><span class="credit-label">記者 (English)</span>'
               '<a href="https://globalvoices.org/author/test-author/">Test Author</a></div>'
               '<div class="contributor-name"><span class="credit-label">翻訳 (日本語)</span>'
               '<a href="https://jp.globalvoices.org/author/test-translator/">Test Translator</a></div>')
    page = (f'<html lang="ja"><head><link rel="canonical" href="{URL}">'
            f'<meta property="og:url" content="{URL}"><meta property="og:type" content="article">'
            f'<meta property="og:title" content="{TITLE}"><meta property="og:site_name" content="Global Voices 日本語">'
            '<meta property="article:published_time" content="2026-11-01T03:00:00+0000">'
            '<meta property="article:modified_time" content="2026-11-02T04:00:00+0000">'
            f'{page_extra}</head><body><div class="post-header-meta">'
            '<div class="post-tagline">合成の副題</div>'
            f'<div id="post-header-credit">{credits}</div>'
            '<span class="post-source-date">元記事掲載 2026/10/30</span>'
            '<span class="translation-language post-translation-en"><a href="https://globalvoices.org/2026/10/30/test/">English</a></span>'
            f'</div><div class="post post-42"><div class="entry-container"><div class="entry">{core}</div></div>'
            '<div class="postfooter"><div class="postfooter-credits">'
            f'<a rel="license" href="{gv.LICENSE_URL}">CC BY 3.0</a>{credits}'
            '</div></div></div></body></html>')
    content = ('<p><big class="tagline">合成の副題</big></p>' + (core if feed_core is None else feed_core)
               + '<div class="gv-rss-footer">合成の配信クレジット</div>')
    feed = ('<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
            f'<language>{language}</language><lastBuildDate>Mon, 02 Nov 2026 04:00:00 +0000</lastBuildDate>'
            f'<item><title>{TITLE}</title><link>{URL}</link><guid isPermaLink="false">{GUID}</guid>'
            '<pubDate>Sun, 01 Nov 2026 03:00:00 +0000</pubDate>'
            '<dc:creator>Test Translator</dc:creator><category>合成試験</category>'
            '<description>合成テストの短い概要。</description>'
            f'<content:encoded><![CDATA[{content}]]></content:encoded></item></channel></rss>')
    return feed.encode(), page.encode()


def receipt(body, url):
    return gv.CaptureReceipt.from_body(url, body, NOW, NOW)


def policies():
    body = b'<!DOCTYPE html><html><p>test-only policy capture, not a rights grant</p></html>'
    return tuple((body, receipt(body, url)) for url in gv.POLICY_URLS)


def candidate(feed_body=None, article_body=None, **kwargs):
    default_feed, default_article = fixture()
    fb = default_feed if feed_body is None else feed_body
    ab = default_article if article_body is None else article_body
    feed = gv.parse_feed(fb, receipt(fb, gv.FEED_URL))
    return gv.parse_article(feed, guid=GUID, body=ab, receipt=receipt(ab, URL),
                            policy_documents=kwargs.pop("policy_documents", policies()), **kwargs)


class GlobalVoicesNewsTests(unittest.TestCase):
    def test_full_body_preserves_structure_links_caption_credits_and_roles(self):
        article = candidate()
        self.assertIn("最初の段落。", article.body.text())
        self.assertNotEqual(article.body.text(), article.feed_item.description_html)
        self.assertEqual([n.tag for n in article.body.children],
                         ["p", "h3", "p", "blockquote", "figure", "iframe", "div"])
        self.assertEqual([c.role for c in article.contributors], ["original_author", "japanese_translator"])
        self.assertEqual(article.contributors[0].name, "Test Author")
        self.assertEqual(article.feed_item.creator, "Test Translator")
        self.assertEqual(article.original_publication_date.isoformat(), "2026-10-30")
        self.assertIn("Test Proof", article.contributor_blocks[0].text())
        self.assertIn("CC BY 3.0", article.article_credits[0].text())
        self.assertEqual(article.taglines[0].text(), "合成の副題")
        self.assertEqual(article.translation_links[0].children[0].attr("href"), "https://globalvoices.org/2026/10/30/test/")
        self.assertFalse(any(x.kind == "feed_page_content_difference" for x in article.review_objects))

    def test_media_and_quotes_are_retained_with_pending_states(self):
        article = candidate()
        media = [x for x in article.review_objects if x.kind == "media"]
        self.assertEqual([x.node.tag for x in media], ["img", "iframe"])
        self.assertEqual(next(x.node.text() for x in article.review_objects if x.kind == "quotation"), "試験用の引用。")
        self.assertTrue(all(x.state == "pending" for x in article.review_objects))
        self.assertFalse(article.ready_for_native_publication)
        self.assertFalse(article.source_independently_authenticated)

    def test_unknown_substantive_tags_and_active_attributes_never_disappear(self):
        fb, ab = fixture(core=CORE + '<custom-block onclick="run()">未知の本文<script>run()</script></custom-block>'
                                  '<p><a href="javascript:run()">危険リンク</a></p><!-- rights note --><?source note?>')
        article = candidate(fb, ab)
        self.assertIn("未知の本文run()", article.body.text())
        kinds = [x.kind for x in article.review_objects]
        self.assertGreaterEqual(kinds.count("unhandled_structure"), 3)
        self.assertIn("inert_active_attribute", kinds)
        self.assertIn("unsafe_or_relative_url", kinds)
        self.assertTrue(any(n.tag == "comment" and n.attr("text") == " rights note " for n in article.body.walk()))
        self.assertTrue(any(n.tag == "processing_instruction" and n.attr("text") == "source note?" for n in article.body.walk()))

    def test_feed_page_difference_is_explicit_and_keeps_both_full_bodies(self):
        fb, ab = fixture(feed_core='<p>異なる完全本文。</p>')
        article = candidate(fb, ab)
        self.assertIn("異なる完全本文。", article.syndication_body.text())
        self.assertIn("最初の段落。", article.body.text())
        self.assertIn("feed_page_content_difference", [x.kind for x in article.review_objects])

    def test_provider_dates_and_check_age_do_not_use_fetch_as_publication(self):
        article = candidate()
        metadata = article.metadata(checked_utc=NOW)
        self.assertEqual(metadata["published_utc"], "2026-11-01T03:00:00+00:00")
        self.assertEqual(metadata["modified_utc"], "2026-11-02T04:00:00+00:00")
        self.assertEqual(metadata["publication_age_seconds"], 543600)
        self.assertEqual(metadata["modification_age_seconds"], 453600)
        with self.assertRaises(gv.GlobalVoicesError):
            article.metadata(checked_utc=datetime(2026, 11, 1, tzinfo=timezone.utc))
        with self.assertRaises(gv.GlobalVoicesError):
            article.metadata(checked_utc=datetime(2026, 11, 7))

    def test_literal_en_us_feed_label_is_retained_not_rewritten(self):
        fb, ab = fixture(language="en-US")
        article = candidate(fb, ab)
        self.assertEqual(article.feed_language_label, "en-US")
        self.assertEqual(article.article_html_language, "ja")
        self.assertIn("feed_language_label", [x.kind for x in article.review_objects])

    def test_hash_length_status_route_and_retrieval_bounds_reject(self):
        fb, _ = fixture()
        original = receipt(fb, gv.FEED_URL)
        for bad in (dataclasses.replace(original, body_sha256="0" * 64),
                    dataclasses.replace(original, body_bytes=len(fb) + 1),
                    dataclasses.replace(original, http_status=302),
                    dataclasses.replace(original, url="http://jp.globalvoices.org/feed/"),
                    dataclasses.replace(original, retrieved_start_utc=datetime(2026, 11, 8, tzinfo=timezone.utc))):
            with self.subTest(bad=bad), self.assertRaises(gv.GlobalVoicesError):
                gv.parse_feed(fb, bad)

    def test_xml_dtd_entities_and_duplicate_fields_reject(self):
        fb, _ = fixture()
        for bad in (b'<!DOCTYPE rss [<!ENTITY x "oops">]>' + fb,
                    fb.replace(b'<title>', b'<title>duplicate</title><title>', 1),
                    fb.replace(b'</item>', b'<guid isPermaLink="false">duplicate</guid></item>'),
                    fb.replace(b'<category>', b'<category><nested/>')):
            with self.subTest(case=bad[:100]), self.assertRaises(gv.GlobalVoicesError):
                gv.parse_feed(bad, receipt(bad, gv.FEED_URL))

    def test_rss_dates_need_explicit_seconds_and_timezone(self):
        fb, _ = fixture()
        for replacement in (b'Sun, 01 Nov 2026 03:00 +0000', b'Sun, 01 Nov 2026 03:00:00',
                            b'Sun, 01 Nov 2026 03:00:00 +9999'):
            bad = fb.replace(b'Sun, 01 Nov 2026 03:00:00 +0000', replacement)
            with self.subTest(value=replacement), self.assertRaises(gv.GlobalVoicesError):
                gv.parse_feed(bad, receipt(bad, gv.FEED_URL))

    def test_source_identity_canonical_metadata_and_title_must_match(self):
        fb, ab = fixture()
        changes = ((b'<link rel="canonical"', b'<link rel="alternate"'),
                   (URL.encode(), b'https://evil.example/42/'),
                   (b'property="og:url"', b'property="og:other"'),
                   (TITLE.encode(), b'changed title'),
                   (b'content="article"', b'content="website"'),
                   (b'lang="ja"', b'lang="en"'))
        for old, new in changes:
            with self.subTest(old=old), self.assertRaises(gv.GlobalVoicesError):
                candidate(fb, ab.replace(old, new, 1))
        with self.assertRaises(gv.GlobalVoicesError):
            candidate(fb, ab.replace(b'href="' + URL.encode() + b'"', b'href="' + URL.encode() + b'" href="https://evil.example"', 1))

    def test_unknown_source_license_and_roles_are_explicit_pending(self):
        fb, ab = fixture()
        article = candidate(fb, ab.replace(gv.LICENSE_URL.encode(), b'https://example.org/license')
                            .replace('記者 (English)'.encode(), 'その他'.encode()))
        self.assertIn("unreviewed_license", [x.kind for x in article.review_objects])
        self.assertIn("unclassified_contributor", [x.kind for x in article.review_objects])
        self.assertEqual(article.contributors[0].source_role_label, "その他")

    def test_date_mismatch_future_and_missing_full_entry_reject(self):
        fb, ab = fixture()
        for old, new in ((b'2026-11-01T03:00:00+0000', b'2026-11-01T03:01:00+0000'),
                         (b'2026-11-02T04:00:00+0000', b'2026-11-08T04:00:00+0000'),
                         (b'2026-11-02T04:00:00+0000', b'2026-10-30T04:00:00+0000'),
                         (b'class="entry"', b'class="excerpt"')):
            with self.subTest(old=old), self.assertRaises(gv.GlobalVoicesError):
                candidate(fb, ab.replace(old, new))

    def test_missing_duplicate_or_unverified_policy_capture_reject(self):
        ps = policies()
        for bad in ((), ps[:2], (ps[0], ps[0], ps[2]),
                    ((ps[0][0] + b'x', ps[0][1]), *ps[1:]), (None, *ps[1:])):
            with self.subTest(case=repr(bad)[:50]), self.assertRaises(gv.GlobalVoicesError):
                candidate(policy_documents=bad)

    def test_age_check_cannot_precede_policy_capture(self):
        ps = policies()
        body, rec = ps[0]
        later = dataclasses.replace(rec, retrieved_start_utc=NOW + timedelta(days=1),
                                    retrieved_end_utc=NOW + timedelta(days=1))
        article = candidate(policy_documents=((body, later), *ps[1:]))
        with self.assertRaises(gv.GlobalVoicesError):
            article.metadata(checked_utc=NOW)
        self.assertFalse(article.metadata(checked_utc=NOW + timedelta(days=1))["ready_for_native_publication"])

    def test_inert_duplicate_nonsemantic_attributes_are_retained_for_review(self):
        fb, ab = fixture(core=CORE + '<p data-id="a" data-id="b">重複属性の本文</p>')
        article = candidate(fb, ab)
        obj = next(x for x in article.review_objects if x.kind == "ambiguous_attributes")
        self.assertEqual(obj.node.attributes, (("data-id", "a"), ("data-id", "b")))
        with self.assertRaises(gv.GlobalVoicesError):
            obj.node.attr("data-id")

    def test_size_depth_node_count_and_unicode_bounds(self):
        fb, ab = fixture()
        with self.assertRaises(gv.GlobalVoicesError):
            gv.CaptureReceipt.from_body(gv.FEED_URL, b'x' * (gv.MAX_BYTES + 1), NOW, NOW)
        for core in ('<div>' * 130 + 'text' + '</div>' * 130, '<p>nul\0</p>'):
            bad_feed, bad_page = fixture(core=core)
            with self.assertRaises(gv.GlobalVoicesError):
                candidate(bad_feed, bad_page)
        with patch.object(gv, "MAX_NODES", 5), self.assertRaises(gv.GlobalVoicesError):
            candidate(fb, ab)
        with self.assertRaises(gv.GlobalVoicesError):
            gv.parse_feed(fb + b'\xff', receipt(fb + b'\xff', gv.FEED_URL))

    def test_pending_flags_cannot_be_upgraded_by_constructor_or_replace(self):
        article = candidate()
        for key, value in (("rights_state", "cleared"), ("rendering_state", "verified"),
                           ("ready_for_native_publication", True), ("source_independently_authenticated", True)):
            with self.subTest(field=key), self.assertRaises((ValueError, TypeError)):
                dataclasses.replace(article, **{key: value})
        with self.assertRaises((ValueError, TypeError)):
            dataclasses.replace(article.review_objects[0], state="cleared")

    def test_cli_is_offline_count_only_and_rejects_paths_and_bad_receipts(self):
        fb, ab = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            captures = {"feed": (fb, receipt(fb, gv.FEED_URL)), "sample-42": (ab, receipt(ab, URL)),
                        **{name: capture for name, capture in zip(("japanese-policy", "republishing-guidelines", "read-share"), policies())}}
            for name, (body, rec) in captures.items():
                (root / (name + ".body")).write_bytes(body)
                metadata = dict(url=rec.url, body_sha256=rec.body_sha256, body_bytes=rec.body_bytes,
                                retrieved_start_utc=NOW.isoformat(), retrieved_end_utc=NOW.isoformat(),
                                status=200, complete=True, failure=None)
                (root / (name + ".json")).write_text(json.dumps(metadata), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(["--capture-dir", directory, "--article-name", "sample-42", "--guid", GUID,
                               "--checked-utc", NOW.isoformat()])
            self.assertEqual(result, 0)
            self.assertNotIn(TITLE, output.getvalue())
            self.assertNotIn("Test Author", output.getvalue())
            self.assertNotIn("example.org", output.getvalue())
            self.assertFalse(json.loads(output.getvalue())["ready_for_native_publication"])
            with self.assertRaises(gv.GlobalVoicesError):
                load_capture(root, "../outside")
            (root / "feed.json").write_text('{"complete":true,"complete":true}', encoding="utf-8")
            with self.assertRaises(gv.GlobalVoicesError):
                load_capture(root, "feed")

    def test_private_actual_capture_replay_when_present(self):
        root = Path(__file__).resolve().parents[1] / "private/news/globalvoices-source-audit-20261107"
        if not (root / "sample-65795.body").is_file():
            self.skipTest("optional private official source capture is absent")
        fb, fr = load_capture(root, "feed")
        ab, ar = load_capture(root, "sample-65795")
        article = gv.parse_article(gv.parse_feed(fb, fr), guid="https://jp.globalvoices.org/?p=65795", body=ab,
                                   receipt=ar, policy_documents=tuple(load_capture(root, name) for name in
                                   ("japanese-policy", "republishing-guidelines", "read-share")))
        self.assertEqual(article.contributors[0].name, "Oiwan Lam")
        self.assertEqual(article.contributors[1].name, "Yasuhisa Miyata")
        self.assertEqual(article.original_publication_date.isoformat(), "2026-08-12")
        self.assertEqual(article.published_utc.isoformat(), "2026-11-02T07:06:38+00:00")
        self.assertEqual(article.modified_utc.isoformat(), "2026-11-04T02:34:30+00:00")
        self.assertEqual(article.feed_language_label, "en-US")
        self.assertEqual(article.article_html_language, "jp")
        self.assertEqual(len(article.contributor_blocks), 1)
        self.assertEqual(sum(x.kind == "media" for x in article.review_objects), 3)
        self.assertEqual(sum(x.kind == "quotation" for x in article.review_objects), 2)
        self.assertNotIn("feed_page_content_difference", [x.kind for x in article.review_objects])
        self.assertFalse(article.ready_for_native_publication)


if __name__ == "__main__":
    unittest.main()
