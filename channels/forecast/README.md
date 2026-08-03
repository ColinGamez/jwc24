# Forecast Channel (Japan)

JWC24 restores the stock Japanese Forecast Channel before Wii no Ma because the
room UI consumes weather state from the Wii ecosystem.

## Installed client baseline

- Title ID: `00010002-4841464A` (`HAFJ`)
- Version: `7`
- Required IOS: `31`
- Region: `JPN`
- Installed in the active Dolphin NAND as a bundled system channel

The title currently has an empty data directory and no entries in
`nwc24dl.bin`, indicating that it has not completed its first-run setup in this
NAND.

## Direct executable evidence

The stock v7 executable contains these URL formats:

```text
http://weather.wapp.wii.com/%d/%03d/forecast.bin
http://weather.wapp.wii.com/%d/%03d/short.bin
```

It calls the native WC24 download APIs and names both files explicitly. The
Japanese first run confirmed that the first numeric field is language (`0` for
Japanese) and the three-digit field is country (`001` for Japan):

```text
http://weather.wapp.wii.com/0/001/forecast.bin
http://weather.wapp.wii.com/0/001/short.bin
```

The client registered these as native WC24 slots 3 and 4 with destination
files `3.bin` and `4.bin`. The original host is offline, producing error
`107305` after task registration.

## Bring-up order

1. Recover and independently validate `forecast.bin` and `short.bin` formats.
2. Generate current Japanese weather, including Gunma/Takasaki, through the
   native WC24 path.
3. Let the stock channel complete its location-selection flow from the restored
   Japanese location table.
4. Confirm the Forecast Channel banner and full UI update correctly.
5. Confirm Wii no Ma reads and displays the same weather state.

The stock WAD remains immutable, but a patched working copy is required for
live replacement data. The client verifies the 320-byte payload envelope with
Nintendo-era RSA trust material; Nintendo's corresponding private key is not
available. A reference binary comparison confirms changes to the two endpoint
strings, code references, and 512 bytes of replacement trust data.

JWC24 will generate its own private signing key under ignored private storage
and patch only a working copy of content `0000000d.app` to trust the matching
public key and JWC24 endpoint. The signature check will remain enabled; it will
not be bypassed. The stock installed content and WAD are preserved for rollback
and reproducibility.

`tools/patch_forecast_trust.py` creates that minimal working-copy trust patch;
it does not redirect Nintendo URLs or disable verification. The matching
private key is never embedded, committed, logged, or distributed.
`tools/sign_forecast_payload.py` adds the expected 64-byte reserved prefix and
RSA-2048/SHA-1 signature to an LZ10 payload.

For Dolphin testing, `tools/rebuild_nand_title_wad.py` reconstructs a private
installable WAD from an existing NAND title, resolves shared contents through
`shared1/content.map`, replaces only requested content indices, updates their
TMD records, and fakesigns the modified TMD. The generated WAD remains under
ignored private storage; rebuilding it does not alter or install into the NAND.

The location generator is country-wide and has no preferred city.
`tools/import_forecast_locations.py` preserves region/location ordering from an
archival XML catalog, and `tools/build_forecast_locations.py` converts the
normalized JSON into the native binary table. Takasaki is only used as a
validation lookup alongside other Japanese cities.

Current conditions use the same provider-neutral boundary:
`tools/build_forecast_short.py` accepts normalized records keyed by the catalog
IDs and emits native LZ10 data. Provider-specific acquisition code and raw
responses remain private; the public builder neither imports nor knows about a
Weathernews endpoint.

`tools/build_forecast_full.py` joins that catalog with normalized today,
tomorrow, six-hour, wind/index, and seven-day records. It rejects duplicate or
unknown location keys before emitting the native long-forecast table.

Generated signed payloads are checked independently before delivery:

```powershell
py -3 tools\validate_forecast_payloads.py private\forecast\generated\forecast.bin private\forecast\generated\short.bin --find-location 高崎市
```

The validator checks the 320-byte signature envelope boundary, Nintendo LZ10
stream, declared file size, CRC-32, validity timestamps, locale fields, and
table bounds. `forecast.bin` and `short.bin` must agree on country and language.

JWC24 must not preselect a city or write a preferred location into `SYSCONF`
or channel save data. The complete Japanese location table is delivered, and
the user chooses their area through the original Forecast Channel setup UI.

## Weather-data source policy

Weathernews is the preferred provider because it supplied the original Wii
Forecast service and still publishes detailed Japanese local forecasts. The
project owner has privately obtained written authorization to use
`weathernews.jp` for JWC24, subject to keeping Weathernews-specific code and API
details confidential.

The public generator keeps acquisition behind a generic provider interface.
The Weathernews acquisition adapter, selectors, endpoint details, credentials,
and captured responses must remain under ignored private storage and must not
appear in Git history, logs, tests, fixtures, or documentation. Only normalized
weather records may cross into the public Wii-format generator. Every generated
payload must retain private source and transformation provenance outside the
binary.
