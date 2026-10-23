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

The next milestone is matching an actual retail client and proving read-only
startup/catalog browsing in its original UI. Commerce SOAP services require a
separate adapter; WC24 task/mail support does not implement Shop accounts,
catalogs, tickets or content installation.

Original source/software, device/account data and tickets stay outside Git.
The checked-in [audit report](../../research/wii_shop_source_audit_20261024.json)
contains metadata and protocol-name leads only. No server endpoints or runtime
Shop behavior are implemented yet.
