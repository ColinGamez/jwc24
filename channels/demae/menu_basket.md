# Verified menu observations and basket handoff

## Local HTTP basket calculation

The loopback preview server accepts JSON at `POST /preview/basket` when its
menu directory is configured. The exact fields are `restaurant_id` and
`selections`, where each selection has an observed `item_id` and integer
`quantity`. It resolves the current branch-bound evidence again and returns
the existing basket plan with listed line/subtotals, unknown checkout total
and `provider_basket_transferred: false`. `/health` advertises this capability
as `basket_preview`; native menu integration remains false.

Payloads are bounded to 16 KiB, JSON only, without duplicate or unexpected
fields. Invalid selections and stale evidence return 409, unknown branches
404, malformed payloads 400 and foreign origins 403. The route only
calculates: it persists no handoff, submits no order and queues no mail.

All 248 retained items across 38 branches passed actual HTTP basket
calculation at quantity two, matching the direct directory plan exactly.
The HTTP regression also covers selecting an item from the second menu
page, wrong item IDs, duplicate lines, boolean quantities, expired evidence,
malformed payloads and foreign origins. It and all five existing fixture
server tests pass. Native Wii selection and checkout handoff wiring remain
unfinished.

## Local HTTP menu preview

The loopback fixture server now exposes read-only JSON at
`/preview/menu?restaurant_id=hotpepper:J000662333&page=1` when supplied a
validated `MenuDirectory`, or automatically with `directory_database`.
Optional `page_size` (1–20) and exact Unicode `category` parameters use the
bounded backend pager. `/health` advertises `menu_preview` separately from
`native_menu_integrated`, which remains false. The native XML menu/item
routes are unchanged and are not connected to this preview endpoint.

Each request rechecks evidence freshness. Unknown restaurants return 404;
missing/expired observations or invalid category/page selections return 409.
Malformed, blank, duplicate or unexpected fields return 400. POST is not
supported. Responses are JSON with no-store caching and cannot create a
basket, order, confirmation or notice. Source evidence is snapshotted at
server startup; restart after importing new evidence.

Actual retained data passed HTTP traversal for all 38 branches, 42 pages
and 248 item identities/prices. The HTTP regression covers category Unicode,
partial last pages, strict requests, missing evidence and expiry while the
server remains running. It and the five existing fixture-server tests pass.
Native Wii item selection remains unfinished.

## Bounded backend menu pages

`MenuDirectory.menu_page` now exposes six-item pages by default, with a
maximum page size of 20 and exact source-category filtering. Item IDs,
names, categories, order and branch-specific prices survive pagination.
Responses include total item/page counts and previous/next page numbers.
Invalid page numbers, unknown categories and stale evidence are rejected;
freshness is checked again on every request. This is a backend interface,
not a completed native Wii screen.

The archive verifier now traverses every full-menu page and every category
page before replaying all observed items through local phone baskets.
A 23-item regression covers partial last pages, category pages, invalid
inputs and evidence expiring between page requests. The focused menu and
handoff suite passes 13 tests. The retained archive passes 42 full-menu
pages across 38 branches, every category traversal and all 248 phone basket
items. No new menus were imported in this change.

## Retained regional batch sixteen

Current coverage is 38 exact-branch menu plans, 248 observed items and 38
prefectures; nine prefectures still lack verified menu observations. Added
six partial listed item/category/price facts from Kochi Otesuji 1-chome:
https://demae-can.com/shop/menu/3248192

The official chain link was followed and the branch's current page read;
its full lot/building/floor identity matches hotpepper:J001036854. Validation
passed and evidence was retained with before/after backups and synchronized
review/link indexes. All 38 links validate against 9,400 restaurants.
Remaining uncovered prefectures are Miyagi, Osaka, Hyogo, Shimane,
Hiroshima, Kagawa, Fukuoka, Oita and Okinawa. These counts describe partial
verified menu observations, not comprehensive prefecture delivery coverage.
All 248 observed items passed local phone basket replay. No orders or
notices were created. Native Wii item selection remains unfinished.

## Retained regional batch fifteen

