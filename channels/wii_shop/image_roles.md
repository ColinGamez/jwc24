# Historical catalog icons and detail images

October 25, 2026. The preview now uses separate images for the original catalog
and detail slots. The earlier cache requested `FFFD0001` for every slot. The
captured pages show why that was incorrect: catalog and detail references often
use different file IDs, and **769 matched titles have different image bytes**.

The private historical cache now contains **776 catalog icons** and **835 detail
images** for the 844-title snapshot. All 1,611 image routes preserve captured
bytes. No images are generated, resized or converted. Both roles include 15
original BMPs; the earlier importer rejected that format. Native Opera rendering
of these BMPs still needs a Dolphin check.

## Reference checks

The reference builder reviews all 90 Japan-region catalog captures, including
the 6 MB all-titles page. An icon is accepted only when one catalog panel pairs
one title-detail target with one image under that same title ID. Conflicting
references are excluded. These pages establish icon references for 776 preview
IDs; the large page adds no further matching IDs.

Detail images come from the `Photo` element of the 835 previously accepted
detail pages. The parser rechecks their metadata and internal ID before using
that reference. It does not assume `FFFD0001`; 222 accepted detail references
use another file ID. Missing or ambiguous references are not guessed.

Each role retains its referencing page's SHA-256, exact archive member, image
fingerprint and catalog binding. Extraction checks the pinned collector archive
and selected members' sizes/CRCs. The cache builder verifies the extracted bytes
and image format/dimensions. The runtime verifies the manifest, role-specific
mapping and cached bytes before serving separate list/detail routes.

The source remains the [2019 collector backup](frontend_capture.md), rather than
a signed Nintendo package. These checks establish agreement with its captured
pages and payloads; they do not verify Nintendo signatures or complete fidelity.
The prior modified-site cache remains private for comparison.

## Gaps and validation

There are **68 missing catalog icons** and **nine missing detail images**. Those
slots still use the existing transparent spacer and remain unfinished fidelity
work. Substituting a detail screenshot into a missing icon slot would obscure
the gap, so the two roles do not fall back to one another.

The [validation report](../../research/wii_shop_image_roles_validation_20261025.json)
records exact-byte checks over certificate-verified loopback HTTPS for all 1,611
routes, plus offline rendering of 85 catalog pages and 844 title pages. Native
visual verification and complete-original-storefront verification remain false.

## Reproduce privately

After the initial [capture](frontend_capture.md#reproduce-privately) and
[metadata](title_metadata.md) imports:

```powershell
python -m tools.import_wii_shop_frontend_capture '<private archive.7z>' --listing '<private listing.txt>' --japan-catalog-only --output private/wii_shop/frontend-japan-catalog-v2
python -m tools.build_wii_shop_image_requests
python -m tools.import_wii_shop_frontend_capture '<private archive.7z>' --listing '<private listing.txt>' --title-images-only --image-requests private/wii_shop/title-image-requests-v3.json --output private/wii_shop/frontend-title-images-v3
python -m tools.build_wii_shop_captured_title_artwork
```

Builders refuse existing outputs. The default server/launcher now require the
matching `private/wii_shop/title-artwork-v4` pack. Original pages, images and
private manifests remain outside Git.
