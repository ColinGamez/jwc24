# Demae restoration status

Current navigation: the home-button QR shortcut was withdrawn. The launcher
pins the restored native-flow v8 WAD; `-PhoneOrdering` preserves that native
flow too. The old QR screen requires explicit `-PhoneQrDiagnostic` selection.
The intended QR entry is final checkout after restaurant/menu/basket browsing.
That integration is unfinished, and native phone validation remains intact.
Only verified real menus may be added; demo dishes are excluded. See
[phone handoff status](phone_handoff.md) for the remaining backend and UI work.

Use `tools/start_demae.ps1` with the existing shared JWC24 Dolphin profile.
The launcher does not create another profile. It uses the privately rebuilt
HCHJ local-API WAD and the loopback fixture service on port 18085.

Implemented backend work:

- Startup document and test-authentication responses with recovered XML root
  and CDATA framing; welcome was reached in the native channel.
- Root prefecture lists and optional nationwide municipality snapshots.
- Seven-digit postal requests use the traced manual-selection fallback;
  successful automatic native postal selection is not implemented.
- Offline Japan Post directory, preserving ambiguous matches and leading zeros.
- Offline terminal-town builder and lossless review registry. Town responses
  are not yet served; native terminal completion needs further tracing.
- Hot Pepper directory import with validated region/page cache identity.
  Current cache: 94 pages and 9,400 unique listings across all prefectures,
  representing partial provider coverage, not delivery eligibility.
  The importer defaults to two pages per prefecture and rejects malformed
  pagination metadata before reusing pages or claiming complete coverage.
- Official Domino's menu-index importer: 40 unique real product records from
  the captured source, retaining source links and qualified advertised prices.
  This is private menu evidence, not native menu serving or delivery eligibility.
  See [menu consumer and source status](menu_contract.md).
- Hot Pepper remains the chosen directory source. A reviewed Demae-can branch
  mapping now has one verified match; restaurant-specific phone sessions and
  confirmation notices are implemented and tested, but not integrated with
  native checkout. See [restaurant linking](restaurant_links.md).
- Experimental category HTTP route: with explicit directory catalogs, postal
  data and a replacement area registry, known town IDs resolve to category
  labels backed by restaurants in that municipality. Current exact-label data
  supports 269 municipalities. Unknown areas and unsupported reservation
  requests are rejected. Shop/menu/basket browsing is still not connected.
- An uninstalled directory-row client candidate and three real-source shop
  preview rows are staged. The candidate removes only the list payment filter;
  the preview does not claim payment support, delivery eligibility or exact
  ordering prices. Native row display and selection remain unverified.
- The three-row shop preview can now be served through a separately enabled,
  strictly validated action7 HTTP route. Tests cover geography/category
  membership, request modes, duplicates and continued order rejection. The
  running shared-profile service still does not enable it. A native stopped-row
  selection gate was traced and must be replaced with a directory details path.
- A dedicated native directory-info modal candidate now intercepts the initial
  row transition before ordinary shop-detail processing and returns to the
  list. Twenty compiled PPC scenarios with mocked SDK calls pass, including
  cleanup and shared-message preservation. The WAD remains uninstalled; this
  does not yet establish live Dolphin browsing.

Remaining: native town completion, original area-ID semantics and Japanese
encoding verification, category/shop/menu responses, image routing, genuine
ordering integration and mail confirmation. Provider directory records do not
establish menus, payment support, delivery availability or order authorization.
No actual orders are submitted by the fixture server.

See [postal directory](postal_directory.md), [native requests](native_requests.md),
[response contracts](native_response_contract.md), [shop contracts](shop_contract.md)
and [historical web research](../../research/demae_historical_web.md).

The [terminal-selection trace](town_completion.md) records the confirmed
display/isNextArea gates and `area_shopinfo` parameter mapping. Its response
requires pre-existing shop models; complete startup ordering remains unresolved.
Further tracing identifies the post-confirmation gate as channel-state NAND
persistence to `State.dcd`, rather than geographic validation. The selected
numeric ID is stored as signed 64-bit words and later formatted with `%011lld`
(minimum width 11). Any custom decimal-ID mapping must preserve that
normalization before it can be connected to lookup routes.
The state-file reader additionally caps the value at 99,999,999,999.
`jwc24.demae_area_code.normalize_area_code` enforces a conservative nonnegative
ASCII-decimal policy within that limit and canonicalizes to eleven digits. It
does not assign geographic identities or enable native town routing.

`tools/build_demae_area_registry.py` now assigns eleven-digit replacement-service
IDs to the offline town candidates. Its persistent registry reserves retired
entries and rejects duplicate codes or exhaustion; it is not an original
Demae-can code mapping. Startup traces found positivity, separate saved-identity
matching and decimal formatting before the API handoff, without geographic
arithmetic in that examined path. The registry remains offline until the
remaining identity/model/API prerequisites are implemented and verified.
The offline town builder accepts a validated `AreaRegistry` snapshot to emit
decimal terminal codes. Bidirectional lookup resolves them to the complete
source municipality/postcode/town tuple. Missing entries abort the build;
experimental and decimal identifiers cannot be silently mixed in this mode.
These responses remain offline pending native integration.

