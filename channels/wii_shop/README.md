# Wii Shop research

The latest [More Details recovery](descriptions.md) enables 835 original game
descriptions and 1,670 source-referenced screenshots, including alternative
image file IDs. The original scroll handler, focus and detail/back context are
preserved. A [captured generic no-results view](../../research/wii_shop_navigation_recovery_20261025.md)
now handles nonblank zero-match name queries; its Japanese keyword/search-again
state remains unverified. Out-of-range pages are distinguished from no matches.

Parallel source work adds an [offline CAS codec](soap_contract.md) and a bounded
[manual importer/reader](manual_recovery.md). Neither enables account operations
or a new manual control; the recovered guide is incomplete. The [all-region
catalog review](../../research/wii_shop_catalog_regions_validation_20261025.json)
found no additional Japanese title/icon associations beyond the existing 776.

The latest [detail/controller recovery](captured_titles.md) enables 834 captured
detail information panels and 836 original controller pages. Game-specific
ratings, controller art, genre/player/platform and date text are retained.
There are still ten legacy detail fallbacks and eight unavailable controller pages.
All 1,670 enabled routes pass live HTTPS checks; full restoration remains
unfinished under the [completion criteria](completion.md).

The [captured catalog update](captured_catalog.md) now uses the historical list
markup, scroll frame and paging controls. It preserves 776 original catalog
title-line sets and restores the original key handler and paging wrap. The
remaining 68 titles use a captured card prototype. Japanese interface copy,
exact Japanese empty-result behavior and native visual checks remain unfinished.

The latest [image-role recovery](image_roles.md) separates 776 captured catalog
icons from 835 detail images, retaining exact bytes and original page references.
It also accepts original BMP payloads. There are still 68 icon gaps and nine
detail-image gaps. The [category contract review](category_contract.md) adds
backend publisher/platform/raw-genre filters while recording missing original
picker pages; the original Japanese category UI remains unfinished.

The [title metadata update](title_metadata.md) now populates 835 captured
product names/publishers and 774 historical point amounts. It verifies internal
title IDs against captured requests and enables search by those names. One
mismatched capture is excluded; current offers and ownership remain unknown.

The latest [storefront recovery](frontend_capture.md) indexes a 2019 collector
backup and privately recovers 1,315 selected files, including thirteen shared
scripts. Japan-region detail requests match 836 of the 844 preview IDs, with
language/field verification still pending. The captured keyboard script and
observed search mode/row limit are now wired into the preview.
The home now uses the captured template and its original CSS/images, with
Japanese labels checked against Nintendo's screenshot. Accepting search clears
and blurs the input before local navigation; empty changes do not navigate.
See the [latest home validation](../../research/wii_shop_captured_home_validation_20261025.json).

**Authenticity requirement:** preserve the original Japanese assets, copy,
control meanings and flows, with no placeholder or invented replacements.
The current browsing experiment does not meet that requirement. See the
[fidelity audit and outstanding work](authenticity.md).

Updated October 25, 2026. A [local browsing checkpoint](runtime_preview.md) now
runs through the original Shop browser in an isolated Dolphin profile. It serves
844 grouped Japan titles over loopback HTTPS. The initial connectivity screen
was confirmed in-channel; an earlier three-panel home was checked
in Dolphin's native frame output. The updated captured home still needs a
native visual check. The preview includes the archived category
menus and the historical image roles above. Keyboard entry and category/detail interaction
still need hands-on checks. Purchases/downloads and a
complete replacement Shop service remain unfinished.

