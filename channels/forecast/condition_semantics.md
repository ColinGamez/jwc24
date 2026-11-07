# Original composite-condition evidence

JMA code 101 can now use native secondary selector 2 under the explicit JWC24
replacement policy. Unlike a visual guess from two independent pictures, this
mapping has a retained original manual screen which pairs the sun/cloud picture
with a caption meaning sunny with intermittent cloud. The captured official
JMA catalog's canonical category `晴時々曇` has that meaning. The complete detailed
forecast sentence remains separate and unchanged in the projection.

This establishes one additional category. It does not recover the original
provider dictionary or establish all native composite, temporal or night rules.

## Original manual evidence

The immutable Japanese HAFJ v7 manual is content index 10 / ID `0x0a`, 276,617
bytes, SHA-256
`6ba845fc812a4106632b2843ae2439e2a14057d8a02cb8782a6514a0ba453b79`.
The size and SHA-1 match the retained TMD entry. Its U8 member `html-jp.arc`
contains the original `page03gazo.png`, 15,220 bytes, SHA-256
`1e1fb971235d7b001762cb64ae7ae9514041aae298ba8532c290a740e49c4db6`.

That actual private image was opened and visually inspected on November 7,
2026. It shows the native Japanese forecast screen with the sun in the upper
left, cloud in the lower right and the intermittent-cloud caption. The image
is an original retained manual illustration, not a new JWC24 screen or a
rendering produced by the new verifier. Its pixels and original caption are
kept outside Git.

`tools/verify_forecast_condition_semantics.py` pins the executable, TMD and
manual before checking both archive membership layers and the exact image
fingerprint. Hash membership proves consistency with the retained inputs; it
does not independently verify Nintendo signatures or acquisition provenance.
The visual reading is explicitly a human inspection finding, separate from
the executable metadata checks.

## Actual original component calculations

The original selector chooses definition 2 with textures 4 then 0 (sun/cloud).
Definition 6 includes an additional arrow texture; definition 11 reverses the
cloud/sun order. Those differences prevent treating every sun/cloud combination
as the manual's category.

The new proof executes original floating-point component calculations from
`0x80020b68` to the drawing-call boundary `0x80020ccc`. It uses the immutable
definition records for selectors 2, 6 and 11, three explicit scale fixtures,
two anchor fixtures and both high-bit states: **84 component cases**. Results
are checked against the private original records. Selector 2 preserves the
sun/cloud relative placement and the original component draw scale. Public
reports expose relationships and texture indices, without original coordinates
or colour records.

The harness enables the PowerPC FP facility in a synthetic CPU and explicitly
sets up the scale, alpha and conversion registers needed at the selected slice
entry. It changes no original instruction. The paired-single save/restore
prolog, complete composition loop, resource lifecycle, GX call and final image
are outside this execution scope. The private manual remains the actual visual
and caption evidence; calculated positions are corroboration.

## High-bit and time boundaries

A machine scan of all pinned executable text identifies **15 immediate direct
calls** to icon renderer `0x80020574`. Selected suffixes at all 15 call sites
execute with ten numerical secondary values: **150 handoffs**. Each preserves
the secondary value, including bit 15, from a supplied runtime dictionary row
or the preceding getter-result boundary. Code/static data, inputs and guards
remain unchanged.

These suffixes do not synthesize a night flag from a clock. This is a bounded
handoff finding, not proof that the entire application has no earlier time
logic. Getter calls preceding the two getter-result suffixes, indirect calls,
whole caller loops, data acquisition and other state are outside that check.
The `0xffff` suffix fixture also does not prove the earlier missing-condition
gate would allow drawing it in a real flow.

The earlier resource proof established crescent/full-moon alternatives when
the separate high-bit flag is nonzero. It did not establish when a backend
should choose them. Neither the manual pages inspected here nor the selected
consumer slices establish the arrow's temporal qualification, sunrise/sunset
policy or provider-to-night-code contract. Those mappings remain unsupported.

## Replacement mapping and verification

Only code 101 is added to the previous four supported JMA categories. Its exact
official canonical label comes from the receipted captured client. No original
provider labels or dictionary records are copied into the implementation.
The full source description, source issue/target dates, published area and
receipts remain unchanged. No generic icon or `0xffff` fallback covers the
remaining **113** unsupported source codes.

The actual historical forecast replay contains 33 weather-code slots; the
revised policy projects **13**, while **20** explicitly remain unsupported.
This is an October 28 source replay, not current weather. It activates no
provider, publishes no payload and touches no emulator profile or device.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_forecast_condition_semantics tests.test_jma_conditions tests.test_forecast_condition_text
```

Nineteen tests pass with the private originals available. Public tests exercise
malformed/ambiguous archive membership, identity rejection, redacted failures
and exact source projection. Optional tests verify retained manual membership,
actual native calculations and source-catalog/forecast replay. Missing private
inputs or optional native execution dependencies produce explicit skips.