`tools/audit_demae_town_responses.py` checks every municipality against the
decimal registry, including duplicate IDs, reverse municipality resolution,
XML framing/counts and conservative response limits. The current snapshot
validates all 1,892 responses with 122,375 emitted town rows and 2,150 excluded
review candidates. Largest response: 220,290 bytes, below the inspector's
262,144-byte producer limit; this is not a proven native capacity.

The offline category builder now uses a `response` root, CDATA, explicit
experimental category codes and final `apiStatus` ordering. Its inspector
rejects duplicate codes, empty lists and misplaced status, matching the traced
consumer's child-count-minus-one hazard. Category semantics and native
activation remain unverified; no category response is served yet.

Further conversion tracing establishes UTF-8 wire CDATA decoded to internal
Shift_JIS strings. The native meal-group comparison is `食事` (bytes 90 48 8E 96
internally). This establishes the category fixture's text encoding, while
end-to-end category activation and provider/category mapping remain unverified.

Experimental decimal town HTTP routes can now be enabled explicitly with
`--town-registry private/demae/postal/replacement-area-registry.json` alongside
`--postal-database`. The server validates the complete snapshot before binding
and reports the opt-in capability via `/health`. The default launcher does not
enable this mode. Native town confirmation and restaurant loading remain
unverified; category and ordering responses are not enabled.

Town label eligibility now includes a conservative Python strict Shift_JIS
check. The current nationwide source adds no exclusions from that check; full
source names remain preserved. This does not establish every behavior of the
native converter's repertoire or error handling.

Native category UI codes `01` through `11` are recovered in
`jwc24.demae_categories`. Provider genre codes are retained separately by the
Hot Pepper adapter (schema version 2), alongside public catchphrases and logo
URLs documented in https://webservice.recruit.co.jp/doc/hotpepper/reference.html .
Only exact genre labels map automatically; unknown labels are left unmapped,
not assigned to Other. All 94 pages were refreshed to schema 2 on 2026-10-15:
9,400 genre codes and logo URLs, and 8,678 promotional descriptions.

`tools/build_demae_catalog_categories.py` audits cached directory genre labels
and builds offline category XML using recovered native IDs. Current coverage:
1,056 exact-label matches and 8,344 explicitly unmapped listings out of 9,400.
This is genre classification, not native shop eligibility or delivery coverage.
All region inputs and fixtures are checked before publishing the batch.
Publication now uses the shared batch publisher with captured source checks,
rollback on ordinary publication errors, and a SHA-256 manifest of active
fixtures. Old XML files outside that manifest are historical artifacts, not
current availability. A region that loses all exact-label matches is removed
from the active manifest without deleting unrelated files.

The shared native XML writer now enforces conservative strict Shift_JIS scalar
representability, valid XML control characters and fixed ASCII element names
before serializing UTF-8 CDATA. Unsupported source text fails the build rather
than reaching a native converter failure. Full native repertoire equivalence
still requires separate verification.

`jwc24.demae_shop_validation` checks recovered required shop-list producer fields,
payment eligibility and conservative encoding/size policies. It does not prove
native rendering or order support. The cached-directory audit currently finds
zero complete native shop records among 9,400 listings and flags 19 names and
816 promotional descriptions that fail strict Shift_JIS encoding. Raw source
text is preserved. Another 722 listings have no promotional description.
Home/reservation/payment/status capabilities
remain unestablished by the directory integration.

The separate read-only text audit finds every strict-codec exception in the
current catalog (19 names, 816 descriptions) is CP932-representable and has an
NFKC-normalized candidate representable by strict Shift_JIS. These diagnostics
do not establish the native converter's extension tables. No source text was
normalized, replaced or dropped; the conservative producer guard stays in place
until that repertoire is traced.
All those exceptions are U+FF5E (fullwidth tilde). An explicit offline
`prepare_native_display` projection substitutes ASCII tilde for that punctuation
only and records substitutions, preserving the source. All 18,800 checked name
and description fields pass with that projection; unsupported unrelated glyphs
remain rejected. This utility is not wired into native shop responses yet.

That strict-codec policy is superseded by the recovered native encoder tables:
all 2,214 unique characters in cached names and descriptions encode identically
with native tables and Python CP932. Native XML/shop producers now use a CP932
representability policy and display preparation preserves the exact provider
text, including fullwidth tilde. No normalization is applied. This is confirmed
for the audited repertoire, not a blanket claim about every Unicode character.

The [phone handoff](phone_handoff.md) now has a stable paired QR entry, expiring
checkout sessions, explicit user confirmation and durable shared-mail delivery.
The dedicated native QR screen is being built separately from merchant imagery.

The importer supports `--upgrade-schema` to replace older valid pages with
adapter schema 2, and `--prefecture JP-xx` to limit a refresh. A targeted refresh
writes its own last-import summary and preserves the nationwide summary.
Provider pages are checked before replacing cached pages; transport errors
remain sanitized so credential-bearing URLs are not printed.
The launcher waits up to 30 seconds for service readiness, allowing time to
validate the nationwide municipality snapshot before launching Dolphin.
The local `/health` endpoint reports loaded municipality coverage and explicit
town/restaurant/ordering capabilities without address or credential data. The
launcher checks those capabilities as well as the test-auth response before
starting Dolphin; missing municipality coverage prevents launch.
