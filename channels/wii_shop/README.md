# Wii Shop research

Updated October 24, 2026. This is a new research track; JWC24 does not yet
provide a working replacement Shop service.

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

The next milestone is capturing that client's startup sequence in an isolated
profile, then proving read-only startup/catalog browsing. Commerce services require a
separate adapter; WC24 task/mail support does not implement Shop accounts,
catalogs, tickets or content installation.

Original source/software, device/account data and tickets stay outside Git.
The checked-in [audit report](../../research/wii_shop_source_audit_20261024.json)
contains metadata and protocol-name leads only. No server endpoints or runtime
Shop behavior are implemented yet.

[MarioCube catalog metadata](catalog.md) is now imported separately: the first
27-page snapshot retains 3,062 listings and 915 Japan-labeled browse candidates.
No title binaries were downloaded. Native catalog integration and verified
title-ID mapping remain unfinished.
The metadata workbook now supplies source-reported IDs for 862 Japan candidates,
with row/hash provenance. Those mappings are not TMD-verified; missing and
conflicting entries stay unresolved.

The [catalog contract review](catalog_contract.md) separates library catalog
calls from native owned-title information. An offline query tool now groups
the mapped Japan listings into 844 distinct source-reported IDs, preserving
all versions and provenance. It is not yet a native catalog endpoint or UI.

The [native URL/navigation checks](startup_contract.md) now execute v21's
original builder, formatter, URL initializer, import loop, entry branch and
browser-dispatch thunk with synthetic state. Mode 0 with zero or one argument
retains the bare host, and the selected URL reaches the `WWWOpenUrl` callback.
Browser/configuration dependencies are stubbed. Actual launch parameters,
HTTP requests and browser rendering remain unverified.
