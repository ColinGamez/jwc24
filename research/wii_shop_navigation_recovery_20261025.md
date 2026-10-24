# Shop category/search capture review — October 25, 2026

The 2019 collector contains a recoverable **generic no-results layout**. It
does not recover the missing Japanese category gateway/publisher/WiiWare menus,
canonical genre membership, or the interactive search-again heading.

The [compact audit](wii_shop_navigation_recovery_20261025.json) records checked
manifest/page fingerprints, original captured controls and exception states.
Original page bodies remain beneath `private/wii_shop/`; none are included in
the parser, tests or public report. A collector URL/hash establishes the source
of the fetched bytes, not a Nintendo signature or an untouched retail server.

## Recoverable no-results layout

The complete all-region catalog selection has 347 request entries totaling
58,170,234 bytes. Three entries contain identical 34,978-byte no-results pages:

`96015418f17ae2072be5b909699ab2df90e2c50a38e28322541c56316862b6e9`

Their recorded selectors contain `titleId`, with one additionally containing
`country`; they are not recorded keyword (`title`) searches. The view has a
`text02-01` notice, a generic English catalog heading, no `catalogFrame`, and a
parental-controls explanation. Its original initializer configures the left
button as Back through `showBack()`. It has no retry input or interactive
heading. These observations establish the captured generic no-results view,
not the exact Japanese keyword-search state.

`jwc24/wii_shop_captured_empty.py` provides a source-pinned reader for this
layout. It checks source/archive metadata, selector provenance, exact byte
size/hash, the original stylesheet list, and all twelve display dependencies
(including images referenced by the shared CSS). It exposes the original
`layout_html`, a parsed body without script tags/comments, caption, stylesheets, dependency list
and manifest hash. External script tags and favicon references are outside
this script-free display check. Captured account/session/gift scripts are not
enabled. Original inline event attributes still require the caller's normal
sanitizer. The original English notice is retained; no Japanese copy is invented.

The reader was exercised against `frontend-all-catalog-v1` and the checked
`CapturedScripts` pack. Its catalog manifest SHA-256 was:

`61053cccb807fa22423960bda15066c13dfa8db5627379a6a909512d0a7befc5`

The earlier JP selection also contains five **different** empty observations:
requests for pages 85–89, beyond the captured 84-page catalog. Those contain an
empty `catalogFrame` and no no-results notice. They must not be used to claim
that the keyword-empty screen was recovered. Across all regions there are 24
empty catalog-frame entries, 320 populated entries, and three entries with the
single no-results layout above.

## Category and search-again limits

The listing has zero filename hits for `B_17.jsp`, `B_23.jsp` or `B_27.jsp`,
including URL-decoded/case-insensitive basename classification. Its 347 `B_04`
request filenames contain none of `genre`, `publisher`, `platform`, `title`,
`search`, `key`, `sort`, `category`, `subCat` or `vc`. This is a bounded archive
inventory, not proof that the pages cannot exist elsewhere.

The captured `B_01` category control targets `B_23.jsp?vc=true`. Its title-search
input uses native keyboard mode `cKT_PredictNoLF`, five rows and a forty-character
limit; the inline handler sends the entered value as `title` to `B_04`, starting
at page 1. The category parser records these constants without emitting full
query strings or input contents.

`B_03` binds ten system codes to captured English labels. `B_16` binds 21 genre
or service codes to captured English labels, including `TRIAL`/Demo,
`BOARD/TABLE`/Board Game, `IMPORT`/Import and the two Wi-Fi service groups. The
audit preserves every observed binding. These are label-to-code observations;
they do not establish which Japanese titles belong to each code. Matching a
canonical code to the separate 210 display-description strings by translation
or spelling would remain a guess. The unlabelled-region request and English
body are not a recovered Japanese picker.

All 347 recovered list headings lack anchors and inputs. The captured caption
counts are Catalog 190, Catalogue 151, Korean catalog 5 and Recommended Titles
1. The thirteen captured shared scripts provide no recovered search-again
heading implementation; the generic keyboard wrapper alone does not supply
the missing markup/handler.

Nintendo's [December 13, 2007 developer interview](https://www.nintendo.co.jp/wii/staff/shopping-channel/articles/index2.html)
independently describes maker/genre/title searches and activating the upper
search-result title with the A Button to search again. That establishes the
historical interaction, while the interview explicitly dates its contents to
2007. It does not provide the missing v21 result template, exact Japanese
strings, or native hover/keyboard behavior for a new implementation.

## Integration boundaries and verification

The no-results reader can supply a captured generic view when a nonempty
replacement-service query returns zero titles, with that reuse documented.
Native Japanese copy and search-again remain unverified; do not manufacture a
Japanese retry heading, new control, genre mapping or missing menu screen.
Preserve the working experiment until an evidence-backed flow is ready.

The parser/reader tests check entity decoding, the original input constants,
private query-value exclusion, source/archive/member-host validation, selector/hash validation, path safety,
dependency failure, and the distinction between an empty frame and a captured
notice. Eleven focused tests passed:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_category_capture tests.test_wii_shop_captured_empty
```

The audit can be reproduced without executing captured scripts:

```powershell
.venv/Scripts/python.exe -m tools.inspect_wii_shop_category_capture --capture private/wii_shop/frontend-navigation-v1 --capture private/wii_shop/frontend-japan-catalog-v2 --capture private/wii_shop/frontend-capture-v1 --capture private/wii_shop/frontend-all-catalog-v1 --listing private/wii_shop/frontend-backup-2019/archive-listing.private.txt --output research/wii_shop_navigation_recovery_20261025.json
```

`--detailed-private-output` optionally writes all per-page observations beneath
`private/`; the default public report aggregates ordinary pages and retains
representative hashes plus empty-frame exceptions. No Dolphin process, NAND,
device credentials, account data, runtime service or existing shared core file
was changed by this review.
