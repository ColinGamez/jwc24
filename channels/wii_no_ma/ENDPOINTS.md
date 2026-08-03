# Wii no Ma v1025 endpoint evidence

This map separates facts recovered from the stock `HCIJ` v1025 WAD from routes
seen in an external reference implementation. Reference routes are leads until
they are confirmed in a JWC24 runtime capture.

## Directly observed in the stock WAD

- The main executable is content index `1` (`0001-00000025.app`).
- The primary resource U8 archive is content index `2`
  (`0002-00000026.app`).
- The executable's production URL allowlist contains:
  - `http*://*.ext.wapp.wii.com/*`
  - `http*://*.nintendo.co.jp/*`
- Decompressing the v1025 content-index-1 executable as Nintendo LZ11 confirms
  its bootstrap URL is `https://wmp2v3.wapp.wii.com/conf/first.bin`.
- The resource archive contains `secure/key.bin` and `secure/iv.bin`, which are
  used by the original client for encrypted bootstrap data.
- The resource archive names a `DS_Download` scene and DSi-specific UI assets.
- The resource archive contains a `Weather` directory plus `Weather_02.lex`,
  `Weather_Mark.lex`, and `Cal_Day_Weather.lex`, confirming that weather is a
  first-class part of the original room UI.
- Named response/cache objects include:
  - `Config.bin`, `RegionInfo.bin`, and `Challenge.bin`
  - `CategoryList.bin`, `CategoryMovies.bin`, and `SearchMovies.bin`
  - `MovieMeta.bin`, `MovieStaff.bin`, `PosterMeta.bin`, and `RelatedMovies.bin`
  - paid-content equivalents including `PayMovieMeta.bin` and
    `PayCategoryList.bin`
  - `DeliveryAgree.bin`, `CouponAgree.bin`, `SpPage.bin`, and `SpPageList.bin`

All 16 decrypted contents passed the SHA-1 values in the stock TMD before this
evidence was collected.

## Confirmed bootstrap contract

The external `room-server` implementation exposes `GET /conf/first.bin`. The
universal client delta changes the stock URL to
`http://prod.wiilink24.com/conf/first.bin`, independently confirming the same
path. Its
encrypted XML config supplies three service roots (`url1`, `url2`, and `url3`),
an eShop URL, feature limits, and a server update timestamp. This structure is
consistent with the `Config.bin` object and the stock archive's key/IV files.

Likely service split:

- `url1`: static metadata and media paths
- `url2`: interactive CGI requests
- `url3`: paid/theatre metadata and media paths

Examples present in the reference server include `/url2/reginfo.cgi`,
`/url2/search.cgi`, `/url2/evaluate.cgi`, `/url1/event/today.xml`, and
`/url1/movie/...`. These are not yet claimed as independently verified JWC24
routes.

JWC24 now serves an AES-128-CBC/PKCS#7 encrypted v1025 bootstrap at that route.
The client build uses a fixed-width LAN replacement URL and the response points
`url1`, `url2`, `url3`, and `shopurl` at the same JWC24 host.

## Next runtime checks

1. Install the privately rebuilt v1025 JWC24-LAN WAD in the isolated Dolphin NAND.
2. Capture the bootstrap request's exact `User-Agent`, method, and query string.
3. Record the first request made through each returned service root.
4. Compare every observed XML node and binary cache filename with the stock
   resource evidence.
5. Trace whether weather is read from Forecast Channel NAND data or requested
   through Wii no Ma's service roots, including its behavior when Forecast data
   is missing or stale.
6. Promote a route into the JWC24 manifest only after that confirmation.

## Local research artifacts

The decrypted contents and cloned reference server are stored below `private/`
and are ignored by Git. Neither is part of the public JWC24 source tree.
