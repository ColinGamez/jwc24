# Supplemental Global Voices Japanese source records

November 7, 2026. `jwc24/globalvoices_news.py` implements an offline adapter for
actual captured Global Voices Japanese RSS and article pages. It returns
complete structured source candidates for future News integration. No provider
has been activated, no article was published, and the original channel UI,
native record builder, signer and delivery routes are unchanged.

## Publisher evidence and scope

The official [Japanese read/share page](https://jp.globalvoices.org/read-share/)
identifies its [RSS feed](https://jp.globalvoices.org/feed/). The
[Japanese republication policy](https://jp.globalvoices.org/about/%E8%A8%98%E4%BA%8B%E3%81%AE%E8%BB%A2%E8%BC%89%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6/)
describes CC BY 3.0 republication with source/article links and author/translator
attribution. The [global guidelines](https://globalvoices.org/about/global-voices-attribution-policy/)
describe attribution and license links, change disclosure and third-party media
exceptions. These were captured from the publisher on November 7; they are not
independent clearance of every article component. No publisher contact or
republication partnership is asserted.

This is a Japanese-language international/citizen-media source candidate. The
latest item in the saved ten-item feed was published November 2, with an article
modification on November 4. That does not establish hourly, daily, all-category
or complete current Japanese News coverage. A mixed provider/editorial decision
and actual recency assessment remain necessary.

All original captured pages and full extracted stories remain private outside
Git. Public tests contain explicitly synthetic test-only stories; they are not
fallback content and cannot be selected by a production service.

## Input and output

`CaptureReceipt.from_body()` binds an exact reviewed HTTPS URL, bounded bytes,
SHA-256, HTTP 200 and ordered timezone-qualified retrieval bounds.
`parse_feed(body, receipt)` verifies those bytes, rejects XML DTD/entity
declarations, duplicate fields/identities, nested scalar fields and unsupported
GUID/URL routes, then retains the actual title, synopsis, full `content:encoded`,
creator, categories and publication instant separately. Source categories are
data, without native genre inference. Feed/HTML limits are 2 MiB, 50,000 nodes,
128 levels, and at most 100 feed items. These are JWC24 acquisition limits.

`parse_article(feed, guid=..., body=..., receipt=...,
policy_documents=...)` selects the exact feed item, checks matching canonical
link, `og:url`, title, article identifier and publication time, and requires
three separately verified official policy/read-share captures. Article
modification time cannot precede publication or exceed article retrieval. No
HTTP response date, feed build date or retrieval date becomes an article date.
The original-language publication date displayed by the article remains a
separate date-only value and raw source block, without an invented timestamp.

The result retains immutable trees for the entire selected article `.entry`,
the complete syndication body and article header metadata. Nested tags, text
nodes, paragraph/headings, inline formatting, explicit breaks, links, lists,
captions, media, quotations, contributor blocks, unknown elements and inert
attributes remain in source order. Comments and processing instructions are
retained as inert records. HTML is never executed, sanitized into a replacement
article, or exported for a browser to run. Unsupported declarations reject.
The bounded HTML parser is an inert extraction parser, not an HTML5 browser or
proof that malformed markup has one rendering interpretation.

Header bylines distinguish the original author from the Japanese translator,
retaining original role labels, exact names and profile links. Unrecognized
roles stay unclassified/pending. Proofreading contributor blocks, footer
credits/license notices, taglines, original-date labels and translation links
remain available. The real sample's RSS `dc:creator` names its translator;
using it as the sole original author would misattribute the story.

The real feed labels its language `en-US`, while the Japanese article HTML
labels itself `jp`. The adapter retains both literal labels and creates a
pending review object. It does not rewrite them to make the metadata agree.

`review_objects` retain each media element, quotation, unsupported structure,
unclassified contributor/license and unsafe/relative URL with an explicit
pending reason. Unknown substantive markup is never silently dropped. Active
attributes remain inert data with a review record. Duplicate attributes are
retained; selecting an ambiguous identity/structural attribute rejects, while
other duplicates create pending interpretation records. The private sample
retains its third-party screenshot, two video embeds, two blockquotes and
proofreading credit. Their rights and native representation are unverified.

The feed/page comparison separates only explicit syndication tagline/footer
wrappers. Differences create a pending record and retain both full versions;
the description never substitutes for the complete article. Normalized text
comparison is diagnostic, not an approved native text renderer. The real sample
has an equal normalized core of 3,534 characters / 7,068 UTF-16BE bytes, before
actual layout, attribution and link rendering. Exact source text-node content
includes additional source whitespace.

`metadata(checked_utc=...)` reports source ages from actual publication and
modification times and requires an explicit check instant after every supplied
capture. Reports contain counts, dates and fixed non-ready states, with no
story text, contributor names, local paths or article image URLs. Node text
concatenation is available for inspection; it does not insert paragraph breaks
or claim native body fidelity.

## Offline inspection

The command reads immutable `.body` and `.json` capture pairs; it never fetches,
contacts, signs, installs or publishes anything:

```powershell
.venv/Scripts/python.exe tools/inspect_globalvoices_news.py `
  --capture-dir private/news/globalvoices-source-audit-20261107 `
  --article-name sample-65795 `
  --guid 'https://jp.globalvoices.org/?p=65795' `
  --checked-utc '2026-11-07T10:00:00Z'
```

Expected companion captures are `feed`, `japanese-policy`,
`republishing-guidelines`, `read-share`, and the selected article name. Receipts
must state complete successful acquisition, hash, length and retrieval times.
Receipt files are bounded duplicate-free UTF-8 JSON; malformed input produces a
generic count-only failure. The saved receipts establish captured bytes and
caller-supplied metadata, not independent publisher authentication.

## Remaining native handoff requirements

`SourceArticle` is always pending for component rights and native body/link/
attribution rendering. Its publication-ready and authentication flags are fixed
false and cannot be set through ordinary construction or `dataclasses.replace`.
They are scope labels, not tamper-proof Python authorization controls.

This adapter supplies no native article IDs, headers/opaque words, minute
conversion, genre mapping, geography, ticker, picture bytes, logos or synthetic
hourly snapshots. Those need explicit justified decisions for the existing
[native builder](record_builder.md). A stable persisted mapping must prevent
native ID collisions. Full body plus accurate visible attribution/usable links
must fit actual native limits and pass native rendering checks; overlong stories
must not be silently truncated. Policy receipts are not a blanket rights grant.

Actual component rights, appropriate source/author/translator/license attribution
and change disclosure, native text/link support, real source coverage, 24-buffer
scheduling/graph, signature trust, VFF capacity and original Japanese UI testing
remain completion gates. No tests of this adapter prove those gates complete.
