# Historical storefront capture

October 25, 2026. A separate collector backup provides a stronger storefront
reference than the modified interactive website used by the preview so far.
The [Internet Archive item](https://archive.org/details/WiiShopChannelBackup)
was uploaded in January 2019 and describes captures through January 27, with
later manual/icon additions and minor cleanup. It is a historical capture,
not recovered Nintendo server source or a signature-verified retail package.

## Recovered material

The downloaded archive is **1,668,780,381 bytes** and matches the SHA-1 in the
item's file metadata. Its listing contains **334,441 files**, with about
8.17 GB declared uncompressed size. We recovered only **1,315 selected files**
totaling **66,646,973 bytes** into a private hashed store. Each selected payload
matches its listed size and CRC and has a SHA-256 fingerprint. These are
selected-member checks, not decompression/CRC verification of every archive file.

The selection includes shared graphics/styles, thirteen shared scripts and
selected navigation/detail captures. Scripts include `oss.js`, `ec.js`,
`title_manager.js`, `shopsd.js`, `keyboard.js`, button/image helpers and the
web variants of Shop/sound helpers. They remain private. Their presence does
not establish that their native calls or account services work against JWC24.

Of 868 selected detail requests with `country=JP` matching IDs in the broader
source catalog, **836 match the preview's 844 grouped Japanese title IDs**.
This is a request-filename association, not independent verification against
each page's internal title state or signed title metadata. Several reviewed
Japan-region captures contain Japanese title/category data but English
interface captions. Historical prices are not current purchase offers, and a
displayed release date may refer to the original game rather than its Wii release.
These fields need semantic review before feeding the renderer.

The [metadata report](../../research/wii_shop_frontend_capture_20261025.json)
records inventory counts, archive/script fingerprints, review limits and current
checks. Original bodies and captured query strings are excluded from Git.

## Keyboard integration

The preview now serves the reviewed captured `keyboard.js` unchanged, with its
Shift-JIS charset and a pinned SHA-256. It initializes the native keyboard once;
the service adapter uses that object and its original constants. The captured
`B_01.jsp` search handler selects predictive input and a five-row limit. Those
parameters replace the previous guessed mode/limit. The original Japanese
prompt and complete submit/cancel behavior still need recovery and validation.

JavaScript VM checks exercise the captured initializer and adapter against
synthetic native/browser objects. Live loopback HTTPS checks verify the exact
served bytes, charset and load order. Actual typing, Japanese conversion,
accept/cancel and navigation still need a Dolphin check. Other captured
commerce scripts are retained for review and are not enabled in the preview.

## Reproduce privately

Download `oss-auth.shop.wii.com.7z` from the item above into a private research
directory. Generate a technical listing using 7-Zip, then inspect/import it:

```powershell
& 'C:\Program Files\7-Zip\7z.exe' l -slt -ba '<private archive.7z>' | Set-Content -Encoding utf8 '<private listing.txt>'
python -m tools.inspect_wii_shop_frontend_backup '<private listing.txt>'
python -m tools.import_wii_shop_frontend_capture '<private archive.7z>' --listing '<private listing.txt>' --output private/wii_shop/frontend-capture-v1
```

The importer requires the known archive size/checksum, bounds the selection to
128 MiB and 4,000 files, and refuses existing output directories. It streams
selected bytes through 7-Zip instead of extracting URL filenames onto Windows.
Each output filename is a content hash; size/CRC checks detect ordering or
selection mismatches. The private manifest preserves source-member provenance.
Recovered scripts are not executed by the importer. The original Nintendo
collection and Wii/vWii backups are not modified.
