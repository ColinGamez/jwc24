# Native menu-list consumer and official menu evidence

## Native item-list contract anchors

The size-row trace is now anchored separately: sizeList child count at
`0x8004FE78` and indexed child access at `0x8004FE94` iterate the actual
children without requiring formatted child names. Within each child,
itemCode (`0x8004FEB0`), size (`0x8004FF18`), price (`0x8004FFC8`) and
isSoldout (`0x800500B8`) are looked up. Their native setters are respectively
`0x800296C0`, `0x8002977C`, `0x80029840` and `0x800299C8`, followed by
attachment through `0x80027358`. The static checker verifies each call.
An itemCode that is missing, has no payload or has empty text skips that size
row; a missing price node/payload exits the size loop and reaches the
positive-count check. Consequently, a generic `options_observed` boolean
cannot supply the actual variant identities/labels/prices required here.
Stock semantics and empty-value defaults still need independent tracing.

The action-10 request is at `0x8004F3E0`; its item-list consumer begins at
`0x8004F45C` with shared status category 0x42. A bounded static trace finds
positive integer `Count`, then `List/container%d` rows indexed from zero.
Each container looks up `name` and an `item` subtree. Within the item context,
the traced fields are `menuCode`, `itemCode`, `price`, `info`, `size`, `image`,
`isSoldout` and `sizeList`. These are case-sensitive names, not a complete
schema or proof of current server compatibility.

After traversing sizeList children, each successfully parsed child is added
through `0x80027358`. Before inserting the item through `0x80026060`, the
consumer calls `0x80027350` (record +0x7C count getter) at `0x800501BC` and
requires a positive result at `0x800501C4`. Zero attached size rows return
failure before item insertion. This establishes a real gap between our
partial name/price observations and the native item model: option/size
evidence has not been extracted, so an empty list or invented single variant
cannot be presented as a verified orderable item.

`tools/inspect_demae_item_contract.py` checks the executable fingerprint,
field-string bytes and exact native call/branch instructions for these
anchors. Its two tests pass; combined with native model/consumer checks,
eight tests pass. This is static contract verification only. Item option
semantics, stock handling, image handling and UI rendering remain unverified.
Private disassembly is retained in `private/demae/item-consumer.private.txt`;
no executable bytes or guessed native item response are published or served.

## Native allocation failure checks

The native model harness now injects failure at each of 22 successive
allocations across two non-lunch menu rows: five source-field setter
allocations, one linked node allocation and five copied fields per row.
All 22 failure paths return failure without increasing the linked row count.
When the second row fails, the first row remains selectable with every text
field and flag unchanged. The test also rejects an injection index that was
never reached. Free remains mocked; these checks do not establish leak-free
cleanup or successful recovery inside the full channel UI.

This changes offline verification only. No executable, save or server route
was changed, and no archived evidence timestamps were refreshed.

## Native menu model storage checks

`tools/verify_demae_menu_model.py` executes the real menu constructor, text
setters, record deep-copy, linked-list insertion (`0x80029D08`), original
record cleanup and indexed selection (`0x80029F00`). Only allocation/free,
memcpy and byte/wide string lengths are mocked. Menu records are 0x24-byte
nodes, with next at +0x20. Their code, title, name, info and setNum fields use
owned allocated strings; enabledLink is stored at +0x0C. This traced storage
path does not impose a fixed 31-character name buffer.

Seven focused model/builder/consumer tests pass. The model regression
preserves 32 linked rows, alternating flags, Japanese text and one 128-unit
label after clearing each original record. These are tested bounds, not a
claim of maximum UI capacity. Allocation failure and lunch attachment remain
outside this model check.

The archive sweep now separately feeds the consumer's captured category
records into the real model checker. All 57 compatible categories across 34
branches retain their text/codes/order; four Unicode-category branches remain
blocked. The consumer harness still mocks its own model, so the report keeps
that limitation and separately records native model verification. No native
rendering, active lunch behavior, item selection or ordering is established.

## Real-category offline candidates

`tools/build_demae_menu_fixture.py` creates experimental category XML from a
validated branch menu. Original category names retain first-seen source
order; local menu codes hash the provider branch URL and category name.
These codes are local routing identities, not provider product/category IDs.
The candidate has nonempty source labels/URL, experimental enabledLink=0
and setNum=0 controls, an empty explicit lunchMenuList and final apiStatus.
The controls' later UI semantics are not yet established. This builder is
not exposed by the server and does not enable ordering.

`tools/verify_demae_native_menus.py` checks candidates with the native XML
parser/tree comparison and the native consumer control-flow harness. The
retained archive passes 57 categories across 34 branches, preserving menu
codes and names through mocked model insertion. Four branches (Kofu,
Kurashiki, Tokushima and Tenmonkan) are blocked by source category brackets
outside the current CP932 producer policy; original Unicode evidence remains
unchanged. This is category-only coverage, not item-name compatibility.

Five focused builder/consumer tests pass, including Japanese text, branch
code separation, required-field failures and unsupported text rejection.
Native model storage, active lunch handling, rendering, item selection and
checkout wiring remain unverified. No candidate is served to Dolphin.

## Executable non-lunch consumer checks