The latest fidelity work extracts three unchanged scripts from the installed
v21 resources, uses native localized title/menu strings and restores the
bundled hover helpers. Hash checks and JavaScript VM tests verify this wiring;
a fresh Dolphin visual check remains outstanding. The collection's development
store example is not the retail storefront. See the [source follow-up](authenticity.md#nintendo-collection-follow-up).

The first [source audit](../../research/wii_shop_audit_20261024.md) verifies
21 selected recovered client/build files against their local extraction
inventory. They document an Opera commerce bridge, SOAP service discovery,
registration/device-status flow and catalog/title-acquisition operations.
They do not establish a complete storefront/backend or a retail-client match.

Reproduce the metadata-only audit with the private recovered source root:

```powershell
python tools/audit_wii_shop_sources.py '<private shop-build-lead directory>'
python -m unittest tests.test_wii_shop_source_audit
```

An [installed-client audit](../../research/wii_shop_client_audit_20261024.md)
now identifies title `0001000248414241` version 21 (IOS 56), verifies all 18
contents against its TMD and locates bundled support pages plus static startup/
SOAP URL candidates. Interface markers overlap the recovered library, but an
exact source-revision match and runtime call order remain unverified.

```powershell
python tools/audit_wii_shop_client.py '<private Dolphin Wii NAND directory>'
python -m unittest tests.test_wii_shop_source_audit tests.test_wii_shop_client_audit
```

The [captured VC menu](captured_navigation.md) now replaces the modified
Virtual Console template and preserves the captured search/control meanings.
The [Japanese controller-image pair](localization.md) supplies the original
normal/hover artwork on 834 captured detail pages. The [latest integration check](../../research/wii_shop_navigation_integration_validation_20261025.json)
verified those selections and all 844 detail routes over local HTTPS; native
visual and Japanese-input checks are still outstanding.

The next milestone is checking the archived layout and catalog navigation in
the running original browser. Commerce services require a
separate adapter; WC24 task/mail support does not implement Shop accounts,
catalogs, tickets or content installation.

The [offline ECS GetECConfig component](ec_config.md) now parses the reviewed
request subset, including the native optional PostalCode pair, and emits explicit
response fixtures. The [original request constructor](ec_config_request.md)
confirms Version 2.0 and supplies synthetic wire to the parser. Selected v21
XML/error readers and URL setters consume synthetic fixtures in an isolated
native harness; no XML lookup or URL setter is replaced by a test double.
The [bootstrap audit](../../research/wii_shop_ec_bootstrap_20261025.md) separates
that component from the unresolved retail caller and connection sequence.
Neither the codec nor the harness is a live commerce route.
The [native origin predicates](origin_access.md) and [network initializer wrappers](../../research/wii_shop_network_initializers_20261025.md)
have separate, bounded checks. They do not establish browser permissions,
EC/plugin initialization, account connection or full startup.

Original source/software, device/account data and tickets stay outside Git.
The checked-in [audit report](../../research/wii_shop_source_audit_20261024.json)
contains metadata and protocol-name leads only. The separate loopback preview
implements HTML catalog routes, not commerce SOAP or acquisition endpoints.

[MarioCube catalog metadata](catalog.md) is now imported separately: the first
27-page snapshot retains 3,062 listings and 915 Japan-labeled browse candidates.
No title binaries were downloaded. TMD-verified title-ID mapping remains unfinished.
The metadata workbook now supplies source-reported IDs for 862 Japan candidates,
with row/hash provenance. Those mappings are not TMD-verified; missing and
conflicting entries stay unresolved.

The [catalog contract review](catalog_contract.md) separates library catalog
calls from native owned-title information. An offline query tool now groups
the mapped Japan listings into 844 distinct source-reported IDs, preserving
all versions and provenance. The preview now renders those groups in the Shop
browser; it does not implement the library's native catalog SOAP interface.

The [native URL/navigation checks](startup_contract.md) now execute v21's
original builder, formatter, URL initializer, import loop, entry branch and
browser-dispatch thunk with synthetic state. Mode 0 with zero or one argument
retains the bare host, and the selected URL reaches the `WWWOpenUrl` callback.
Browser and OS dependencies are stubbed in those isolated execution checks.
The later runtime preview separately demonstrates actual loopback browser
requests and native object initialization; full launch parameters and account
service behavior remain unverified.

The prerequisite is now identified as the `IPL.EULA` boolean. Its native getter,
indexed lookup and record parser run on synthetic cache records through URL
selection and dispatch. Missing/wrongly typed records select the bundled EULA
page, while nonzero boolean bytes preserve the Shop URL. Config loading and
browser/OS dependencies remain outside these checks; no user EULA state changes.

The [EULA/manual browser commands](bridge_contract.md) now run through the native
property getter, callback, pending-request setter, AREA decoder and dispatcher
up to an intercepted title launch. Regional destinations and preservation of
existing requests are checked. Actual channel transitions remain unverified.
