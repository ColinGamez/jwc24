# Wii Shop research

Updated October 24, 2026. A [local browsing checkpoint](runtime_preview.md) now
runs through the original Shop browser in an isolated Dolphin profile. It serves
844 grouped Japan titles over loopback HTTPS. The initial connectivity screen
was confirmed in-channel; the current renderer uses archived Shop layouts and
artwork and still needs its native visual check. Purchases/downloads and a
complete replacement Shop service remain unfinished.

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

The next milestone is checking the archived layout and catalog navigation in
the running original browser. Commerce services require a
separate adapter; WC24 task/mail support does not implement Shop accounts,
catalogs, tickets or content installation.

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
