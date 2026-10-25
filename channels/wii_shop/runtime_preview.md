# Local Shop browsing checkpoint

**Fidelity status:** this experiment includes adapted labels, repurposed
controls and placeholder values/images. It does not meet the owner's original
experience requirement. The [authenticity audit](authenticity.md) records those
gaps and the evidence needed to resolve them.

The latest [description recovery](descriptions.md) restores 835 More Details
pages and 1,670 original screenshots. Its verified detail buttons return to the
same title/list context, and the captured scroll-only handler runs without the
account initialization script. Nonblank zero-match name queries use the
[captured generic no-results view](../../research/wii_shop_navigation_recovery_20261025.md).
Exact Japanese keyword/search-again behavior remains unverified.

Updated October 25, 2026. The original v21 Shop browser has reached JWC24's
loopback HTTPS service in Dolphin. The initial connectivity screen rendered at
608 × 456 and reported successful native Shop/sound initialization; the user
also confirmed it visually. That handmade screen has been removed. The current
renderer binds the catalog into archived Shop layouts and artwork. An earlier
three-panel home was inspected in Dolphin's own frame output at 640 × 480,
with the browser viewport reporting 608 × 456. The current captured-home
template/style update still needs its own native visual check.

This is a read-only browsing experiment in a privately patched Dolphin profile.
It is not the clean-WAD restoration milestone, an acquisition service or a
working replacement for Shop accounts, points, tickets or installation.

## Pages and original artwork

