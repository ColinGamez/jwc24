# Experimental Hot Pepper category route

## Catalog-wide native list mode (October18)

Final route verification covers9400 distinct restaurant IDs, all47 prefectures,
652 municipalities and1257 category responses. Every HTTP shop list matches
its source identities and order. The largest complete response in each of47
prefectures passes native XML tree comparison; maximum stack use is4320 bytes.
The private machine-readable result is nationwide-route-verification.json.
This supersedes the earlier9398-record run before the verified ward alias.

The directory launcher now passes --directory-all-shops rather than its old
three-store manifest. The backend serves complete municipality/category lists
from the loaded source catalogs, advertises the corresponding categories, and
retains original restaurant names, addresses, descriptions and attribution.
Explicit preview manifests remain available separately; combining both modes
is rejected. Order endpoints remain unsupported.

The former25-row limit was a fixture policy, not a demonstrated native list
capacity. Native insertion at0x800BF0F4 allocates0x9C-byte linked-list nodes;
0x800BF3A0 walks that list for selection. The new native model verifier executes
those routines with mocked allocation/record copying, preserving every index
for162 rows (the largest current source group). Full directory mode permits
up to1000 rows subject to the existing256KB response bound; it never truncates.
This proves model operations, not native rendering, decoding or scrolling.

The nationwide verifier checks all municipality/category HTTP routes and exact
restaurant identity/order. It also runs the largest complete shop response in
each prefecture through the native XML parser. Images remain on-demand and
require separate live decoder/rendering verification.

Two Hamamatsu source addresses used the former Naka ward. Hamamatsu's official
2024 reorganization states that all former Naka ward is now Chuo:
https://www.city.hamamatsu.shizuoka.jp/ksh/d/sj-1.html
Only routing normalization applies this exact prefix alias. Provider display
addresses remain unchanged. No other old ward is assigned speculatively.

These changes enable catalog-wide directory responses; native menus, basket
and verified provider checkout integration are still separate unfinished work.
The source catalogs are still bounded provider snapshots, not all restaurants
in Japan. Historical preview-only restrictions below describe superseded modes.

## Nationwide catalog audit (October18)

`tools/audit_demae_directory.py` inspects every identity in all47 loaded
prefecture snapshots and writes private/demae/directory-coverage-audit.json.
The snapshots contain9400 restaurants (200/prefecture), not every provider
restaurant. The report preserves every source ID and lists unmapped genres,
unresolved municipalities, missing source images, serialization errors and
unstaged records separately. With --native-parser it verifies complete native
XML trees for bounded test batches; those batches do not implement pagination.

Explicit directory genre mappings now cover all17 observed provider labels.
Broad genres such as izakaya use native Other; unfamiliar labels remain
unmapped. This changes directory categorization, not delivery eligibility.
Missing promotional descriptions are optional; real names, addresses and
attribution remain required and no substitute description is invented.

All9400 records serialize individually. Two source addresses retain Hamamatsu's
old Naka ward name and need verified location reconciliation; they are not
silently assigned to a current ward. There are78 municipality/category groups
above the25-row preview ceiling. Native pagination, source image downloads for
uncached records and live rendering remain unverified. The launcher still
stages only its explicit three-restaurant manifest; nationwide audit success
must not be described as nationwide browsability or ordering support.

The completed native sweep verifies9398 located records in1434 bounded batches
across1257 municipality/category groups,652 municipalities and all47 prefectures.
Maximum observed parser stack use is4320 bytes. The two unresolved-location
records also pass native XML tree verification individually. These checks cover
every current catalog restaurant's XML representation, not live image decoding,
menu accuracy, checkout or complete provider coverage.

## Current executable image routing (v7)

The current staged preview is HCHJ-directory-modal-candidate-v7.wad, SHA256
f7e05616eb367c7ec83ff3fef13a69859e305c12c170d5614112441d9add92b1.
It supersedes v6. The guarded builder's --local-directory-images option replaces
the exact logo-prefix data at0x802D647B with127.0.0.1:18085/logoimg2/ and changes
the list caller's li r6,1 at0x800398E8 to li r6,0 for HTTP. Other string data and
instructions outside the existing reviewed modal/filter hooks remain intact.
The image builder is executed offline to verify the resulting local URL.

