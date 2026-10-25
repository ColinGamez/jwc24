# Retail v21 commerce surface audit

Reviewed October 25, 2026. **The existing offline CAS codec is not a complete
retail-v21 request contract and must remain disconnected.** The original v21
ListTitles builder has extended filtering and ordering fields absent from the
recovered older library. This audit adds evidence and reproducible inspection,
without enabling a commerce route or simulating account/entitlement success.

The [metadata report](../../research/wii_shop_commerce_surface_20261025.json)
records executable/container/overlay fingerprints, 15 inventory-verified private
source files, allowlisted marker locations and bounded native references.
Original files and derived disassembly remain private. No original program or
script ran; no browser, service, device/account state or credentials were read.
Only explicitly selected installed content files were inspected read-only.

## Concrete retail files and limits

The main DOL matches the installed-client audit's SHA-256
`aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898`.
The isolated preview executable has a different fingerprint and was not used
as the original comparison target.

The original browser container has SHA-256
`7cebfa18a7b7525d25a9ebf407b648e13e4fa2470b6c628fd7f1e007adb2faa8`.
Its `wwwlib-rvl.lz7` member has SHA-256
`5742df998f3bcf4545e4a7ba1df591a11b76e660087fd3ceb2cdf8f90582fefe`;
the 9,130,272-byte decompressed overlay has SHA-256
`703a9810ee62c0a3c6675a4ebaa14ef498759dbc8c274e74be2f9ddf1512f514`.
It contains no occurrences of the selected ListTitles/GetTitle commerce markers
or ECommerceInterface/getTitleInfos/downloadTitle names. This places the reviewed
commerce family in the main executable; marker absence is not a proof of all
possible browser behavior or dynamically constructed names.

Inspection follows fixed slices in this fingerprinted executable. Relative
string references decode one instruction form against a manually reviewed
constant base; they are static candidates, not general control-flow proofs.
The report distinguishes complete stored literals from NUL-terminated suffixes:
the compiler can share a substring, and a native pointer to that substring is a
valid C string. The synthetic tests cover this distinction.

## ListTitles is present; retail invocation is still unproven

Constructor `0x800A39D0` references the default `ListTitles` action. The identified
direct caller is environment setup at `0x8008AD50`. The table at `0x8032CC08`
contains dispatch `0x800A3240`, request candidate `0x800A3310` and response-extract
candidate `0x800A3890`. Construction during setup does not establish an actual
catalog request, its caller, or its selected attribute vocabulary.

The request slice contains the familiar list range, requested Attributes,
AttributeFilters/Name/Value and TitleId operations. It also contains this
**additional retail structure**, which the older source and offline parser lack:

| Native structure | Direct evidence | Remaining type/meaning gap |
| --- | --- | --- |
| repeated `AttributeFiltersEx` | Outer loop at `0x800A367C`, 20-byte entries; fields `FilterType`, `DataType`, `Name`, repeated `Value` | Allowed filter/data type strings, comparison semantics and API/caller prerequisites unproven |
| `OrderByAttribute` | Conditional block at `0x800A3730`; `OrderByType`, `DataType`, `Name` | Allowed order/data type values, defaults and sorting rules unproven |
| Caller-provided element name/value pairs | Loop at `0x800A378C`, eight-byte entries | Actual caller field names, constraints and whether any retail page uses them unproven |

The extended field values use the same candidate string-element helper
`0x8007D7A0` as ordinary Name/Value strings. This does not establish numeric
enum values, allowable vocabulary or a complete WSDL. In particular, do not
invent ASC/DESC, numeric types, category names or filtering behavior.
Unknown-field rejection in the offline codec is useful containment; expanding
it without matched caller/response evidence would not restore retail browsing.

## Attribute names: examples are not the storefront schema

Inventory-verified `ec_test.cpp:688-707` requests Version, TitleType, TitleName,
TitleDescription, TitleSize, FsSize and Category, and demonstrates Category
filters. This is explicitly a client-library test, not a recovered Japanese
Shop catalog call. TitleName, TitleDescription, TitleSize, FsSize and Category
do not occur as NUL-terminated strings even allowing compiler-shared suffixes
in the inspected original main. TitleType does occur as a suffix, which is
reported separately rather than incorrectly called absent.

`include/ecbase.h:264-285` models catalog attributes and simple filters as
name/value **character strings**; a catalog row separately carries a title ID,
ratings, license pricing and repeated attributes. This establishes the older
generic representation, not native display attribute names or their business
types. Field names from captured B04/B05 HTML or imported historical metadata
must not be relabeled into CAS attributes on this basis.