The current local pack (`artwork-v2`) contains 71 resources from the
[Shop website archive](https://wiishopchannel.net/): `W_03.html`, `B_04.html`,
`B_05.html`, category menus `B_01.html` / `B_27.html`, shared CSS, button graphics,
shadows and other page artwork.
The three-panel home, catalog-card and detail-page layouts come from those
files in the earlier preview. The home now uses the reviewed 2019 capture and
its matching CSS/images. Populated catalog lists now also use the [reviewed
historical capture](captured_catalog.md), retaining 776 original catalog title-line
sets and the original scroll/page-key handler. The [title-page integration](captured_titles.md)
replaces 834 detail views and adds 836 controller pages. Category, ten detail
fallbacks, non-keyword/out-of-range states and explanation pages still use the interactive archive.
That archive contains later edits; this is not a claim of an untouched
Nintendo server snapshot. Two shared images, `spacer.gif` and
`under_banner_shadow.gif`, also match the installed original channel byte-for-byte.

Rendered stylesheet links now use the captured global/detail CSS even on the
remaining experimental templates. The modified global CSS added three web-font
rules referencing an unavailable `font2.ttf`; the captured stylesheet keeps the
original native font declarations. Captured inline CSS common-image URLs also
resolve through the captured asset pack. This removes the recreation's font
dependency without claiming that the remaining experimental HTML is original.

Third-party archived scripts and event handlers are discarded. Three unchanged
scripts from the installed v21 resource archive (`sound.js`, `common.js`,
`shop.js`) now initialize the native sound/Shop objects and supply the original
image-swap helpers. A small ES3 service adapter handles initialization,
search wiring, diagnostics and local navigation. A reviewed captured
`keyboard.js` now supplies the native keyboard object and constants; the search
mode and row limit follow the captured retail handler. See the
[capture recovery and limits](frontend_capture.md). The home heading and
Wii Menu button use `shop.title` and `shop.menuBtn` from the native client rather
than handwritten Japanese. Hover handlers use the bundled image-swap functions
and sound constants. The scripts are served byte-for-byte, with pinned SHA-256
checks; the replacement adapter remains JWC24 code. Catalog
names and links are escaped before insertion. Japanese labels and read-only
status messages replace unavailable server values. Unknown points, publishers,
dates and player counts are not invented.

The [historical title cache](title_metadata.md) now supplies accepted captured
names/publishers for 835 IDs and point amounts for 774. Current offers and
ownership remain unknown; captured dates are not treated as Wii release dates.
A [historical image-role cache](image_roles.md) now supplies **776 catalog icons**
and **835 detail images**, using separate references from captured list/detail
pages. The previous single-image mapping was incorrect for many slots. There
are still 68 icon gaps and nine detail-image gaps using the original transparent
spacer; these remain unfinished work. No replacement pictures are generated. The Wii
Channels panel currently leads to the scope explanation because this snapshot
only contains mapped Japan WiiWare/Virtual Console candidates.

Original HTML, CSS, images and software remain under `private/`. Git contains
the importer, bindings and tests. Each cached resource has a source URL, length
and SHA-256; altered resources are rejected before serving. Title image mappings
also retain the catalog digest, exact archive member and referencing-page hash, with bounded byte sizes,
dimensions and image-format validation. The native frame confirms the archived
home; category navigation, keyboard entry and detail-page interaction still need
hands-on checks in the channel.

The home now opens the archived WiiWare/Virtual Console selection menus before
listing titles. Their original button geometry and artwork are retained. The
working bindings provide a software list, WiiWare demos and the original search
banner's input with a native keyboard call. Search uses the catalog's normalized
name filter and preserves the category. Back links return from details to the
same filtered page and from the list to its category menu. Popularity/release-date
ranking and complete publisher/genre browsing remain unimplemented. The
[category backend](category_contract.md) supports exact publisher/platform/raw
genre-text filters and preserves them through list/detail/back navigation;
original picker UI and genre-code mappings remain unfinished. Captured
publisher names now populate individual items. The current list/demo labels are adapted to these
available data fields rather than claiming the complete original menu behavior.
Populated lists now restore the captured paging wrap and frame focus. Their
captured caption remains English, and 68 unmatched titles use a captured card
prototype. Original Japanese interface copy and native rendering remain work.

## Profile and credentials

Before starting the updated service, prepare its private native script pack:

```powershell
python -m tools.import_wii_shop_native_assets '<original installed Dolphin Wii directory>'
```

This verifies the installed contents against their TMD, requires the known v21
resource fingerprint and extracts only those three unchanged scripts into a
new `private/wii_shop/native-assets-v1` directory. It refuses overwrite and
does not read keys, tickets or account saves. The server requires this pack;
the launcher rejects an older listener without native scripts. JavaScript VM
checks verify object initialization, native string binding, image hover/restore
and returning to the menu with synthetic browser/native dependencies. The new
script wiring still needs a Dolphin visual check; earlier frame evidence
predates this change.

The updated service also requires the reviewed private storefront capture at
`private/wii_shop/frontend-capture-v1`. Its [import procedure](frontend_capture.md#reproduce-privately)
checks the collector archive and extracts selected files into a hashed store.
Among scripts, the server exposes only the fingerprint-pinned keyboard script from that store;
the remaining captured commerce scripts are not enabled. The same reviewed
pack now supplies the captured home template and 420 validated shared CSS/image
files through mirrored local paths. Keyboard input and
the full Japanese prompt/submit/cancel flow remain unverified in Dolphin.

After importing the capture, run `python -m tools.build_wii_shop_title_metadata`
to prepare `private/wii_shop/title-metadata-v2/metadata.json`. The service requires
that cache to match both the catalog and capture-manifest fingerprints. The
launcher also compares its running digest with the local file. See the
[acceptance checks and limits](title_metadata.md).

Also prepare the [separate historical image roles](image_roles.md#reproduce-privately)
at `private/wii_shop/title-artwork-v4`. The server and launcher require its
matching manifest; older flat image packs do not satisfy that check.
The same import sequence supplies `frontend-japan-catalog-v2`, now required by
the populated catalog renderer. The launcher checks its running manifest digest.
Also run the [controller import and title-page index builder](captured_titles.md#reproduction-and-checks)
to prepare `frontend-title-support-v1` and `title-pages-v2/index.json`. Their
bindings are required by the updated server and checked by the launcher.

Import the all-region catalog evidence and the description pack into new private
directories before starting the latest service:

```powershell
python -m tools.import_wii_shop_frontend_capture '<private archive.7z>' --listing '<private listing.txt>' --catalog-only --output private/wii_shop/frontend-all-catalog-v1
python -m tools.import_wii_shop_descriptions '<private archive.7z>' --listing '<private listing.txt>' --output private/wii_shop/descriptions-v2
```

The first supplies the pinned generic no-results view; the second recovers only
source-proven B05/B06 pairs and their exact referenced screenshots. Both manifest
digests are checked by the launcher. Existing outputs are refused.

`tools.prepare_wii_shop_preview` copies Config/Wii into a new private profile.
It audits the source Shop's 18 contents, replaces 20 Shop URL fields with
`https://127.0.0.1:18443`, and changes the copied Opera URL filter and CA store.
Only content indices 1 and 2 are modified. Their sizes/hashes are updated in
the copied TMD and all referenced contents are rechecked. The patched TMD's
Nintendo signature is not valid or verified; this is a Dolphin-only experiment.
The source title is checked again to confirm it was not changed.

Dolphin initially refused to boot without owner-supplied device credentials.
With the user's authorization, `tools.prepare_vwii_credentials` mapped the Wii
banks of their **Wii U OTP** into the BootMii structure Dolphin reads. It writes
only a new `Wii/keys.bin` inside the marked private preview profile, rejects
existing outputs/default or empty fields, and verifies the source is unchanged.
No raw NAND image was imported, no actual Wii backup was used, and no key or
console-ID values are printed. Real account authentication remains untested.

Format references: [Dolphin IOSC](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/IOSC.cpp),
[ShowMiiVWiiKeys](https://github.com/CuriousTommy/ShowMiiVWiiKeys).

## Transport finding

Forcing `Connection: close` on each HTTPS response produced five repeated Opera
GETs and a blank screen, followed by watchdog error 209601. Keeping HTTP/1.1
connections open with accurate `Content-Length` headers allowed CSS, JavaScript
and the native-ready beacon to load. The persistent-connection behavior is now
covered by a live-listener regression test.

The listener binds only IPv4 loopback. Its private development CA is trusted
only by the copied Opera resources. Certificate verification stays enabled;
TLS 1.0 and legacy ciphers are enabled on this local listener for compatibility.
No system trust store or real-console settings are changed. Request diagnostics
retain route categories, method, status, byte count, TLS version and an agent
family, excluding query strings, identifiers, headers and bodies.

The native page adapter retains `shop.connecting` in a variable to cancel the
page timer. See the [Open Shop Channel bridge documentation](https://docs.oscwii.org/wii-shop-channel/js/shop).
The Opera CA-store format follows
[WSC-Patcher](https://github.com/OpenShopChannel/WSC-Patcher/blob/main/modify_arc.go);
its MIT notice is retained in [third_party](../../third_party/wsc-patcher.LICENSE).

## Reproduction

Tested with libWiiPy 0.6.0, PyCryptodome 3.23.0, OpenSSL and the existing v21
installation. Close Dolphin before making the initial profile copy.

```powershell
python -m tools.import_wii_shop_artwork
python -m tools.import_wii_shop_native_assets '<original installed Dolphin Wii directory>'
python -m tools.prepare_wii_shop_preview
python -m tools.prepare_vwii_credentials --otp '<your Wii U backup>\otp.bin'
powershell -File tools/start_wii_shop_preview.ps1
```

Prepare the captured frontend, metadata and historical image-role caches using
the linked procedures before the first launch. The old modified-site title-image
import is retained for comparison and is no longer the default runtime pack.

The import/preparation tools refuse existing destination packs/profiles or
credential files. Do not rerun them over a working profile. For subsequent
launches, run only the launcher. `-ServerOnly` updates service availability
without opening or closing Dolphin. Existing Dolphin instances are never
stopped by the launcher.

Browse categories, scroll the catalog, open a title and return to the list.
Acquisition/account controls lead to the scope explanation or remain unavailable;
they do not contact payment or account services.

The image importer uses Pillow from the existing `artwork` optional dependency.
Normal preview launches explicitly disable frame dumping; temporary test videos
were removed after retaining a private native proof image.

Validation: 198 Shop tests and 2 credential tests pass. All 85 catalog pages and 844 title pages were
rendered against the real snapshot; title links cover all 844 grouped IDs once.
All 1,611 current image routes were checked over verified loopback HTTPS. See the
[image-role report](../../research/wii_shop_image_roles_validation_20261025.json)
and [initial transport report](../../research/wii_shop_preview_validation_20261024.json).
The [native script update report](../../research/wii_shop_native_scripts_validation_20261025.json)
separately records exact bytes served over verified loopback TLS, script load
order and native text bindings. It explicitly leaves the updated Dolphin
visual check and complete-original-storefront verification outstanding.
The [captured home report](../../research/wii_shop_captured_home_validation_20261025.json)
records the newer template/style selection, 20 live dependency checks,
screenshot-backed Japanese copy and search-callback verification. Its native
visual check remains explicitly outstanding.
The [title-data report](../../research/wii_shop_title_metadata_validation_20261025.json)
records all-page checks with the accepted metadata, all 835 captured-name
searches and three live detail/search pairs. Native visual verification remains
outstanding.
The [captured catalog report](../../research/wii_shop_captured_catalog_validation_20261025.json)
adds 85 live catalog pages, 799 dependencies, original title-line preservation,
835 name searches and original navigation-handler VM checks. Native visual
verification and complete-original-storefront verification remain outstanding.
The [detail/controller report](../../research/wii_shop_captured_titles_validation_20261025.json)
adds all 834 captured detail and 836 controller routes, 882 dependencies and
game-specific information/return-path preservation. It leaves Japanese copy,
native visual verification and complete commerce explicitly unfinished.
The [combined integration report](../../research/wii_shop_parallel_integration_validation_20261025.json)
checks all 835 description routes, 1,670 original screenshots, 834 More Details
links, all catalog/detail/controller pages, generic no-results cases and shared
dependencies over verified local HTTPS. The [SOAP codec](soap_contract.md) and
[partial manual reader](manual_recovery.md) remain disconnected from live
account/manual routes. Native visual verification is still outstanding.

The [VC navigation update](captured_navigation.md) uses the pinned B01 menu
and all twenty original display/hover/CSS dependencies. Unsupported popularity,
release-order and category-gateway controls keep their original meaning rather
than becoming unrelated list/demo filters. The WiiWare menu remains the older
experiment. The [localization update](localization.md) selects the verified
Japanese controller-image family only when the source uses its matching English
normal/hover pair, including normalized doubled slashes in captured paths.
The [navigation integration report](../../research/wii_shop_navigation_integration_validation_20261025.json)
records 886 certificate-verified HTTPS requests, all 844 detail routes and 834
Japanese normal/hover selections. This is service verification, not native
rendering evidence. No Dolphin process was launched for that check.

The launcher checks the navigation manifest as well as the other private packs.
`-ServiceStartupTimeoutSeconds` defaults to 120 (range 5–300) to accommodate
observed slow cold reads; a service that exits is reported immediately. An
existing listener must still pass all TLS/pack health checks before a launch.