DirectoryPreview now selects this fingerprint and requires an image-capable
backend. WAD decryption verified that only contents1/2 differ from the local-API
source, matching the staged executable and directory layout. The original
default launch remains separate. Native rendering, decoder behavior and modal
close/reopen remain pending; source-image HTTP delivery is not rendering proof.

## Catalog-wide image cache

The optional --directory-image-cache now indexes every restaurant in the loaded
Hot Pepper catalogs, rather than only the three staged shop rows. The current
47 snapshots contain9400 identities:8080 usable source logo URLs and1320
provider no-image GIFs replaced by the same record's source photo_url JPEG.
Missing source art remains missing; unknown IDs never trigger provider fetches.

Known image requests fetch only the catalog-bound HTTPS provider URL, validate
JPEG limits, and atomically persist unchanged bytes plus source/hash metadata.
Repeated requests and server restarts reuse validated cached bytes. The store
serializes downloads, bounds response size and timeout, and rejects changed
cache identity or bytes. No arbitrary URL proxy or replacement artwork is used.
DirectoryPreview configures the private on-demand cache; this does not expand
staged restaurant/menu coverage or yet redirect the native image URL builder.

## Restaurant logo path and source cache

Native0x80039854 selects a shop, obtains its logo identifier through0x800C03D0
and calls0x8002C59C at0x800398EC with HTTPS enabled. The URL builder uses the
stock nwpic.demae-can.com/logoimg2/ prefix and JPEG suffix. The current directory
candidate does not redirect this path yet; source API success alone cannot
establish native row loading.

`tools/cache_demae_directory_images.py` caches unmodified logo_url JPEGs for an
explicit source selection. It restricts source and redirect hosts to HTTPS
imgfp.hotp.jp, validates bounded JPEG dimensions/size, and publishes private
bytes plus source URLs, SHA256 hashes and dimensions. The current three selected
restaurants have validated private cache entries in directory-images-v1.

The fixture's optional --directory-images cache is validated before listening;
it only admits IDs in the explicit shop preview and serves exact bytes at
/logoimg2/hotpepper:J#########.jpg. The default launcher does not enable or
redirect native logo requests. A future guarded executable change must pair
the local prefix and HTTP transport with this route before native testing.

## Preview route consistency and HTTP verification

When an explicit shop-preview manifest is configured, advertised category codes
are restricted to that municipality's staged shop responses. Full source
classification remains intact, and category-only research mode is unchanged.
This prevents the preview from offering source categories that would lead to
unsupported shop requests. Preview coverage remains the explicit manifest,
currently one Takasaki category with three restaurants, rather than all catalog
entries. Known areas outside the preview return an empty category response.

`tools/verify_demae_preview_routes.py` starts an ephemeral loopback server with
the real private snapshots and verifies root municipality membership, the town
route, registry identity, advertised category and exact selected restaurant IDs.
Area URLs are constructed by executing the fingerprinted native wrapper and
URL-builder instructions with mocked libc and HTTP submission. The current
manifest passes through all these HTTP steps with three source restaurant rows.
No orders are submitted. This is backend/native-URL integration verification,
not native screen, save or modal rendering verification.

## Known empty directory results (October16)

A registry-resolved town with no classified source entries now receives an
explicit empty CategoryList with its normal group and final apiStatus/code0.
Unknown registry IDs still receive400. This distinguishes missing catalog
coverage from a malformed request without inventing delivery availability.
Native0x8002E04C obtains the child count, and0x8002E150 skips the category loop
for zero;0x8002E164 through0x8002E17C clears errors and returns success.
The caller tests the category-model count at0x800AAB60 and selects job0x1C for
zero. The resulting stock empty-state wording still needs live review: it must
not be treated as evidence that a delivery provider has no available shops.
The category producer requires explicit allow_empty=True for this response.
HTTP tests distinguish known empty towns, populated towns and unknown codes.

The fixture server has an opt-in route for the traced action4 request:
`webApi_category_list`, `platform=wii`, `areaCode=<known replacement ID>`,
`reservationType=0`. It requires `--directory-catalogs`, `--postal-database`
and `--town-registry`. Existing default launch behavior is unchanged.

