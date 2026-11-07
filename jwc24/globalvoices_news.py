"""Bounded Global Voices Japanese source candidates, without native publication.

Publisher policy: https://globalvoices.org/about/global-voices-attribution-policy/
Japanese articles: https://jp.globalvoices.org/feed/
Captured hashes establish bytes, not independent authentication or blanket rights.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
import re
from typing import Iterator
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

MAX_BYTES = 2 * 1024 * 1024
MAX_NODES = 50000
MAX_DEPTH = 128
MAX_ITEMS = 100
FEED_URL = "https://jp.globalvoices.org/feed/"
POLICY_URLS = (
    "https://jp.globalvoices.org/about/%E8%A8%98%E4%BA%8B%E3%81%AE%E8%BB%A2%E8%BC%89%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6/",
    "https://globalvoices.org/about/global-voices-attribution-policy/",
    "https://jp.globalvoices.org/read-share/",
)
LICENSE_URL = "https://creativecommons.org/licenses/by/3.0/deed.ja"
ARTICLE_RE = r"https://jp\.globalvoices\.org/([0-9]{4})/([0-9]{2})/([0-9]{2})/([1-9][0-9]{0,11})/"
UTC = timezone.utc


class GlobalVoicesError(ValueError):
    """The captured source is malformed, ambiguous or outside this contract."""


def _need(ok: bool, message: str) -> None:
    if not ok:
        raise GlobalVoicesError(message)


def _utc(value: datetime) -> datetime:
    _need(isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None,
          "timezone-qualified datetime required")
    return value.astimezone(UTC)


def _text(value: str, *, maximum: int = MAX_BYTES, nonempty: bool = False) -> str:
    _need(isinstance(value, str) and len(value) <= maximum and "\0" not in value,
          "invalid or overlong source text")
    try:
        value.encode("utf-16-be", errors="strict")
    except UnicodeError as exc:
        raise GlobalVoicesError("invalid Unicode source text") from exc
    _need(not nonempty or bool(value.strip()), "empty source text")
    return value


def _article_id(url: str) -> str:
    _need(isinstance(url, str), "article URL required")
    match = re.fullmatch(ARTICLE_RE, url)
    _need(match is not None, "unreviewed canonical article route")
    try:
        datetime(*map(int, match.groups()[:3]))
    except ValueError as exc:
        raise GlobalVoicesError("invalid article route date") from exc
    return match.group(4)


def _safe_url(url: str) -> bool:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and bool(parts.hostname) and parts.username is None
                and parts.password is None and parts.port in (None, 443) and "\\" not in url)
    except ValueError:
        return False


def _route(url: str) -> None:
    _need(isinstance(url, str), "source URL required")
    if url not in (FEED_URL, *POLICY_URLS):
        _article_id(url)


@dataclass(frozen=True)
class CaptureReceipt:
    url: str
    body_sha256: str
    body_bytes: int
    retrieved_start_utc: datetime
    retrieved_end_utc: datetime
    http_status: int = 200

    @classmethod
    def from_body(cls, url: str, body: bytes, started: datetime, ended: datetime,
                  *, status: int = 200) -> CaptureReceipt:
        _route(url)
        _need(type(body) is bytes and 0 < len(body) <= MAX_BYTES, "invalid captured body size")
        start, end = _utc(started), _utc(ended)
        _need(start <= end and type(status) is int and status == 200, "invalid capture bounds or status")
        return cls(url, hashlib.sha256(body).hexdigest(), len(body), start, end, status)

    def verify(self, body: bytes) -> None:
        actual = CaptureReceipt.from_body(self.url, body, self.retrieved_start_utc,
                                          self.retrieved_end_utc, status=self.http_status)
        _need(type(self.body_bytes) is int and actual == self, "capture body or receipt mismatch")


@dataclass(frozen=True)
class ContentNode:
    """Inert data only. Tags, attributes, text and order are never executable HTML."""
    tag: str
    attributes: tuple[tuple[str, str | None], ...] = field(repr=False)
    children: tuple[ContentNode | str, ...] = field(repr=False)

    def attr(self, key: str) -> str | None:
        values = [value for name, value in self.attributes if name == key]
        _need(len(values) <= 1, "ambiguous HTML attribute")
        return values[0] if values else None

    def has_class(self, name: str) -> bool:
        return name in (self.attr("class") or "").split()

    def walk(self) -> Iterator[ContentNode]:
        yield self
        for child in self.children:
            if isinstance(child, ContentNode):
                yield from child.walk()

    def text(self) -> str:
        """Diagnostic exact text-node concatenation; not a native body renderer."""
        return "".join(child.text() if isinstance(child, ContentNode) else child for child in self.children)


class _MutableNode:
    def __init__(self, tag: str, attributes=()):
        self.tag, self.attributes, self.children = tag, tuple(attributes), []

    def freeze(self) -> ContentNode:
        return ContentNode(self.tag, self.attributes, tuple(
            child.freeze() if isinstance(child, _MutableNode) else child for child in self.children))


class _HTML(HTMLParser):
    VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _MutableNode("document")
        self.stack = [self.root]
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        _need(self.count <= MAX_NODES and len(self.stack) < MAX_DEPTH, "HTML structure bound exceeded")
        _need(len(attrs) <= 64, "excessive HTML attributes")
        for key, value in attrs:
            _text(key, maximum=128, nonempty=True)
            if value is not None:
                _text(value, maximum=32768)
        node = _MutableNode(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, data):
        _text(data)
        self.stack[-1].children.append(data)

    def handle_comment(self, data):
        _text(data)
        self.count += 1
        _need(self.count <= MAX_NODES, "HTML structure bound exceeded")
        self.stack[-1].children.append(_MutableNode("comment", (("text", data),)))

    def handle_pi(self, data):
        _text(data)
        self.count += 1
        _need(self.count <= MAX_NODES, "HTML structure bound exceeded")
        self.stack[-1].children.append(_MutableNode("processing_instruction", (("text", data),)))

    def unknown_decl(self, data):
        raise GlobalVoicesError("unsupported HTML declaration")

    def handle_decl(self, decl):
        _need(decl.lower() == "doctype html", "unsupported HTML declaration")
        self.count += 1
        _need(self.count <= MAX_NODES, "HTML structure bound exceeded")
        self.stack[-1].children.append(_MutableNode("declaration", (("text", decl),)))


def _html(text: str) -> ContentNode:
    _text(text)
    parser = _HTML()
    try:
        parser.feed(text)
        parser.close()
    except (AssertionError, RecursionError) as exc:
        raise GlobalVoicesError("malformed HTML") from exc
    return parser.root.freeze()


def _decode(body: bytes) -> str:
    try:
        return _text(body.decode("utf-8", errors="strict"))
    except UnicodeError as exc:
        raise GlobalVoicesError("source must be UTF-8") from exc


def _one(values, label: str):
    values = list(values)
    _need(len(values) == 1, "missing or duplicate " + label)
    return values[0]


def _xml_field(element, name: str) -> str:
    child = _one(element.findall(name), "RSS field")
    _need(len(child) == 0, "nested RSS scalar")
    return _text(child.text or "", nonempty=True)


def _rfc_date(text: str) -> datetime:
    _need(bool(re.fullmatch(r"[A-Z][a-z]{2}, [0-9]{2} [A-Z][a-z]{2} [0-9]{4} "
                            r"[0-9]{2}:[0-9]{2}:[0-9]{2} [+-][0-9]{4}", text)),
          "RSS datetime must include seconds and numeric timezone")
    try:
        return _utc(parsedate_to_datetime(text))
    except (TypeError, ValueError, OverflowError) as exc:
        raise GlobalVoicesError("invalid RSS date") from exc


def _iso_date(text: str) -> datetime:
    _need(bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:?[0-9]{2})", text)),
          "invalid complete source datetime")
    try:
        return _utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError as exc:
        raise GlobalVoicesError("invalid complete source datetime") from exc


@dataclass(frozen=True)
class FeedItem:
    identifier: str
    guid: str
    guid_is_permalink: str
    canonical_url: str
    title: str = field(repr=False)
    description_html: str = field(repr=False)
    content_html: str = field(repr=False)
    creator: str = field(repr=False)
    categories: tuple[str, ...] = field(repr=False)
    published_raw: str
    published_utc: datetime


@dataclass(frozen=True)
class FeedSnapshot:
    receipt: CaptureReceipt
    language: str
    last_build_raw: str
    last_build_utc: datetime
    items: tuple[FeedItem, ...] = field(repr=False)


def parse_feed(body: bytes, receipt: CaptureReceipt) -> FeedSnapshot:
    _need(isinstance(receipt, CaptureReceipt), "capture receipt required")
    receipt.verify(body)
    _need(receipt.url == FEED_URL, "wrong feed route")
    text = _decode(body)
    _need(re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE) is None, "XML declarations/entities are forbidden")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise GlobalVoicesError("malformed RSS XML") from exc
    _need(root.tag == "rss", "RSS root required")
    count = 0
    stack = [(root, 0)]
    while stack:
        element, depth = stack.pop()
        count += 1
        _need(count <= MAX_NODES and depth < MAX_DEPTH, "RSS structure bound exceeded")
        stack.extend((child, depth + 1) for child in element)
    channel = _one(root.findall("channel"), "RSS channel")
    language = _xml_field(channel, "language")
    last_raw = _xml_field(channel, "lastBuildDate")
    last = _rfc_date(last_raw)
    _need(last <= receipt.retrieved_end_utc, "future feed build date")
    entries = channel.findall("item")
    _need(0 < len(entries) <= MAX_ITEMS, "unsupported feed item count")
    items = []
    for entry in entries:
        _need(all(len(x) == 0 for x in entry.findall("category")), "nested RSS category")
        url = _xml_field(entry, "link")
        identifier = _article_id(url)
        guid_node = _one(entry.findall("guid"), "RSS GUID")
        guid = _xml_field(entry, "guid")
        _need(guid == "https://jp.globalvoices.org/?p=" + identifier and guid_node.attrib == {"isPermaLink": "false"},
              "unsupported or mismatched RSS identity")
        published_raw = _xml_field(entry, "pubDate")
        published = _rfc_date(published_raw)
        _need(published <= last and published <= receipt.retrieved_end_utc, "future or inconsistent RSS publication")
        items.append(FeedItem(identifier, guid, "false", url,
                              _xml_field(entry, "title"), _xml_field(entry, "description"),
                              _xml_field(entry, "{http://purl.org/rss/1.0/modules/content/}encoded"),
                              _xml_field(entry, "{http://purl.org/dc/elements/1.1/}creator"),
                              tuple(_text(x.text or "", nonempty=True) for x in entry.findall("category")),
                              published_raw, published))
    _need(len({x.guid for x in items}) == len(items) and len({x.canonical_url for x in items}) == len(items),
          "duplicate feed identity")
    return FeedSnapshot(receipt, language, last_raw, last, tuple(items))


@dataclass(frozen=True)
class Contributor:
    role: str
    source_role_label: str
    name: str
    profile_url: str


@dataclass(frozen=True)
class ReviewObject:
    kind: str
    node: ContentNode = field(repr=False)
    reason: str
    state: str = field(default="pending", init=False)


@dataclass(frozen=True)
class SourceArticle:
    provider: str
    identifier: str
    guid: str
    canonical_url: str
    source_name: str
    article_html_language: str
    feed_language_label: str
    title: str = field(repr=False)
    published_raw: str
    modified_raw: str
    published_utc: datetime
    modified_utc: datetime
    feed_item: FeedItem = field(repr=False)
    body: ContentNode = field(repr=False)
    syndication_body: ContentNode = field(repr=False)
    header_metadata: ContentNode = field(repr=False)
    taglines: tuple[ContentNode, ...] = field(repr=False)
    contributors: tuple[Contributor, ...] = field(repr=False)
    contributor_blocks: tuple[ContentNode, ...] = field(repr=False)
    article_credits: tuple[ContentNode, ...] = field(repr=False)
    original_date_blocks: tuple[ContentNode, ...] = field(repr=False)
    original_publication_date: date | None
    translation_links: tuple[ContentNode, ...] = field(repr=False)
    observed_license_uris: tuple[str, ...]
    policy_receipts: tuple[CaptureReceipt, ...]
    feed_receipt: CaptureReceipt
    article_receipt: CaptureReceipt
    review_objects: tuple[ReviewObject, ...] = field(repr=False)
    rights_state: str = field(default="pending_component_review", init=False)
    rendering_state: str = field(default="pending_native_attribution_and_body_rendering", init=False)
    ready_for_native_publication: bool = field(default=False, init=False)
    source_independently_authenticated: bool = field(default=False, init=False)

    def metadata(self, *, checked_utc: datetime) -> dict:
        checked = _utc(checked_utc)
        _need(checked >= max(x.retrieved_end_utc for x in
                             (self.feed_receipt, self.article_receipt, *self.policy_receipts)),
              "check time precedes source capture")
        return dict(provider=self.provider, article_identifier=self.identifier,
                    published_utc=self.published_utc.isoformat(), modified_utc=self.modified_utc.isoformat(),
                    publication_age_seconds=(checked - self.published_utc).total_seconds(),
                    modification_age_seconds=(checked - self.modified_utc).total_seconds(),
                    body_nodes=sum(1 for _ in self.body.walk()),
                    body_text_characters=len(self.body.text()), contributor_count=len(self.contributors),
                    additional_contributor_blocks=len(self.contributor_blocks),
                    original_publication_date=(self.original_publication_date.isoformat()
                                               if self.original_publication_date else None),
                    pending_objects={kind: sum(x.kind == kind for x in self.review_objects)
                                     for kind in sorted({x.kind for x in self.review_objects})},
                    policy_capture_count=len(self.policy_receipts), rights_state=self.rights_state,
                    feed_language_label=self.feed_language_label, article_html_language=self.article_html_language,
                    rendering_state=self.rendering_state, ready_for_native_publication=False,
                    source_independently_authenticated=False, native_payload_generated=False)


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_article(feed: FeedSnapshot, *, guid: str, body: bytes, receipt: CaptureReceipt,
                  policy_documents: tuple[tuple[bytes, CaptureReceipt], ...]) -> SourceArticle:
    """Recover a complete, non-ready supplemental source candidate from captures.

    Policy pages are retained as verified byte receipts, never treated as blanket
    item/component clearance. This API cannot generate native News records.
    """
    _need(isinstance(feed, FeedSnapshot) and isinstance(guid, str), "feed snapshot and exact GUID required")
    item = _one((x for x in feed.items if x.guid == guid), "selected feed item")
    _need(isinstance(receipt, CaptureReceipt), "capture receipt required")
    receipt.verify(body)
    _need(receipt.url == item.canonical_url, "article receipt and feed identity differ")
    _need(type(policy_documents) is tuple and len(policy_documents) == len(POLICY_URLS), "three reviewed policy captures required")
    policies = []
    for pair in policy_documents:
        _need(type(pair) is tuple and len(pair) == 2 and isinstance(pair[1], CaptureReceipt), "invalid policy capture pair")
        document, policy_receipt = pair
        policy_receipt.verify(document)
        _need(policy_receipt.url in POLICY_URLS, "unreviewed policy route")
        _html(_decode(document))
        policies.append(policy_receipt)
    _need({x.url for x in policies} == set(POLICY_URLS), "missing or repeated policy capture")
    page = _html(_decode(body))
    nodes = tuple(page.walk())
    html_language = _one((x.attr("lang") for x in nodes if x.tag == "html"), "article HTML language")
    _need(html_language in ("jp", "ja", "ja-JP"), "unreviewed article HTML language")
    canonical = _one((x.attr("href") for x in nodes if x.tag == "link" and x.attr("rel") == "canonical"), "canonical link")
    _need(canonical == item.canonical_url, "canonical identity mismatch")

    def meta(key):
        value = _one((x.attr("content") for x in nodes if x.tag == "meta" and x.attr("property") == key), key)
        return _text(value, nonempty=True)

    _need(meta("og:url") == canonical and meta("og:type") == "article", "article identity metadata mismatch")
    _need(meta("og:title") == item.title, "feed and article titles differ")
    source_name = meta("og:site_name")
    published_raw, modified_raw = meta("article:published_time"), meta("article:modified_time")
    published, modified = _iso_date(published_raw), _iso_date(modified_raw)
    _need(published == item.published_utc and published <= modified <= receipt.retrieved_end_utc,
          "source publication or modification dates inconsistent")
    post = _one((x for x in nodes if x.has_class("post-" + item.identifier) and x.has_class("post")), "article container")
    entry = _one((x for x in post.walk() if x.has_class("entry")), "complete article entry")
    _text(entry.text(), nonempty=True)
    header = _one((x for x in nodes if x.has_class("post-header-meta")), "article header metadata")
    credit = _one((x for x in header.walk() if x.attr("id") == "post-header-credit"), "article byline")
    contributors = []
    for group in (x for x in credit.walk() if x.has_class("contributor-name")):
        label = _one((x for x in group.walk() if x.has_class("credit-label")), "contributor role").text()
        link = _one((x for x in group.walk() if x.tag == "a" and _compact(x.text())), "contributor name")
        role = ("original_author" if re.fullmatch(r"記者\s*\([^()]+\)", label) else
                "japanese_translator" if label == "翻訳 (日本語)" else "unclassified")
        url = link.attr("href")
        _need(_safe_url(url) and bool(re.fullmatch(r"https://(?:jp\.)?globalvoices\.org/author/[A-Za-z0-9_-]+/", url)),
              "invalid contributor profile link")
        contributors.append(Contributor(role, _text(label, nonempty=True), _text(link.text(), nonempty=True), url))
    _need(bool(contributors) and len(contributors) <= 32, "missing or excessive article contributors")
    licenses = tuple(dict.fromkeys(x.attr("href") for x in post.walk() if x.tag == "a" and x.attr("rel") == "license"))
    _need(bool(licenses) and all(_safe_url(x) for x in licenses), "article license URI missing or unsafe")
    reviews = []
    if feed.language not in ("ja", "ja-JP", "jp"):
        reviews.append(ReviewObject("feed_language_label", header, "feed language label differs from the Japanese article HTML label; both retained"))
    article_credits = tuple(x for x in post.walk() if x.has_class("postfooter-credits"))
    original_dates = tuple(x for x in header.walk() if x.has_class("post-source-date"))
    original_date = None
    if len(original_dates) == 1:
        match = re.fullmatch(r"元記事掲載\s+([0-9]{4})/([0-9]{2})/([0-9]{2})", original_dates[0].text().strip())
        if match:
            try:
                original_date = date(*map(int, match.groups()))
            except ValueError as exc:
                raise GlobalVoicesError("invalid displayed original publication date") from exc
    if original_dates and original_date is None:
        reviews.append(ReviewObject("unclassified_original_date", header, "displayed original date retained without inventing a timestamp"))
    if not article_credits:
        reviews.append(ReviewObject("missing_footer_credits", post, "article footer credits could not be identified"))
    recognized = frozenset("div p br h1 h2 h3 h4 h5 h6 a em strong b i u s del ins span big small sup sub ul ol li dl dt dd blockquote pre code img iframe figure figcaption hr".split())
    for node in entry.walk():
        if len({key for key, _ in node.attributes}) != len(node.attributes):
            reviews.append(ReviewObject("ambiguous_attributes", node, "duplicate attributes retained without selecting a rendering interpretation"))
        if node.tag in ("img", "iframe", "video", "audio", "embed", "object", "picture", "source"):
            reviews.append(ReviewObject("media", node, "component rights and faithful native representation unverified"))
        if node.tag == "blockquote":
            reviews.append(ReviewObject("quotation", node, "third-party quoted material and attribution require review"))
        if node.tag not in recognized:
            reviews.append(ReviewObject("unhandled_structure", node, "source structure retained without an approved native renderer"))
        for key, value in node.attributes:
            if key.startswith("on") or key in ("style", "srcdoc"):
                reviews.append(ReviewObject("inert_active_attribute", node, "attribute retained as data only; never execute or render as HTML"))
            if key in ("href", "src", "poster", "cite", "data") and value is not None and not _safe_url(value):
                reviews.append(ReviewObject("unsafe_or_relative_url", node, "URL retained as data only; no resolution or request authorized"))
    if any(x.role == "unclassified" for x in contributors):
        reviews.append(ReviewObject("unclassified_contributor", credit, "unrecognized byline role retained verbatim"))
    if LICENSE_URL not in licenses:
        reviews.append(ReviewObject("unreviewed_license", post, "article-specific license differs from reviewed CC BY 3.0 URI"))
    syndication = _html(item.content_html)
    # Feed and page are both retained intact. A mismatch is an explicit review
    # object, never license to substitute the description or drop paragraphs.
    roots = tuple(x for x in syndication.children if isinstance(x, ContentNode))
    excluded = set()
    if roots and any(x.has_class("tagline") for x in roots[0].walk()):
        excluded.add(id(roots[0]))
    for node in roots:
        if node.has_class("gv-rss-footer"):
            excluded.add(id(node))
    feed_core = _compact("".join(x.text() if isinstance(x, ContentNode) else x for x in syndication.children if id(x) not in excluded))
    if feed_core != _compact(entry.text()):
        reviews.append(ReviewObject("feed_page_content_difference", syndication, "full feed and page differ after explicit syndication wrapper comparison"))
    return SourceArticle(
        provider="globalvoices-ja", identifier=item.identifier, guid=item.guid, canonical_url=canonical,
        source_name=source_name, article_html_language=html_language, feed_language_label=feed.language,
        title=item.title, published_raw=published_raw, modified_raw=modified_raw,
        published_utc=published, modified_utc=modified, feed_item=item, body=entry,
        syndication_body=syndication, header_metadata=header,
        taglines=tuple(x for x in header.walk() if x.has_class("post-tagline")),
        contributors=tuple(contributors),
        contributor_blocks=tuple(x for x in entry.walk() if x.has_class("contributors")),
        article_credits=article_credits, original_date_blocks=original_dates,
        original_publication_date=original_date,
        translation_links=tuple(x for x in header.walk() if x.has_class("translation-language")),
        observed_license_uris=licenses, policy_receipts=tuple(policies), feed_receipt=feed.receipt,
        article_receipt=receipt, review_objects=tuple(reviews))