The older `getter_ECInterface` exposes getTitleInfo/getTitleInfos, downloadTitle
and a generic request callback, with no dedicated listTitles getter. Native
v21 contains the corresponding selected method-name markers; exact source
revision and complete getter behavior remain unverified. The old generic
request method delegates a string to an application callback and returns its
string result or null. The reviewed initializer sets that callback to null.
This is not evidence of a CAS request tunnel or of an application-supplied
callback in retail v21.

## GetTitle, owned titles and account/return boundaries

`ec_getTitle.cpp` implements the internal `ECGetTitle` **download/import worker**.
Its public entry is `EC_DownloadTitle`, reached by the older JavaScript
`downloadTitle(titleId)` with the required-content update option
(`ec_js.cpp:2138-2168`). The native main includes the worker's debug name
`EC_GetTitle(titleId)`. Neither that name nor a substring match establishes a
SOAP action named GetTitle. No such new service action is implemented here.

The recovered source establishes these separate contracts:

| Interface | Preconditions / result evidence | Restoration limit |
| --- | --- | --- |
| C `EC_ListTitles` (`ec_listTitles.cpp:260-305`) | Initialized operation environment, confirmed device key pair, connected state and nonempty account; positive asynchronous operation ID or negative error | No account-state fabrication; exact retail wrapper remains unverified |
| C `EC_DownloadTitle` (`ec_getTitle.cpp:679-711`) | Environment, connection, account and supported option checks; asynchronous ID/error result | Worker also requires an ES ticket view for ordinary download (`:172-184`) and later performs TMD/content/ES work; catalog presence is not ownership |
| Native JavaScript asynchronous bridge (`ec_js.cpp:1208-1220`) | A positive operation ID starts progress retrieval; failure constructs an error progress object | A returned object is not a completed operation or purchase confirmation |
| C `EC_GetTitleInfo(s)` (`ec_api.cpp:277-344`) | Synchronous owned-title enumeration through ES; single-title lookup can return NOT_OWNED; collection supports count query and overflow | Imported provider catalog rows must not become owned ES titles |
| SOAP common response (`ec_soap.cpp:294-349`) | Common error status checked before operation-specific data extraction | A zero error code for a response is not entitlement or permission to download |

These source gates have not been executed against actual identity or matched
comprehensively to the retail wrappers. The audit does not read ES state,
tickets or credentials, bypass checks, or turn transport success into ownership.

## Next source-proven component

The [offline ECS GetECConfig codec](ec_config.md) and isolated retail response
verification now implement this bounded next step, without a live route.
The request parser remains based on the older source subset; selected original
v21 response readers and URL setters are separately exercised on synthetic data.
Their observed behavior takes precedence where it differs from the older source.
The original function at `0x80088920` references this exact field family:

| Field | Native reference instruction |
| --- | --- |
| action `GetECConfig` | `0x800889D8` |
| request `ECVersion` | `0x80088BE0` |
| response `ContentPrefixURL` | `0x80088C0C` |
| response `UncachedContentPrefixURL` | `0x80088C44` |
| response `EcsURL` | `0x80088C7C` |
| response `IasURL` | `0x80088CB4` |
| response `CasURL` | `0x80088CEC` |

This corroborates `ec_connect.cpp:45-109`: service discovery reads all five URLs
and installs them into the environment. `EC_Connect` itself still requires an
initialized environment and confirmed key pair (`:227-247`); connection then
has EULA/account/device-status branches. Supplying five URLs does not establish
an authorized identity or connected account.

The native checks establish selected response lexical/error behavior and exact
URL storage, including quirks that prevent treating zero status as proof of a
valid response. They do not prove the retail request version, origin/transport
policy, complete connection or account state. No operational endpoint overrides,
registrations or live commerce routes were introduced. The actual storefront-to-CAS
call path, requested attribute/type vocabulary, account protocol and
entitlement/ticket/content contracts remain unfinished work.

## Reproduction

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m tools.audit_wii_shop_commerce_surface `
  --main '<private original v21 main content>' `
  --browser-container '<private original v21 browser U8 content>' `
  --source-root '<private inventory-backed shop-build-lead>'
.\.venv\Scripts\python.exe -m unittest tests.test_wii_shop_commerce_surface -v
```

Eight synthetic tests pass for byte bounds, original fingerprint rejection,
allowlisted/redacted output, section mapping, signed relative references,
compiler-shared strings, branch-link caller selection and bounded native reads.
No full captured queries, original bodies or derived instruction text are emitted
by the tool. No original executable, build, browser or captured script is run.
