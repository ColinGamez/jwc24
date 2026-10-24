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
