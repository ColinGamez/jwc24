# MarioCube catalog metadata

MarioCube is the user-selected catalog source. The first import, on October
24, 2026, read 27 alphabetical listing pages in its
[WiiWare/VC/channel/IOS directory](https://repo.mariocube.com/WADs/_WiiWare%2C%20VC%2C%20DLC%2C%20Channels%20%26%20IOS/).
It retained **3,062 file listings**, of which **915** are Japan-labeled WiiWare
or Virtual Console browse candidates without the DLC tag. Demos remain
explicitly labeled. These are filename observations, not verified unique title
IDs, installation targets or a claim of complete Japanese Shop coverage.

The repository also has `_Clean` and other separate branches. Its
[structure notes](https://repo.mariocube.com/WADs/_WiiWare%2C%20VC%2C%20DLC%2C%20Channels%20%26%20IOS/README.md)
distinguish those branches from the alphabetical set. This first snapshot does
not import the separate branches, system-software tree, custom injects or DLC
collections. Duplicate versions/regions are retained as separate source rows.

`jwc24/wii_shop_catalog.py` parses the listing table without following file
links. It retains source page/link, filename tags, listed size and source
modification text. Japan/category/demo/DLC values are explicitly filename
labels. Missing title ID, publisher and price remain null; TMD verification
and install support remain false. No title data is inferred from file size.

`tools/import_wii_shop_catalog.py` fetches listing pages only, with three
concurrent requests, bounded HTML size, timeouts and redirects restricted to
equivalent encodings of the same listing URL. Unexpected formats, links or
sizes fail the import before replacing the existing snapshot. Output stays
under `private/`; no WAD, ticket or content binary is fetched.

```powershell
python -m tools.import_wii_shop_catalog --output private/wii_shop/mariocube-catalog.json
python -m tools.import_wii_shop_catalog --buckets A --output private/wii_shop/mariocube-A.json
python -m unittest tests.test_wii_shop_catalog
```

The private snapshot records fetch time and each listing page's SHA-256.
It is a discovery catalog, not yet connected to the native CAS/catalog
interface. Next steps are verified title-ID mapping, source-version handling
and original-channel catalog rendering. Content delivery/installation remains
a separate integration target.

## Source-reported title IDs

The directory's [metadata workbook](https://repo.mariocube.com/WADs/_WiiWare%2C%20VC%2C%20DLC%2C%20Channels%20%26%20IOS/WAD%20Info.xlsx)
contains 2,900 rows in `database`. The mapper reads only columns A:D: filename,
title ID, version and region. Other workbook columns are not exported into the
catalog. The source workbook remains unchanged under `private/`.

The first mapping enriches **2,597 of 3,062 listings**, including **862 of 915
Japan browse candidates**. Among the remaining Japan candidates, 51 lack exact
filename matches and two have region conflicts. Across all listings, 399 lack
matches and 66 have region conflicts. No approximate name or cross-region match
is chosen. A source worksheet is not independent proof of a title's contents.

`title_id_status=source_metadata` distinguishes a workbook match from TMD
verification. Each match records the source URL, workbook SHA-256, sheet,
columns and row. Version zero is preserved. Invalid IDs/versions, duplicate
filenames and region conflicts remain unresolved with an explicit reason.
Prices and publisher data are not invented. Installation stays unsupported.

```powershell
python -m tools.map_wii_shop_catalog_ids private/wii_shop/mariocube-catalog.json "private/wii_shop/WAD Info.xlsx" --output private/wii_shop/mariocube-catalog-ids.json
python -m unittest tests.test_wii_shop_catalog_ids
```

The read-only XLSX reader uses bounded ZIP/XML parsing and requires the expected
sheet/header. It rejects catalog-cell formulas and unsupported worksheet paths.
All 2,900 selected rows were independently compared with a read-only workbook
reader and agreed exactly. No binary title downloads, ticket import or native
catalog changes occur during this mapping step.

## Offline browsing queries

The [catalog query layer](catalog_contract.md) groups mapped listings by title
ID without selecting an installation version. It supports stable pagination,
name search, category/demo filters and exact-ID queries. The first snapshot
contains 844 distinct mapped Japan IDs; all source variants remain visible.
It neither supplies owned-title information nor implements the retail page flow.
