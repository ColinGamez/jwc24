# Original condition resource evidence

The retained Japanese HAFJ v7 resource now has a bounded, repeatable metadata
audit. This establishes which original textures the native graphical selectors
reference. It does not assign JMA weather codes to those selectors or activate a
replacement Forecast feed.

`tools/verify_forecast_resources.py` accepts the immutable original application,
retained TMD and content file. It checks their pinned identities before optional
native execution. Content index 9 / ID `0x10` matches the retained TMD's size and
SHA-1. The uniquely named U8 member `TPLWeather.tpl.LZ` decompresses to the pinned
TPL with 27 textures. Every texture header and padded pixel region is checked
for bounds and overlap. Reports contain hashes and numerical metadata, never
original raster data, text, coordinates, colour records or software bytes.

The executable SHA-256 is
`ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5`;
the resource content SHA-256 is
`039a0139a13723c1cc7348f7925b0c22860967565c8d9a480b2d1ecb6f7da0ee`.
These fingerprints and TMD membership establish consistency with the retained
inputs. They do not independently verify a Nintendo signature or acquisition
provenance.

## Actual private texture inspection

On November 7, 2026, all 27 textures were decoded to private images and their
contact sheet was inspected visually. Selected observations are:

| Texture | Observed original picture |
| --- | --- |
| 0 | Rounded cloud symbol |
| 1 | Crescent moon |
| 2 | Umbrella |
| 3 | Snowman |
| 4 | Sun symbol |
| 5 | Dark cloud with lightning |
| 6, 7, 8 | Different cloud pictures |
| 9 | Soft horizontal cloud or haze-like layers; exact weather meaning unassigned |
| 10 | Separate round falling particles; precise precipitation category unassigned |
| 11 | Full moon |
| 12 | Slanting rain strokes |
| 13, 14 | Different snowflake/particle pictures |
| 15 | Radiant sun |
| 16 | Lightning |
| 17 | White ribbon-like curve; exact weather meaning unassigned |
| 18 | Arrow-like transition mark |
| 22–25 | Original provider-credit graphics |

Visual observations establish depicted objects, rather than the original
provider's weather taxonomy. In particular, particle, haze and cloud variants
must not receive stronger meteorological labels merely because they look
familiar. No private image is added to Git.

## Executed native selection and substitution

The verifier executes the unchanged selector at `0x800205b8` for all 127
low-bit values. It reaches 59 definitions: selectors 1–33 and 101–126. It reads
their bounded, terminated 24-byte component records from the pinned original;
only texture indices, definition addresses and hashes enter the public report.
The complete selector-to-texture membership is in
`research/forecast_resources_validation_20261107.json`.

Some single-component cases have especially direct evidence:

| Secondary graphical selector | Original texture | Observed picture |
| --- | --- | --- |
| 1 | 4 | Sun |
| 10 | 0 | Cloud |
| 19 | 2 | Umbrella |
| 26 | 3 | Snowman |
| 33 | 5 | Dark cloud with lightning |
| 101 | 15 | Radiant sun |

The high bit is passed separately by the original dispatcher, as established
in [the units and condition audit](native_units_and_conditions.md). Both
original composition functions have integer substitution blocks: a nonzero
flag changes texture 4 to 1 and texture 15 to 11, preserving every other
texture. The new verifier executes each block across all 27 texture indices
and flags 0, 1 and `0x8000`: 162 cases. It executes the original preceding
comparison before the dependent branch and checks source bytes and guards
afterward. No branch instructions are replaced or simulated.

This connects the high-bit alternative to crescent/full-moon graphics. The
clock, sunrise/sunset or provider policy which should choose that flag remains
unverified. The floating-point placement/colour calculations, complete
composition loops, resource-loader lifecycle, GX calls and final native UI are
not executed by this check. An unordered description such as “sun and cloud”
cannot establish “occasionally,” “later,” timing, severity or provider-code
equivalence for a composite.

Seven focused tests pass, including synthetic malformed table, name,
duplicate-member, overlap, palette, format, dimension and padded-pixel checks,
plus optional comparisons against the immutable private originals. Missing
private inputs or optional native dependencies produce explicit skips in the
corresponding original tests.