Current coverage is 37 exact-branch menu plans, 242 observed items and 37
prefectures; 10 prefectures still lack verified menu observations. Added
six partial listed item/category/price facts per branch from fresh pages:
https://demae-can.com/shop/menu/3179267 (Akita west exit, Akita)
https://demae-can.com/shop/menu/3148272 (Toyama south exit, Toyama)

Both full branch identities match retained Hot Pepper records. Akita's
source building spelling uses a katakana hyphen, handled by the existing
address-only normalization without changing display text. Toyama's listed
prices differ from Akita's and were retained independently, including
746 versus 713 yen for the first item. Fresh page reads supersede older
search excerpts. The validated batch was retained with before/after backups
and synchronized review/link indexes. All 37 links validate against 9,400
restaurants. Menus remain partial; provider item IDs/options and customer
delivery eligibility are unverified. All 242 observed items passed local
phone basket replay; no orders or notices were created. Native Wii item
selection is unfinished.

## Retained regional batch fourteen

Current coverage is 35 exact-branch menu plans, 230 observed items and 35
prefectures; 12 prefectures still lack verified menu observations. Added
six independently read partial item/category/price facts per branch:
https://demae-can.com/shop/menu/3141542 (Kofu south exit, Yamanashi)
https://demae-can.com/shop/menu/3272608 (Nagasaki station, Nagasaki)

Both full branch identities matched the retained Hot Pepper records. Fresh
page reads supersede older search excerpts; Kofu's current listed prices
were read directly rather than taken from its older search result. The
validated batch was retained with before/after backups and synchronized
review/link indexes. All 35 links validate against 9,400 restaurants.
Original Unicode labels are preserved; 30 menus have fully CP932-compatible
labels. These remain partial menus without extracted provider item IDs,
option groups or customer delivery eligibility. All 230 observed items
passed local phone basket replay; no orders or notices were created.
Native Wii item selection remains unfinished.

## Retained regional batch thirteen

Current coverage is 33 exact-branch menu plans, 218 observed items and 33
prefectures; 14 prefectures still lack verified menu observations. Added
six partial listed item/category/price facts per branch from:
https://demae-can.com/shop/menu/3146061 (Kurashiki station, Okayama)
https://demae-can.com/shop/menu/3157260 (Tokushima station, Tokushima)
https://demae-can.com/shop/menu/3141488 (Tenmonkan main branch, Kagoshima)

Each official branch page was read independently and its full address matched
to the retained Hot Pepper identity. The validated batch was retained with
before/after backups and synchronized review/link indexes; all 33 links
validate against 9,400 retained restaurants. Original category brackets are
preserved as Unicode and correctly flagged as not CP932-compatible; 29 menus
currently have fully CP932-compatible labels. No item IDs, option groups or
delivery eligibility are inferred. All 218 observed items passed local phone
basket replay, with no orders or notices created. Native Wii item selection
is unfinished.

## Retained regional batch twelve

Current coverage is 30 exact-branch menu plans, 200 observed items and 30
prefectures; 17 prefectures still lack verified menu observations. Added
six independently read seafood-bowl facts per branch from:
https://demae-can.com/shop/menu/3146140 (Meitetsu Gifu station, Gifu)
https://demae-can.com/shop/menu/3141586 (Kumamoto Shimotori arcade, Kumamoto)

Both exact names and full lot/building/floor addresses matched retained
Hot Pepper records. Branch-specific observations were validated and retained
with before/after archive backups and synchronized review/link indexes.
All 30 links validate against 9,400 retained restaurants. These remain
partial observations, with no provider item IDs/options or delivery
eligibility established. All 200 observed items passed the local phone
basket replay, with no orders or notices created. Native Wii item selection
remains unfinished.

## Retained regional batch eleven

Current coverage is 28 exact-branch menu plans, 188 observed items and 28
prefectures; 19 prefectures still lack verified menu observations. Added
six partial listed item/category/price facts per branch from:
https://demae-can.com/shop/menu/3433730 (Shimonoseki, Yamaguchi)
https://demae-can.com/shop/menu/3138545 (Saga station north exit, Saga)
https://demae-can.com/shop/menu/3138482 (Miyazaki station west exit, Miyazaki)

