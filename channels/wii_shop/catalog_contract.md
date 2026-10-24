# Catalog, owned-title data and browsing boundary

Reviewed October 24, 2026. Seven relevant recovered files match their
extraction inventory; see the [source fingerprints](../../research/wii_shop_catalog_contract_sources_20261024.json).
The library revision is not yet established as an exact match for installed v21.

## Library catalog request

`ec_listTitles.h/.cpp` defaults to CAS operation `ListTitles`. The common
request builder sends:

| Field | Source behavior |
| --- | --- |
| `ListResultOffset` | Caller-supplied start index |
| `ListResultLimit` | Caller-supplied requested element count |
| `Attributes` | Repeated requested attribute names |
| `AttributeFilters` | Repeated name/value pairs, including API-provided filters |
| `TitleId` | Repeated 16-digit hexadecimal title IDs |

The response reader requires `ListResultTotalSize` and walks repeated `Titles`
items until the requested limit, end of list or buffer exhaustion. A missing
next item terminates successfully. Buffer overflow after at least one decoded
item is also treated as a successful partial result. This is a client parsing
rule, not a permission to omit required data within a title item.

`ec_soap.cpp` requires `TitleId` within each catalog item. The reviewed generic
item reader permits absent content, attribute, rating and pricing blocks. That
does not prove the actual Shop page can render useful entries without those
fields. Required display attributes, artwork, category conventions and real
storefront request order remain open.

The public library `EC_ListTitles` entry checks initialization, confirmed device
key-pair state, connection readiness and a nonempty account identifier before
starting the asynchronous operation. A catalog response alone does not satisfy
those prerequisites. `EC_ListTitleContents` is another operation: the reviewed
implementation fetches a TMD/content view rather than providing storefront
catalog rows.

## JavaScript and ownership are different interfaces

The reviewed `getter_ECInterface` does not expose a dedicated `listTitles`
method. Its `getTitleInfos` method calls `EC_GetTitleInfos`, which enumerates
owned titles and titles on the card using ES services. Imported MarioCube
listings must not be supplied as owned-title information.

The generic JavaScript `request` method delegates a string to an application
callback. Its presence does not establish a direct CAS listing route; that
application callback still needs tracing in the retail client. Catalog browsing
may require server-rendered pages and their original scripts. This audit does
not establish a replacement for that page flow.

## Offline query implementation

`jwc24/wii_shop_browse.py` now provides deterministic queries over the imported,
enriched metadata. It is not a SOAP serializer, server route or replacement UI.
The current private snapshot produces **844 distinct source-reported IDs** from
862 mapped Japan listings. There are **18 IDs with multiple source listings**,
including **15 with multiple source versions**. All variants and their row/hash
provenance are retained; no version is silently selected for installation.

The remaining 53 Japan candidates stay outside the mapped-ID query and are
reported as unresolved. Conflicting category/demo metadata for the same ID is
quarantined. Duplicate listing identifiers are rejected. Ownership and price
remain unknown, and all returned IDs remain source metadata, not TMD-verified
or installation-enabled titles.

Queries support offsets, category, demo policy, exact title-ID filtering and
Unicode-normalized name search. Results sort deterministically by name and ID.
The 20-item default and 50-item maximum are **offline tooling bounds**, not
recovered native page-size limits. Every real-snapshot page was checked for
complete, duplicate-free coverage of the 844 IDs.

```powershell
python -m tools.query_wii_shop_catalog private/wii_shop/mariocube-catalog-ids.json --limit 10
python -m tools.query_wii_shop_catalog private/wii_shop/mariocube-catalog-ids.json --category WiiWare --demos exclude --offset 20
```

Next: trace the retail application's catalog/page entry and establish which
of these interfaces it actually exercises. No CAS success responses, account
state, ownership, purchases or installs were added by this work.