At startup, cached public Hot Pepper catalogs are validated and snapshotted.
AreaRegistry resolves a replacement ID to its known municipality. Japan Post
prefecture/city labels form an address prefix, with Unicode and whitespace
normalization, used to select restaurant records in that municipality. These
records use the existing conservative exact-label category classification.
For example, a verified directory genre 和食 maps to native category04. Unknown
genres are not forced into the Other category. No delivery radius, customer
address, payment capability, menu or reservation availability is inferred.

The response uses the existing category producer with UTF-8 CDATA and final
apiStatus placement. Different towns in one municipality share its directory
category snapshot; this is municipality-level directory coverage, not town
delivery coverage. The current partial 9,400-record cache yields supported
exact-label categories for 269 municipalities. Absence means insufficient
cached/classified directory evidence, not that the municipality has no food.

Unknown IDs, municipalities without classified cached listings, reservation
mode1, duplicate parameters and extra fields are rejected. No neighboring
prefecture or all-Japan fallback is used. Database access occurs while building
the snapshot, not per request. Health reports directory_categories separately
from restaurant_navigation and ordering_supported, both of which remain false.

This route passed real HTTP framing tests and a read-only full-cache snapshot
build. It has not been enabled in the running shared-profile launcher or
verified through the native category screen. It does not make restaurant
browsing ready for user testing. Native shop rendering still requires a
reviewed directory-mode change because the stock consumer filters shops by
cash-on-delivery support. Fabricating that payment support from Hot Pepper
directory data is not the solution; ordinary ordering remains unavailable.

Further bounded native inspection locates the exact list filter at
`0x80038DB8`: it branches to the next shop at `0x80038F28` when the supported
payment flag in r16 is zero. The flag is initialized to zero at `0x80038D38`
and set only after the exact supported-payment comparison succeeds at
`0x80038D94`. The filter is separate from later shop-status parsing and model
insertion (`0x80038EC8`). This identifies a potential directory-mode change;
it is not yet patched. Row display, selection, status wording, detail requests
and all ordering paths still need a coordinated review before bypassing it.
No cash-on-delivery value or native success state has been invented.

## Uninstalled directory-row candidate

The exact filter is now represented by a fingerprinted candidate builder,
`tools/build_demae_directory_client.py`. Against the local API DOL SHA-256
`da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830`, it checks
instruction `41820170` at `0x80038DB8` and replaces only that instruction with
NOP. It does not set the supported-payment flag, inject code, alter the DOL
header or change home/telephone/order callbacks. The staged compressed content
roundtrips to the modified DOL. This is an uninstalled candidate, not a claim
that the client now safely supports a full browsing or checkout experience.

`tools/build_demae_directory_shops.py` builds a private XML preview with real
names and catchphrases from explicitly selected Hot Pepper records, matching
the existing exact source-genre category mapping. A three-row Takasaki preview
has been generated from the cached Gunma catalog. It carries the source digest
and selected restaurant IDs in metadata. Duplicate identities, missing text,
wrong categories, unsupported native characters, invalid XML scalars and more
than 25 selected records are rejected; nothing is silently truncated.

Preview fields deliberately omit minimum prices, wait times and provider
isOpen claims. paymentList is empty. activate=stop and yoyaku=0 express the
replacement service's current ordering/reservation restrictions, not a claim
about the provider's opening hours. The catchphrase is prefixed with a visible
directory-only/ordering-unavailable note and includes Hot Pepper attribution.
homeCode and shopCode use the replacement's stable Hot Pepper directory ID,
not a purported original provider transaction identity.

An opt-in HTTP shop route has since been added; it remains disabled in the
running shared-profile service. No candidate has been installed in the
shared profile. Native stopped-row status wording, price/default-field
visibility, selection behavior, image handling and the details return path
remain to be reviewed and tested before exposing this preview. The existing
local backend continues to reject actual ordering requests.

## Explicit HTTP shop preview

`--directory-shop-previews` accepts a private selection manifest containing
municipality, category_code and restaurant_ids. It requires directory catalogs,
postal data and the area registry. The server rebuilds rows from its validated
catalog snapshot; the manifest cannot supply names, prices or payment fields.
Each selected ID must belong to that exact municipality/category. Duplicate
selections, unknown IDs, oversized lists and duplicate location/category entries
are rejected before listening. The default launcher does not enable this mode.

