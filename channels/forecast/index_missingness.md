# Original Forecast index missingness

This contract records selected HAFJ v7 validation and display consumers. It does
not supply UV, laundry or pollen observations, define their measurement scales,
or establish that a current provider can supply them. The implementation in
`jwc24/forecast_index_policy.py` projects their branch decisions from explicit
caller inputs; it does not construct a Forecast payload or modify an emulator.

The private original application is 1,925,536 bytes, SHA-256
`ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5`.
No original executable bytes, dictionary strings, images, NAND or credentials
are published with this proof. `research/forecast_missingness_validation_20261028.json`
records a reproducible run against that input.

## Validation, lookup and availability are separate

Day-relative bytes `+0x19`, `+0x1A` and `+0x1B` hold the UV, laundry and pollen
dictionary codes. The complete selected validation block is
`0x8000D328..0x8000D448`, exclusive of its exit. For each field, byte `FF`
bypasses membership validation. A non-FF UV byte must match the first byte of
some eight-byte raw UV dictionary entry. Laundry and pollen perform equivalent
membership checks only when the word at `r13-0x6A04` is zero; a nonzero word
skips those two checks. This proof retains that word numerically rather than
assigning it an independently unverified geographic meaning.

The raw header dictionary count/offset pairs are UV `+0x38/+0x3C`, laundry
`+0x40/+0x44` and pollen `+0x48/+0x4C`. A failed membership check sets the
incoming accumulator to `FFFFFFFF`. Successful or skipped checks preserve it,
including a prior failure. This is not full-validator acceptance. Codes are
dictionary keys; the block does not establish a numeric severity scale or
globally reject a non-FF byte merely because its numeric value is high.

Complete cooked lookups at `0x8002044C`, `0x80020488` and `0x800204C4` scan the
respective eight-byte cooked rows in order, compare the first byte through each
row's raw-entry pointer, and return the first matching cooked-row pointer or
zero. They do **not** special-case FF. Thus an explicit FF dictionary entry
remains matchable even though FF skipped raw membership validation. Duplicate
entries preserve first-match behavior, including a null text pointer on the
first row. The proof constructs raw and cooked tables explicitly; the original
table deserializer/constructor is outside this proof.

The complete availability callbacks at `0x80011D98` and `0x80011E64` read the
selected day's codes through the actual record handle. The former returns true
on the first non-null UV/laundry/pollen lookup; the latter tests UV only. An FF
entry can therefore make either callback true. Their registration lies beside
the original `life_no_service.brlyt` resource reference, but outer layout
selection and visible card hiding have not been executed here.

## Display branch decisions

The full combined renderer `0x80011EB0..0x800122D8` obtains all three lookup
pointers and processes display calls in laundry, UV, pollen order. Its metadata
helper `0x8001C89C` is called for a field only when the row exists, its raw code
is not FF, and its cooked second word is a non-null text pointer. This proves
call selection, not successful loading or presentation of that metadata.

For each value, a null lookup or FF code copies the original missing string
at `r13-0x781C` into the original scratch output location. An existing non-FF
row uses the original integer conversion helper; a null text pointer does not
prevent that numeric path. The original string-copy and integer helpers run
unchanged in the native verifier. The original string itself remains private.

The UV-only caller slice `0x80011A74..0x80011BC0` differs. A null UV lookup
skips its value path. An existing row calls the metadata helper even when the
row's code is FF or its text pointer is null, then chooses the original missing
string for FF and integer conversion otherwise. Because that helper is an
explicit intercepted graphics boundary, the proof does not establish that
these pointer combinations render safely. The parent function and surrounding
layout selection are not claimed complete.

The byte at `r13-0x6A0A` chooses the combined renderer when zero and the UV-only
branch when nonzero at this caller slice. Native fixtures execute the full
combined function directly and the UV-only branch with this byte set to one.
Synthetic day indices zero and one verify the actual record stride of 28 bytes
and code positions `record + day*28 + 0x29/0x2A/0x2B`.

## Wind boundary relevant to absent data

All 256 direction bytes were executed through `0x8000D310..0x8000D328`. The
validator admits `0..16` or `FF`, preserving the incoming accumulator; other
bytes set it to `FFFFFFFF`. In particular, zero is admitted. This establishes
validation range, not safety of every direction/speed pair.

The actual wind-render prefix at `0x8001E1D0` sends direction FF directly to
`0x8001E8FC` before reading either speed byte `+0x17/+0x18`. Both selector-word
cases zero and one execute this branch with read observations proving that no
speed byte was fetched. Speed units, speed-FF combinations and the complete
wind renderer belong to the separate unit/formatter proof. In particular,
direction zero plus speed FF must not be inferred safe from the validator's
admitted range.

## Reproduction and limits

Run `python tools/verify_forecast_missingness.py PRIVATE_ORIGINAL_APP` with the
optional Unicorn dependency installed. Identity refusal and eight public
policy tests run without original input or Unicorn. The private native test
skips explicitly when either is unavailable.

The verifier executes 10,426 comparisons: 256 direction blocks; 3,584 index
validation blocks; 3,840 complete dictionary lookups; 1,372 availability
callbacks; 686 full combined renderers; 686 UV-only caller slices; and two
direction-FF prefixes. Synthetic dictionaries include empty tables, duplicates,
every possible explicit code byte, and null/non-null text-pointer cases. The
display matrix also exercises numeric zero, seven and 254 without assigning
them provider meaning. Tests preserve an already-failed accumulator.

Instruction fetches stay inside unchanged initialized original text sections.
Reads stay inside pinned initialized sections or explicit synthetic fixture,
stack, SDA-word and output ranges. Native writes are limited to the stack,
synthetic UI object and bounded output. All initialized original sections and
the input file are checked unchanged. Each run has an instruction-count bound.
The graphics boundaries `0x800D56E8`, `0x800D3C7C`, `0x8001C89C`, `0x80031170`,
`0x800313F4`, `0x8003E150` and `0x8003F088` are intercepted; actual pixels and
resource loading are not tested. Original lookup and string/integer helper
instructions execute normally, including their original callees.

An adapter with no verified UV/laundry/pollen source can represent absent
membership with FF, but must also account for dictionary contents, the native
availability callbacks and the caller's display branch. This proof does not
authorize fabricated dictionaries or values, and it does not implement a JMA
conversion, signed/encrypted delivery, full client startup or native UI test.