Each link was followed from the official chain directory, each branch menu
was read independently, and full lot/building/floor identities matched to
the retained Hot Pepper records. The batch passed atomic validation with
before/after backups and synchronized review/link indexes. All 28 links
validate against 9,400 retained restaurants. These are partial observations;
provider item IDs/options and customer delivery eligibility are unverified.
All 188 observed items passed local phone basket replay, including exact
line counts, escaped names and listed subtotals. No orders or notices were
created. Native Wii item selection remains unfinished.

## Retained regional batch ten

Current coverage is 25 exact-branch menu plans, 170 observed items and 25
prefectures; 22 prefectures still lack verified menu observations. Added
14 partial menu facts from the official Matsuyama branch page in Ehime:
https://demae-can.com/shop/menu/3138435

The freshly read page differs from the search engine's older menu excerpt.
The retained observation uses the current page's item names, categories and
listed prices, including 504 yen for the grilled ray fin. The exact branch
and full building/floor address match hotpepper:J000770010. No menu was
copied from another branch. Import validation passed with before/after
archive backups; all 25 reviewed branch links validate against the retained
9,400-restaurant catalog. All 170 observed items passed the local phone
basket replay; no orders or notices were created. Native Wii item selection
remains unfinished.

## Retained regional batch nine

Current archive coverage is 24 exact-branch menu plans, 156 observed items
and 24 prefectures; 23 prefectures still lack verified menu observations.
Added six partial listed item/category/price observations per branch:
https://demae-can.com/shop/menu/3138420 (Kusatsu, Shiga)
https://demae-can.com/shop/menu/3157249 (Gakuenmae, Nara)
https://demae-can.com/shop/menu/3465756 (Tottori station, Tottori)

Each official branch page was read independently and its full address matched
against its retained Hot Pepper identity. The three-branch batch passed
validation, was retained with before/after database backups, and refreshed
the legacy review/link indexes. All 24 branch links validate against 9,400
retained restaurant identities across all 47 prefectures. These observations
are partial menus, with no extracted provider item IDs or options and no
customer delivery eligibility claim. Native Wii item selection remains
unfinished.

All 156 observed items passed the local phone basket replay, checking item
names, line counts and listed subtotals. No orders or notices were created.

## Retained regional batch eight

Current coverage is21 exact-branch menu plans,138 observed items and21
prefectures;26 prefectures still lack verified menu observations. New partial
menus, six source name/category/price facts per branch:
https://demae-can.com/shop/menu/3138478 (Ebina, Kanagawa)
https://demae-can.com/shop/menu/3157251 (Matsumoto, Nagano)
https://demae-can.com/shop/menu/3138493 (Hamamatsu, Shizuoka)
https://demae-can.com/shop/menu/3145967 (Toyohashi, Aichi)
https://demae-can.com/shop/menu/3248196 (Tsu, Mie)

Every branch's name, full source address, category and listed price was read
from its own official provider page; none were copied from another branch's
menu. Matsumoto's sushi names remain exactly as observed, without the numeric
prefixes present in Koga's separate source menu. The validated five-branch
batch was committed together, retained in the archive and source index, and
protected by before/after backups.21 branch links validate against the9400
catalog identities. Native menu integration remains unfinished.

## Retained regional batch seven and full item replay

Current coverage is16 reviewed branches,108 observed items and16 prefectures;
31 prefectures still lack verified menu observations. Added partial sources:
https://demae-can.com/shop/menu/3138463 (Urawa, Saitama)
https://demae-can.com/shop/menu/3138402 (Nishifunabashi, Chiba)
Both branch identities and six listed names/prices were checked independently
against their official pages and the source catalog, then imported with
before/after archive backups.16 reviewed links validate against9400 records.

The phone verifier now replays every observed item rather than a two-quantity
sample of the first item. It uses bounded50-line test baskets, checks escaped
names, exact line counts and listed subtotals, and verifies that GET leaves
confirmation/mail flags unset. All108 archived items across16 branches pass.
A51-item regression proves that the verifier crosses the basket limit without
silently skipping the last item, including non-CP932 source text and HTML
metacharacters. These are test basket pages, not native menu pagination.

