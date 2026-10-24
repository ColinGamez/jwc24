# Historical title display data

October 25, 2026. The preview now uses accepted title facts from the private
[2019 storefront capture](frontend_capture.md), alongside the imported catalog.
This supplies original captured product names and publishers for **835 of 844
preview title IDs**, plus **774 historical point amounts**. It does not establish
current offers, ownership, entitlement, signed title identity or installation.

## Acceptance checks

The builder selects Japan-region detail requests matching the preview catalog.
Each source file must match the private capture manifest's size and SHA-256.
The internal `titleId` literal must agree with the requested ID. Display fields
are parsed without executing scripts; duplicate fields, decoding substitutions
and ambiguous identity are rejected. One captured URL has a different internal
ID and is excluded. Together with eight IDs lacking a matching capture, this
leaves **nine titles without accepted metadata**.

Historical point amounts are accepted only when the displayed number agrees
with the page's literal `titlePoints` value. An expression, missing amount or
disagreement produces an unknown value. **61 accepted pages** have no verified
point amount. Publishers and titles are preserved as captured, rather than
being translated by the template's general localization substitutions.

Some captured dates refer to an original game release, such as a 1980s arcade
release. They are retained as `captured_display_date`, not promoted to the Wii
release-date field. Player, platform and genre text is also retained for review;
it is not automatically relabeled into Japanese UI fields.

## Preview behavior

Accepted names, publishers and point amounts populate list/detail pages.
Captured titles are also searchable with the existing Unicode-normalized name
filter. Original source listing names and all version variants remain present;
no installation version is selected. Catalog `price` and `owned` remain unknown.
The accepted amounts live separately under `historical_metadata.points`.

The cache is bound to both the catalog digest and capture-manifest digest.
The server checks that pairing, and the launcher checks the running metadata
digest against the local file. Raw captured bodies and the derived title-data
file remain private; Git contains the builder, parser, tests and aggregate
[validation report](../../research/wii_shop_title_metadata_validation_20261025.json).

```powershell
python -m tools.build_wii_shop_title_metadata
```

The default output is a new `private/wii_shop/title-metadata-v2` directory.
Existing outputs are preserved. Build this after importing the storefront
capture and before starting the updated service.

Validation covers all 85 catalog pages, 844 detail pages, 835 captured-name
searches and three detail/search pairs over verified loopback HTTPS. There are
85 Shop tests plus two credential tests. Layout, Japanese typography, keyboard
input and complete interaction still need native Dolphin checks. Other page
templates, unknown fields and unsupported commerce functions remain unfinished.
