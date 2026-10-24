# Historical detail and controller pages

October 25, 2026. The preview now uses accepted historical detail pages for
**834 title IDs**, with their original information-panel structure, matching
stylesheets, title text, genre, publisher, player text, platform, ratings and
date text. Dates retain their captured context; they are not reclassified as
Wii release dates. The prior custom preparation message is absent from these
captured views. Purchases and installation remain unimplemented.

## Source acceptance

Detail bodies must match the private capture manifest and the accepted
[title metadata](title_metadata.md), including the internal `titleId`. All
required shared image paths must exist. One accepted detail page references
`/oss/oss/common/images/Pic_Rating/CERO/cd05.gif`, which is absent from this
backup and from the installed resource archive. Images with that basename in
the GRB/PEGI directories are different rating-system resources and are not
substituted. That title keeps the earlier experimental view. Together with
nine IDs without accepted detail metadata, **ten detail routes retain the
earlier renderer**.

The captured controller link leads to `B_08.jsp`. A further private extraction
recovers **837 Japan-region controller pages**, totaling **29,874,331 bytes**.
These pages have no `titleId` variable; acceptance instead requires their
generated internal progression URLs to agree with the requested title ID,
plus readable, nonempty title text and complete shared dependencies. One
capture has a blank title and is excluded, leaving **836 enabled controller
pages** and eight unavailable title/controller routes. Those purchase
progression URLs are inspected as evidence and are never executed.

All 834 enabled captured detail views link to their corresponding controller
page. Its original game-specific text and controller artwork are retained.
The original compatibility-mode condition hides GameCube artwork on vWii;
its body is extracted from a fingerprint-pinned page and enclosed in a small
JWC24 function wrapper. Other captured account/session scripts are not enabled.

The detail heading now follows the Japanese purchase-screen heading in
Nintendo's [official functions manual](https://www.nintendo.co.jp/wii/support/pdf/wiimanual_functions.pdf),
printed page 42 (PDF page 44), visually checked in its screen reference.
The private PDF SHA-256 is
`1ff816b91dc7d01afe524b551dc0bc256902ba547a7c678ba61fc0f8f3d65c5d`.
This corroborates that heading, not a version-matched v21 localization dump.
The controller caption and back label remain English pending further evidence.
The [collector provenance limits](frontend_capture.md) apply.

## Service behavior

The detail renderer enables the original information panel and its controller
link. Captured purchase, gift, storage-selection, downloaded-state and
balance-error branches are excluded. Their recorded states do not describe the
visitor's account. No invented availability notice, balance, ownership or
purchase confirmation is added. Acquisition controls remain unfinished work.

Controller routes return to the same detail with list/search/filter context
preserved; details return to the corresponding catalog context. Only local
read-only routes are served. Source trees are copied before adaptation and a
bounded cache retains at most sixteen parsed pages.

A one-time index builder checks every selected page and dependency. Its private
output is bound to the frontend manifest, metadata digest and controller capture
manifest and validation revision. Older acceptance revisions are rejected.
Runtime startup checks those bindings rather than rescanning every
body. Requested pages still undergo size/hash and identity checks before being
cached. The launcher checks the running index and support-manifest digests.

## Reproduction and checks

After the [frontend/metadata imports](title_metadata.md):

```powershell
python -m tools.import_wii_shop_frontend_capture '<private archive.7z>' --listing '<private listing.txt>' --title-support-only --output private/wii_shop/frontend-title-support-v1
python -m tools.build_wii_shop_captured_title_pages
```

The index defaults to `private/wii_shop/title-pages-v2/index.json`; existing
outputs are refused. Original bodies, images, the derived compatibility script
and index remain private. Git contains adapters, tests and aggregate evidence.

The [validation report](../../research/wii_shop_captured_titles_validation_20261025.json)
records all 834 detail and 836 controller routes, 882 dependencies, source field
preservation and return context over certificate-verified loopback HTTPS.
There are 111 Shop tests plus two credential tests. VM checks exercise the
compatibility condition with synthetic native/DOM state. Actual native visual
verification, Japanese copy recovery and full commerce remain outstanding.