Listed subtotals in the verification artifact now sum one of every observed
item, rather than two of the first item. They remain test estimates with no
checkout total, delivery eligibility claim or submitted order. Native item
selection and menu rendering are still not integrated.

## Retained regional batch six and Unicode preservation

Current coverage is14 reviewed branches,96 observed items and14 prefectures;
33 prefectures still lack verified menu observations. Added official sources:
https://demae-can.com/shop/menu/3138422 (Utsunomiya, Tochigi)
https://demae-can.com/shop/menu/3482957 (Koga, Ibaraki)
Both links were followed from the official chain directory, then their full
names/addresses and six partial listed menu facts were checked separately.
No product code is inferred from a number included in a displayed item name.

Koga's sushi menu includes original names such as458〗並にぎり, whose bracket
is not representable in CP932. The first batch attempt rejected that label
before committing any records. The source menu layer now preserves valid
UTF-8 labels and adds explicit per-item/per-menu cp932_labels compatibility
flags rather than replacing glyphs or discarding facts. Invalid Unicode
surrogates and control characters remain rejected. This supersedes the
initial blanket CP932-label rejection described below.

All14 phone basket checks pass with original source labels retained;13 of
the partial observed menus have entirely CP932-compatible labels. This flag
only describes encoding, not native font/rendering acceptance. Unsupported
labels require a native display solution before those items can be offered
through a Wii-native menu. Native menu integration remains false.

## Retained regional batch five

Current coverage is12 reviewed branches,84 observed items and12 prefectures;
35 prefectures still lack verified menu observations. Added partial sources:
https://demae-can.com/shop/menu/3145974 (Wakayama)
https://demae-can.com/shop/menu/3478318 (Kanazawa, Ishikawa)
The six observed item names/prices were read independently for each branch.
For example, the observed 炙りエイヒレ prices are504 and493 yen respectively.
Both remain branch-bound, with provider SKUs/options and delivery eligibility
unknown. All12 archived phone basket summaries pass; no notices or orders
were created.25 relevant regression tests pass.

The official Kanazawa address uses セントラルア－ク for the catalog's
セントラルアーク. Address normalization now interprets a hyphen between
katakana as the vowel-length mark, retaining numeric separators, Latin
building/unit text, floor numbers and building suffixes. Tests reject a
different lot, floor or annex. Displayed source addresses remain unchanged.

Successful menu-batch imports now atomically synchronize the legacy source
review index from the archive after validation/commit. The authoritative
database keeps the evidence and before/after backups; the source index no
longer needs a separate manual merge for each new reviewed menu batch.

## Retained regional batches three and four

Current coverage is ten exact-branch menu plans and72 observed items, with37
prefectures still missing verified observations. Added sources:
https://demae-can.com/shop/menu/3451802 (Nagaoka, Niigata)
https://demae-can.com/shop/menu/3272604 (Kyoto)
https://demae-can.com/shop/menu/3168411 (Aomori)
https://demae-can.com/shop/menu/3204005 (Morioka, Iwate)
Six names/prices were read independently per branch; these are partial menus.
All ten archived branches pass the local phone summary verifier, with no
orders, confirmations or notices created. Both batches have before/after
integrity-checked database backups.

Reviewed-link address normalization now handles a numeric lot's optional
trailing 番地 label and a trailing numeric floor F/階 notation. It retains
all lot/floor digits, building text and unit information. Tests cover Kyoto's
849/849番地 and Nagaoka's III/Ⅲ and1F/1階 formatting, while rejecting a
different lot, floor or appended numeric sub-lot. The source display address
is not changed. These rules do not infer a branch from its chain name.

## Retained regional batch two

