# Demae restoration status

Updated October 22, 2026. Demae is an experimental restoration using real
Hot Pepper restaurant data, with a separate Demae-can phone checkout backend.
**Native dish selection, basket UI and final checkout handoff are unfinished.**

## Restaurant and menu data

The private SQLite archive retains 9,400 listings across all 47 prefectures,
source history, reviewed branch links and menu observations. Missing source
listings are retained rather than automatically marked permanently closed.
This is a partial directory snapshot, not complete delivery coverage.

The latest reviewed imports retain 248 observed items from 38 branches in
38 prefectures. These are partial menus. Miyagi, Osaka, Hyogo, Shimane,
Hiroshima, Kagawa, Fukuoka, Oita and Okinawa still lack reviewed menu observations
in this snapshot.

Menu observations must be at most 24 hours old when used; branch reviews also
expire. Retained history does not establish current prices, stock or delivery
eligibility. Only verified real menus are admitted. A directory listing or
chain-wide menu alone does not establish an orderable branch menu.

Restaurant photos are source-backed and cached on demand. Credentials,
private databases, original channel software and generated WADs stay outside Git.

See [database retention](database.md), [Hot Pepper sources](hotpepper.md),
[reviewed restaurant links](restaurant_links.md) and
[menu/basket progress](menu_basket.md).

## Preview backend

The loopback fixture server supports recovered startup XML, nationwide area
navigation, directory categories and restaurant lists. Postal lookup currently
uses the manual-selection fallback. Directory rows do not establish delivery
or payment capabilities.

The offline [processed postal lookup](postal_lookup_contract.md) now matches
the original helper's exact-match and rounded-fallback selection on synthetic
native checks. The original `zpcd` header gate is also verified separately;
synthetic LZ10/LZ11 downloads exercise the independent decoder through lookup.
The original decrypt-and-strip callback also passes synthetic file-I/O checks,
including allocation and header failure cleanup. Native LZ10/LZ11 decompression
now passes separate guarded synthetic checks. Its filesystem wrapper also
passes synthetic file/heap tests, including read,
write, close and allocation failures. Real storage and complete download
acceptance remain unverified. The original processing orchestrator now also
passes a combined synthetic task-file test from decryption through address
selection, including its cancellation checkpoint. WC24 task delivery is not
part of this test.
These checks are not connected to the live postal route.

With a menu directory loaded, the separate preview API provides:

- `GET /preview/menu?restaurant_id=hotpepper:J000662333&page=1`: six-item
  pages by default, exact category filtering and a 20-item page-size limit.
- `POST /preview/basket`: JSON containing `restaurant_id` and `selections`
  (`item_id`, `quantity`), returning listed subtotals only.
- `GET /health`: preview capabilities and ordering limitations.

The Wii client does not call these JSON endpoints yet. They reject stale or
mismatched evidence and cannot submit orders, create handoffs or queue mail.

The separate phone backend supports expiring sessions, explicit “I placed my
order” confirmation and durable Wii Mail delivery. Provider checkout requires
reselecting items and confirming options, fees and prices. There is no
provider callback or automatic basket transfer. See
[phone handoff](phone_handoff.md) and [mail notices](mail_notice_contract.md).

## Native verification and remaining work

The native XML recursion fix uses explicit closing tags and CDATA. Offline
checks exercise the fingerprinted native parser, category consumer, text
storage, deep copies and linked-list selection, with SDK dependencies mocked.
Allocation-failure checks verify preservation of already-linked menu rows.
Separate native size-field checks verify text copies and replacement failure
behavior; they do not establish stock meanings or size-list rendering.

The last real-category sweep verified 57 categories across 34 branches. Four
branches retain category characters outside the current CP932 producer policy;
source text is preserved. These checks do not establish live rendering.

The item-list consumer requires at least one parsed size row, including
variant item code, size label, price and stock fields. Current observations
lack verified variant details. Native item rendering and selection, stock
semantics, lunch handling and checkout wiring remain unfinished.

See [menu/item contracts](menu_contract.md), [shop contracts](shop_contract.md),
[directory status](directory_categories.md) and [crash findings](native_crashes.md).
The [address-save follow-up](address_save_contract.md) verifies a cataloged
HCCJ sample, native save-header trace and AES-CBC routines with synthetic keys.
Identifier-dependent key/IV construction is checked with replaced templates;
actual sample/device binding, integrity checks and decoding remain unfinished.
Decrypted section framing now has a bounded metadata inspector and native
lookup checks; it does not decode personal fields or validate authenticity.

## Local setup and checks

Run commands from the repository root with Python 3.11 or newer:

```powershell
python -m pip install -e ".[artwork,reverse-engineering]"
python -m unittest discover -s tests -p "test_demae*.py"
```

The launcher requires locally prepared private fixtures, postal data and the
fingerprinted WAD. A fresh clone does not include these artifacts. It uses
the existing shared Dolphin profile:

```powershell
powershell -File tools/start_demae.ps1
powershell -File tools/start_demae.ps1 -DirectoryPreview
```

The default pins the restored native-flow v8 WAD. `-DirectoryPreview` selects
the experimental directory client. The home-button QR shortcut remains
withdrawn; `-PhoneOrdering` also preserves the native home flow. A QR-only
diagnostic is available through `-PhoneQrDiagnostic`.

Useful offline checks after preparing private source data:

```powershell
python tools/verify_demae_menu_coverage.py
python tools/verify_demae_menu_plan.py
python tools/verify_demae_native_menus.py
```

Freshness checks may reduce usable coverage until sources are reread. Never
refresh timestamps without reviewing the source again. These verification
commands do not submit actual orders. See [fixture setup](fixture_harness.md)
for the detailed experimental server workflow.