`tools/verify_demae_menu_consumer.py` now executes the fingerprinted native
consumer at `0x800499FC` using Unicorn PPC. XML lookup/payload access, shared
status validation, allocation/text conversion, lunch attachment and model
storage are mocked. The native consumer's branching and field traversal run
unchanged. This isolates control-flow requirements; it does not establish
wire XML acceptance, native model capacity, rendering or ordering.

Three passing regression tests establish that two non-lunch rows reach the
mocked insertion in order, with their menu codes, Japanese names and exact
enabledLink flags preserved; omission of each required field rejects the
response; status-first ordering rejects it; and zero handled rows reject it.
The harness rejects a different executable fingerprint and explicitly refuses
the unverified active-lunch branch. Mock payload wrappers are supplied even
for empty XML elements, so these tests make no claim about empty CDATA or
missing native payload-wrapper behavior. Synthetic test rows are never served
to Dolphin. No channel binary, save, production route or order was changed.

The restored native home route is unchanged by this pass. No menu fixture was
served, order submitted, or checkout-complete state synthesized.

## Menu categories (action 9)

The request at `0x80049980` calls GET wrapper `0x8002C274` with action 9.
The consumer starts at `0x800499FC`, validates status with error category
`0x41` at `0x80049A38`, and requires the existing menu model at global `+0x268`.
It clears that model through `0x80029CB0` at `0x80049ACC` before parsing.
The XML document is read from global `+0x230`.

The consumer finds `response` at `0x80049B18`, obtains its child count and
iterates only count-minus-one (`0x80049B48` through `0x80049B5C`). As with the
category and shop producers, status must be last for a conservative producer.
Each preceding child is used as the lookup context. These fields must have
nodes and payload wrappers; missing either aborts the response:

| Field | Lookup | Subsequent use |
| --- | --- | --- |
| menuCode | `0x80049B7C` | Copied when nonempty |
| linkTitle | `0x80049C28` | Converted to native display text when nonempty |
| enabledLink | `0x80049D1C` | Flag true only for exact string `1` |
| name | `0x80049DE4` | Converted to native display text when nonempty |
| info | `0x80049ED4` | Converted to native display text when nonempty |
| setNum | `0x80049FC4` | Copied as a string; full UI meaning not yet traced |
| lunchMenuList | `0x8004A060` | Required subtree introducing lunch rules |

The `lunchMenuList` context is inspected for `isLunchTimeMenu` at
`0x8004A09C`. An absent node leaves the native default `0` and skips lunch
hour/status parsing. Exact value `1` enters the branch at `0x8004A148`.
That branch requires `hour`, optionally reads `start`/`end`, and requires
`isOpen` and `message` payload wrappers. Empty start/end/isOpen values can
skip the current row. These are local control-flow findings, not a complete
lunch-hours schema.

At `0x8004A4A0`, a helper attaches lunch data to the menu entry. Its failure
rejects the response; the native menu model insertion at `0x8004A508` is also
checked. A final menu count of zero is an error (`0x8004A570` onward).
The accepted maximum count, field capacities, item schema and later UI paths
still need review. Merely returning these tag names is not native acceptance.

Private disassembly evidence: `private/demae/menu-consumer.private.txt`.

## Executable size-field checks

`tools/verify_demae_size_fields.py` executes the four size-row setters in the
fingerprinted private executable, with allocation, free, string lengths and
memcpy mocked. Item code (`0x800296C0`) and stock text (`0x800299C8`) use
byte strings; size (`0x8002977C`) and display price (`0x80029840`) use native
UTF-16 text. Their field offsets are `+4`, `+20`, `+8` and `+12` respectively.
The stock setter stores text; this does not establish which values the UI
interprets as available or sold out.

Checks verify that copied text survives overwriting the source buffer and
that replacement invokes free for the previous field. Injecting allocation
failure into each setter returns zero and leaves that field null: replacement
does not preserve the old value. Free is mocked, so this is not a leak check.
These checks do not execute XML consumption, size-list attachment, native
rendering or ordering. Synthetic inputs remain offline test data only.

## Basket trace start

Action 16 is requested at `0x8007ADD4`. The following consumer starts at
`0x8007AE58`, validates with error category `0x4B` at `0x8007AE9C`, and requires
an existing basket model from global `+0x270` (`0x8007AF08`). Its error return
is at `0x8007F7F4`, so the current bounded trace does not cover the whole
consumer. Do not implement basket success from this partial inspection.

## Official source import

`tools/import_demae_official_menu.py` parses a private capture of
[Domino's Japan's official menu index](https://www.dominos.jp/menu). The
current source contains 40 unique pizza-product links after identical repeated
entries are deduplicated. Names, descriptions, source links and advertised
price labels remain linked to the SHA-256 of the captured HTML. Conflicting
duplicates, missing names, malformed/truncated product blocks and corrupted
UTF-8 are rejected.

Prices retain their original qualifiers; they are not converted into exact
yen amounts or assigned to unverified sizes. Imported records explicitly have
no exact price or delivery eligibility and are not orderable. A published
chain product is not proof that a local store sells/delivers it or that
Demae-can accepts the same basket. The import is private evidence for the
real-menu implementation, not a replacement native ordering backend.

The importer has no network or ordering side effects. It ignores links that
are not direct official pizza-product paths and writes through the existing
source-snapshot publication guard. Unit fixtures do not get served in-channel.
