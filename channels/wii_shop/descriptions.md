# Original captured B06 descriptions

`jwc24/wii_shop_descriptions.py` and `tools/import_wii_shop_descriptions.py`
recover original, title-bound More Details content from the private historical
collector capture. The source is the existing
`https://archive.org/details/WiiShopChannelBackup` archive, with SHA-1
`e20c789c86bd602d7af3816d105c3f62ab504374` and SHA-256
`f7f349b8baf06f0f77ba6d413ed87e535378bc746084e24c7d5f59273acacda0`.
These identify a collector archive; they do not establish Nintendo provenance,
an exact installed-v21 match, complete Japanese localization or a working native
commerce backend. Original page bodies, descriptions, styles, script bytes and
screenshots remain under `private/`, outside Git.

The [metadata-only validation report](../../research/wii_shop_descriptions_validation_20261025.json)
records the real pack's coverage, exclusions, image formats/dimensions, active
content inventory, checksums and startup measurements. This component does not
modify existing artwork, HTTP routes, launchers, a Wii backup or credentials.

The parent runtime now integrates this reader as the local `/description/<id>`
flow. It enables 834 source-proven More Details buttons on captured detail views
and preserves the original description markup, scroll/focus behavior and Back
cancel sound. The [combined integration report](../../research/wii_shop_parallel_integration_validation_20261025.json)
records HTTP/context/screenshot checks; current native visual verification is
still outstanding. Account and manual initialization scripts are not enabled.

The validated private `descriptions-v2` pack has **835 eligible descriptions and
1,670 original screenshots** for the 844 catalog IDs. Eight IDs lack a matching
B05/B06 source pair; one B05 has a genuine internal-title-ID disagreement.
All 266 B05/B06 display-title wording differences are preserved. No screenshot
was missing or invalid among eligible pages. All 837 recovered B06 pages have
zero active elements inside `goodsfree`, zero inline/style-attribute CSS URLs
and the same captured Back/showBack/cancel-sound footer behavior.

## Selection and identity

The importer verifies the known archive checksum and streams its bounded listing.
Its first extraction selects only Japan-region B05/B06 pages for the existing
catalog's source-reported IDs. It validates each original B05's internal title ID,
nonempty title, literal `isFreeIntroEnabled="false"` and exact generated footer
branch: true targets `ext/B_30.jsp?titleId=<same-ID>`; false targets
`B_06.jsp?titleId=<same-ID>`. Empty or unsupported flags, absent pages and genuine
internal-ID conflicts remain excluded. A manual pack is not a B06 replacement.

For B06, the requested ID must agree with every CCS reference. The title and
commentary must be nonempty and decode without substitutions. The original
`goodsfree`, `text`, `goodsdetails`, `TitleName1stline`, optional second title line
and `Platform` structure is preserved. Title wording differences from B05 are
measured, never rewritten or treated as identity conflicts. In particular,
trademark marks and line wrapping are not normalized into invented labels.

The second extraction selects only the **exact same-title FFFD file IDs actually
referenced** by accepted B06 pages, with at most two screenshots per title. The
review found legitimate screenshot IDs beyond FFFD0002/0003, including FFFD0006,
FFFD0007 and FFFD001C. File IDs are never guessed from another title or image
role. Decoded image format, MIME, dimensions, byte length and SHA-256 are checked.
Missing or invalid screenshots exclude the page; there are no substitutes.
Unrelated CCS files, title binaries and expanded manual trees are not selected.

The optional `--source-pack` reuses only source pages from a completed private
description pack after checking archive/catalog/listing bindings, exact selected
membership, listing size/CRC and every raw source SHA-256. It writes a new pack
and records the reused manifest's checksum. It never trusts the earlier pack's
eligibility decisions, and it selects the new screenshot stage afresh. The
restricted v1 experiment is preserved privately; v2 fixes its overly narrow
screenshot-file-ID assumption.

## Preserved behavior and runtime boundary

`Descriptions(root, catalog_digest, title_ids, shared_paths=capture.shared)`
exposes eligible `.rows`, `.excluded`, `.page(title_id)` and `.asset(path)`.
`page` returns a copied original body tree, original inline CSS and the two
original stylesheet paths. `asset` serves only verified original CCS screenshot
bytes and `/assets/captured/description-scroll.js`. It does not map unknown
content links to another screen.

The source's scroll-only subset is sliced from private page bytes and pinned to
SHA-256 `e3c84935e0f4f13d0e6376a1bae14d54154f42fd402822547994838d23c429ae`
(304 bytes), reviewed from B06 page SHA-256
`f72fd8ed3b3cf41d686dc21c7d3f1834b4cedf96377f8c4759fefe9c3e335d22`.
It uses only the browser's document/event objects and its own scroll-step state.
The original body invokes `kdown('goodsfree');` on keypress and focuses
`goodsfree` on load. The rest of captured `initPage` is not exposed as executable
code: it includes session/account-related behavior outside this component.
The verified footer label is the capture's **Back**, targeting `showBack()` with
`snd.playSE(cSE_Cancel)`. Historical Japan-request product text and captured
English common labels remain distinct evidence; this does not establish the
original retail Japanese wording for every common control.

Original anchors, forms, scripts, embedded objects and event handlers inside
`goodsfree` are inventoried before generic tree parsing removes scripts.
Unreviewed embedded active content is excluded; plain HTTP(S) publisher anchors
remain original references for the integrator to preserve explicitly. Inline
CSS and style-attribute `url(...)` dependencies must resolve to captured common
resources or the same title's verified screenshots; external URLs, imports and
unsupported references are rejected. Shared CSS resources remain the caller's
verified capture dependencies.

Startup requires validation revision **2** and checks the builder-generated
private manifest, catalog/source bindings,
row counts, source fingerprints, image metadata, referenced resources and
recorded exclusions without eagerly rereading thousands of payloads. First use
rechecks raw B05/B06 hashes and the original identity/footer/layout/scroll proofs;
each requested screenshot is reread, rehashed and decoded before serving.
Caches hold at most eight parsed pages and sixteen verified images. The importer
performs exhaustive source/image validation when building the pack. Neither a
manifest row nor an accepted catalog ID establishes ownership or entitlement.
After recovery, a final-code sweep reverified every eligible page and screenshot
in 15.45 seconds before stamping revision 2. A fresh revision-enforced instance
loaded in 0.081 seconds; these are local measurements, not native Wii timings.

Local bounds are 1,000 titles, 4,000 files, 2 MiB per source page, 512 KiB per
image, 1,024 pixels per image dimension, 128 MiB per extraction selection and
192 MiB per completed pack. They are defensive tooling limits, not recovered
native protocol limits. Outputs must be new directories beneath `private/`.

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m tools.import_wii_shop_descriptions `
  private/wii_shop/frontend-backup-2019/oss-auth.shop.wii.com.7z `
  --listing private/wii_shop/frontend-backup-2019/archive-listing.private.txt `
  --output private/wii_shop/descriptions-new
.\.venv\Scripts\python.exe -m unittest tests.test_wii_shop_descriptions -v
```

Tests use synthetic pages and images only. They cover the complete two-stage
import/read path, exact screenshot selection including alternative file IDs,
title/route/source bindings, Unicode and byte preservation, source drift,
missing resources, invalid images, active/CSS dependency checks and bounded lazy
caches. Browser/HTTP integration and native Wii scrolling remain separate
verification work for the parent restoration flow.