The route accepts only the traced action7 request with platform=wii,
isReservation=0 and selectType=1, plus one known areaCode and categoryCode.
Unknown areas, missing selections, alternate modes, duplicate/extra parameters
are rejected. HTTP tests verify names, empty paymentList, absent minimum price,
and continued rejection of order POSTs. Health exposes directory_shop_preview
separately; restaurant_navigation and ordering_supported remain false.

The real-source three-row Takasaki selection is saved privately. A WAD using
the one-instruction directory candidate and otherwise stock UI is staged but
uninstalled. It has not been tested in Dolphin and is not the default launch.

## Native selection gate

The activation string getter is `0x800C0C4C` (record+0x40). Direct-caller tracing
finds a later shop-detail/status gate at `0x800B7268` through `0x800B7290`. It compares
activation to literal `on` at `0x802D74FC` before checking the status boolean
through `0x800C2378`. A non-on activation branches at `0x800B7280` to
`0x800B72E4`, which writes error category0x5A/code1 instead of proceeding. Thus
the current honest stop rows cannot use that ordinary detail continuation.
Changing them to on or inventing an open status is not a fix for this gate.
A separate directory-selection/return path is required. This is **not the
initial list-row click**: further tracing places it in job0x521, after the
shop-detail request, parsing and status-selection worker. The earlier inference
that it was the initial click gate was too broad.

Private evidence: `directory-activate-callers.private.txt`. This bounded static
trace is not proof of all caller states or the exact rendered error wording.

## Dedicated directory-info candidate (v6)

The initial row click records the selected index at `0x8003C2B4`. Once its
selection animation finishes, `0x8003C3BC` normally selects job0x104. The steady
interactive list job is **0xFA**, dispatched to `0x800AD0B0`, not job0xF1.
The guarded candidate redirects only that transition into unused job0x53B,
whose original table target was the common exit `0x800B75C4`.

The assembled payload is 1,040 bytes in the previously reviewed original text
padding at `0x800058C0`. It verifies the selected record's `hotpepper:` namespace
and bounds the UTF-16 information string. A dedicated hidden JWC24_DIRECTORY
group and JWC24_DIR_BODY pane are added under the animated dialog window and
appended to its original system-font binding group. The stock shared message
pane and text remain untouched. The preview text now includes the source name,
address and description, the directory/ordering-unavailable note and provider
attribution. Producer text is limited to 256 UTF-16 units without truncation.

While the modal is active, the candidate draws the list with a null input cursor
and transition mode30, updates/draws the shared dialog controller with the real
cursor, and does not run ordinary shop-detail or ordering jobs. On completed
dismissal it hides only its dedicated group, resets the selected row through
the native row-state helper, and returns to job0xFA. HOME pauses the payload.
The scene4 cleanup entry at `0x800AA2DC` is separately guarded; its hook closes
an owned modal, hides the dedicated pane and preserves the native argument,
nonvolatile, CR/CTR and stack behavior before relocating the original prologue.

`tools/verify_demae_directory_modal.py` executes the compiled PowerPC bytes in
Unicorn against mocked native SDK calls. Twenty scenarios cover idle/pending
states, foreign busy dialogs, namespace/text rejection, missing pane, update,
close/return, HOME, scene transition and cleanup ownership/ABI preservation.
These checks are included in optional toolchain-dependent unit coverage; they
do not validate native SDK rendering or the surrounding callback dispatcher.

The latest staged WAD is private HCHJ-directory-modal-candidate-v6.wad, SHA-256
`45761d4665bc7a44f778824ba6b031c26723e8a56725872351a86a13db91739e`.
Only executable content1 and directory resource content2 differ from the local
API source WAD. It is uninstalled and not the default launcher. Earlier
intermediate modal candidates are superseded, especially the prototype that
wrote directly to the shared ordinary message pane. Native rendering, row
image requests, the stored-phone/setup gate and live close/reopen behavior
remain unverified. No menus, payment capability or ordering success is invented.

`tools/start_demae.ps1 -DirectoryPreview` explicitly selects the pinned v6
candidate and enables the postal registry, Hot Pepper directory and reviewed
preview selection together. It rejects phone-mode combinations and checks
read-only backend capabilities before launching in the shared profile.
The default launch remains unchanged. On 2026-10-15 the candidate reached the
native home screen in the shared Dolphin build. Selecting restaurant entry
then displayed the native invalid-phone-number gate before any category/shop
request. No stored address or phone data was changed. Live row rendering and
modal close/reopen therefore remain unverified.
