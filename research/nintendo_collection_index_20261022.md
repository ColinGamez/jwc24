# Nintendo collection index for JWC24

Indexed October 22, 2026, from the user's local Nintendo folder. This expands
the [19-PDF review](sdk_pdf_review_20261022.md) to the entire physical tree and
the collection's existing archive catalogs. Original contents were read only.

## Coverage

| Record type | Count | Meaning |
| --- | ---: | --- |
| Physical files | 242,945 | Files encountered on disk, including binaries, tools, dependencies and research outputs |
| Physical directories | 21,656 | Traversed directories |
| Reparse points | 2 | Recorded but not followed |
| Logical physical-file bytes | 46,311,348,006 | About 43.1 GiB; not deduplicated or allocated disk usage |
| Existing catalog files | 75 | Imported from the collection's `index/*.list.txt` |
| Catalog listing rows | 718,595 | Previously listed paths, including directories and repeated catalogs |
| Prior nested-archive member rows | 975,163 | Imported from one existing compressed member index |
| Selected text documents | 802 | Bounded Wii-related source/document text and Markdown; not all source code |
| Previously extracted PDF documents | 19 | The earlier 669-page Wii SDK review, added to text search |

The whole physical tree is indexed by path, type, size and modification time.
Selected document text is searchable separately. Two text documents were
limited to 256 KiB: a generated GX texture-data source and Ghidra's change log.
The physical tree includes 20 PDFs; the additional one is a Ghidra training
document, inventoried by metadata rather than added to the earlier PDF review.

**These counts must not be added together as unique files, packages or builds.**
Catalog rows are previous observations, not proof that their archive or payload
is currently present. This pass did not reopen/decompress every archive,
decrypt every binary, traverse version-control object stores or inspect every
file's contents. No recovered program, build script or installer was executed.

The new scan/import reported zero filesystem/import exceptions. That does not
erase errors in earlier scans: the existing SDK reference audit, for example,
records two July archive parsing failures. Reparse targets, opaque formats,
encrypted contents, stale catalogs and bounded text extraction remain limits.

## Private index and search

The local, ignored `private/nintendo_index/` directory contains:

- `inventory-20261022.sqlite`: metadata and selected-text search, about 685 MiB.
- `summary.json`: counters, per-root/per-extension totals, heuristic topics,
  exceptions and SQLite integrity result.
- `search.py`: read-only lookup that returns paths and provenance without
  printing original source or key material.
- `README.md`: schema, scope, limits and usage.

Example commands from the repository root:

```powershell
.venv/Scripts/python.exe private/nintendo_index/search.py --topic wc24 --kind file
.venv/Scripts/python.exe private/nintendo_index/search.py --path NHTTP --limit 50
.venv/Scripts/python.exe private/nintendo_index/search.py --text NWC24 --limit 20
```

Path search is literal and case-insensitive. Text search uses SQLite FTS5 over
only the selected documents. Topic tags are heuristic leads, not verified
channel identities. Exact original paths, source text, catalog rows and local
profiles remain private and are not part of the Git commit. The private search
database is a local artifact, not something supplied by a fresh clone.

## Leads relevant to JWC24

### Later Shop HTTP and WC24 integration material

The extracted Shop overlay trees contain later HTTP-related headers and
libraries, including NHTTP startup material and an SSL/socket wrapper. There
are also Shop WC24/channel-jump integration sources. These are more relevant
leads for particular client API usage than the networking-free initial SDK
described by the PDFs.

They do not establish a complete WC24 SDK, a VFF format specification, a
working Shop backend or the contracts used by every retail channel. Repeated
copies/revisions must be compared before treating hits as independent evidence.
Binary libraries are inventoried, not interpreted as complete protocols.

For example, the path search for `nwc24.h` returns two **RFL_NWC24.h** catalog
entries associated with the face library. It does not locate the full core
NWC24 header on disk. Filename suffix matches need this kind of qualification.

### Address-channel sample-save lead

The existing apps catalog contains an HCCJ sample-save tree in a pre-repair
test application, including a `nocopy/pd.dat` entry. The 18 matching rows
include directories and CVS metadata; they are not 18 recovered saves.

This is a possible lead for the address channel's saved-data framing. It is
not evidence of Demae restaurant menus, order APIs or a complete HCHJ client.
The payload was not extracted or read in this pass. Any follow-up should
check identity/provenance and avoid copying personal records into fixtures or
publishing them.

### Early channels and original visual references

The collection already contains extensive early-menu/channel research, resource
inventories, runtime notes and a nested-snapshot audit. These are now locatable
alongside the file records rather than hidden among unrelated platforms.

Those existing notes distinguish a substantial early menu and Mii/Photo
applications from reserved News/Forecast/Shop packages and static reference
images. A placeholder package, build recipe or screenshot is not the complete
service client. This indexing pass did not independently repeat the prior WAD
decryption, runtime tests or banner reconstruction work.

### Known missing dependencies and false-positive media matches

The selected text contains references to the missing Shop base archive
`wstrunk1316_repack.zip`, but no indexed path matches that filename. This is
consistent with the existing hunt reports; it is a scoped index result, not
proof that the bytes cannot exist inside any opaque or unidentified object.

The Wii no Ma topic also matches Mobiclip material from a different platform's
game-engine tree. A codec name alone does not establish compatibility with
the Wii no Ma MOC5 client. Likewise, generic NEWS files, arbitrary title-code
substrings and development-board networking are not channel implementations.

## Updated follow-up order

1. **Shared transport/client diagnostics:** review the specific later HTTP and
   channel-jump usage, compare with JWC24's independently recovered request
   behavior, and retain exact version/build provenance. Keep original code
   separate from public independent implementations.
2. **Demae address data:** verify the cataloged HCCJ sample-save identity and
   its relationship to the existing address parser. Do not confuse this lead
   with verified branch menus or progress on native dish selection.
3. **Channel-specific data recovery:** continue News task/container work,
   Nintendo Channel CSData recovery, CMOC startup/auth semantics and Body
   Check prerequisites using actual client evidence. A zero match in the
   selected text subset is not evidence that an entire archive lacks a feature.
4. **Media/artwork:** retain the earlier GX/TPL and codec-specific checks.
   Distinguish original resources, static references and generated previews.
5. **Avoid repeating completed broad hunts:** consult the indexed local
   reports and their caveats before reopening large archives or searching for
   already-missing Shop exports. New candidates need new evidence.

## Verification

SQLite `integrity_check` returned `ok`. Physical/catalog/member counts were
cross-checked against the completed summary. Read-only path and FTS lookups
were exercised with known positive records; absent-path and restricted-kind
queries were checked separately. No channel server, original Nintendo file,
emulator profile, save, order or mail queue was modified by indexing.