The archive now contains six menu-plan branches and48 observed items across
Hokkaido, Yamagata, Fukushima, Gunma, Tokyo and Fukui. The new partial source
observations are six seafood bowls per exact branch:
https://demae-can.com/shop/menu/3248193 (Yamagata)
https://demae-can.com/shop/menu/3307854 (Koriyama)
https://demae-can.com/shop/menu/3157290 (Fukui)
Their names, full addresses and listed prices were read separately from each
official provider page and validated against the corresponding catalog row.
No descriptions, provider product IDs, options or delivery guarantees were
inferred. These are not complete menus.

ingest_reviewed_menus validates a complete paired branch-review/menu batch
before any evidence is committed. A bad branch URL, expired menu, missing
pair or duplicate identity rejects the batch. Repeated successful batches
are deduplicated. tools/import_demae_menu_batch.py accepts private source
files and makes integrity-checked backups before and after import. The
six-branch phone verifier passes through the persistent archive with no
orders or notices.41 prefectures still lack verified menu observations.

## Nationwide evidence index

MenuDirectory now indexes all47 prefecture catalogs and validates menu evidence
by exact restaurant identity. It rechecks review and observation timestamps on
each use, rejects unknown/duplicate observations and shared provider branches,
and keeps missing evidence explicit. Source inputs are copied so subsequent
caller mutations cannot change indexed prices. No chain-wide menu is assumed.

Three reviewed branches currently have partial observed menus: Sapporo
(Hokkaido,18 items), Maebashi (Gunma,6 items), and Shinagawa (Tokyo,6 items).
The added official source pages are:
https://demae-can.com/shop/menu/3148258
https://demae-can.com/shop/menu/3141636
Exact provider names and addresses match the corresponding Hot Pepper records
after existing normalization. Tokyo's observed red tuna bowl is900 yen versus
Sapporo's850; the index preserves that branch-specific difference.

tools/verify_demae_menu_coverage.py writes nationwide-menu-coverage.json with
one entry per catalog restaurant and per-prefecture readiness counts. It
reports9400 restaurants,3 menu-plan branches,30 observed items and44 prefectures
without current verified menu observations. Directory coverage in all47
prefectures does not imply menu/order coverage in those prefectures.

The phone summary verifier now discovers every valid menu through this index
instead of a hard-coded Sapporo filename. All three branches pass temporary
handoff, HTML escaping and listed-subtotal checks, without orders or notices.
Expired evidence remains unavailable until actually reviewed again; the tools
never update timestamps simply to make a stale menu pass.

## Initial branch implementation

The first branch-specific observation file is private/demae/menus/
demaecan-3248195.observed.json. It records18 seafood-bowl names and displayed
item prices read from the official public branch page:
https://demae-can.com/shop/menu/3248195

This is a partial menu observation, not a current checkout quote, delivery
eligibility check or provider SKU export. No product descriptions or images
were copied. Direct HTML retrieval failed; the source was readable through
the web tool. The observation timestamp records that reading, not a guarantee
of the provider's last update or live stock. Options were not extracted.

jwc24/demae_menu.py binds observations to an existing exact-name/address
reviewed Hot Pepper branch link. It rejects another branch URL/identity,
observations older than24 hours or in the future, ambiguous prices, duplicate
items, invalid quantities and unsupported CP932 labels. Item IDs use a local
observed: namespace and never masquerade as provider SKUs.

basket_plan calculates listed item subtotals only. Checkout total and delivery
availability remain unknown, and provider_basket_transferred is false. A
handoff may now retain that local plan when its restaurant context matches.
The additive SQLite migration preserves existing generic and restaurant-only
handoffs. The phone page escapes item names and displays the plan, subtotal,
and instructions to reselect items and confirm options, fees and final prices
on the provider page. No order is submitted from this data path.

tools/verify_demae_menu_plan.py validates the real18-item observation, then uses
a temporary store and local phone HTTP server to check an item summary. Its
synthetic test recipient never receives a notice: only GET is exercised and
no confirmation or dispatch is performed. The two-item subtotal is1700 yen.

Wii native menu rendering, native item selection and native basket navigation
are not integrated. The existing explicit phone confirmation and Wii mail
outbox behavior remain in place. Basket summaries do not become official
provider receipts or enable ordering for the other catalog restaurants.
