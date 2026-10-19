# Nationwide catalog regions

The catalog manifest covers Japan's 47 prefectures using `JP-01` through
`JP-47`. These identifiers are internal catalog identifiers, not recovered
Demae `areaCode` values. Original HCHJ area coverage and the native XML hierarchy
remain unverified; a prefecture record does not establish delivery availability.

Generate the private manifest:

```powershell
.venv/Scripts/python.exe tools/build_demae_regions.py
```

Each region starts with `catalog_status: not_imported`. The existing Takasaki
OSM snapshot remains a local snapshot, not prefecture-wide coverage.

Recruit's [area master API](https://webservice.recruit.co.jp/doc/hotpepper/reference.html)
provides `large_area` names and codes. Given a saved JSON response from that API:

```powershell
.venv/Scripts/python.exe tools/build_demae_regions.py --provider-master private/demae/hotpepper/areas.json
.venv/Scripts/python.exe tools/import_hotpepper_catalog.py --large-area Z011 --output private/demae/hotpepper/tokyo-page1.json
```

The mapping requires exactly one match for every prefecture and rejects duplicate
codes, ambiguous names and missing prefectures. Provider codes must come from
the master rather than being inferred from prefecture numbers. Restaurant
imports require `JWC24_HOTPEPPER_API_KEY`; each invocation fetches one page of at
most 100 records. A page is not a complete prefecture catalog. Nationwide
restaurant population, pagination and native Demae presentation are pending.

## Nationwide first-page import

`tools/import_hotpepper_regions.py` fetches the live area master, validates all
47 mappings, and caches the first restaurant page for each prefecture. It
waits between requests and resumes completed prefectures on subsequent runs.
The key comes from `JWC24_HOTPEPPER_API_KEY` or the ignored local file
`private/demae/hotpepper/api-key.txt`. Neither request URLs nor credentials are
included in generated catalogs or failure output.

```powershell
.venv/Scripts/python.exe tools/import_hotpepper_regions.py --pages 2
```

The page budget defaults to one and can be raised to at most 100 per prefecture.
The importer stops when provider pagination reports the last page, deduplicates
overlapping IDs, and publishes a combined catalog for each prefecture.
`private/demae/hotpepper/regions.json` reports actual cached counts and distinguishes
partial coverage from reaching the provider's reported end. Existing pages are
reused; remove a specific private page cache to explicitly refresh it. Older
pages without pagination metadata cannot prove completeness. These changing
provider snapshots do not establish every restaurant in a prefecture, delivery
availability, or native Demae integration.
