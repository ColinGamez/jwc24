# Native Japanese Forecast measurement and condition consumers

October 28, 2026. This audit uses only the pinned, private original Japanese
HAFJ v7 application: 1,925,536 bytes, SHA-256
`ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5`.
It does not read live settings, profiles, a NAND backup or provider observations.
The [metadata report](../../research/forecast_units_validation_20261028.json)
contains source-region hashes and bounded execution results, without original
message text, graphics, executable bytes or complete formatted strings.

## Wind bytes, selected units and integer formatting

The original daily-display slice at `0x8001E1D0` reads direction from day `+0x16`.
Direction `0xFF` skips the wind section entirely, before either speed byte is
read. Otherwise the original settings word at `r13-0x6B4C` chooses day `+0x18`
when zero and day `+0x17` when nonzero. This is a native settings-controlled
selection; the setting is not inferred from a provider field or country.

For the explicitly supplied synthetic configuration **country 1, language 0,
unit selector 0 or 1**, the caller dispatches to Japanese formatter
`0x8001F110`. Selector 0 resolves unit pointer `0x8032FCB0` (`mph`); selector 1
resolves `0x80199928` (`km/h`) through table `0x801999B0`. The ordinary selected
speed byte is passed unchanged as an integer. The original formatter and its
original string/numeric helpers run to normal return, and their bounded output
contains the selected decimal integer and unit. No helper is replaced by a
stub. The wind field called `wind_speed_metric` in JWC24 therefore corresponds
to **km/h in this verified Japanese daily-display configuration**, rather than
establishing an m/s field or a universal rule for all locales and consumers.

The explicit fixture does not apply the owner's real settings. Original startup
code at `0x80004224..0x80004234` supplies the SDA bases used by this harness.
Static writes at `0x8000E0D4`, `0x8000E114`, `0x8000E128` and `0x80028768` show
that the selector is loaded/defaulted and can toggle; this audit does not run
that settings lifecycle or read its persisted values.

The native consumer already receives an integer. It establishes neither how
an original provider rounded fractional m/s into a stored km/h byte nor any
permitted approximation policy for a replacement provider. A later adapter
must name and test its own conversion/quantization policy, preserve raw source
units and missingness, and reject overflow rather than wrap into `0xFF`.

## Cardinal direction meaning and an observed boundary

The country-1/language-0 table at `0x801994D8` resolves original Japanese labels
whose meanings are:

| Native value | Meaning | Native value | Meaning |
| --- | --- | --- | --- |
| 0 | Calm / no wind | 9 | SSW |
| 1 | NNE | 10 | SW |
| 2 | NE | 11 | WSW |
| 3 | ENE | 12 | W |
| 4 | E | 13 | WNW |
| 5 | ESE | 14 | NW |
| 6 | SE | 15 | NNW |
| 7 | SSE | 16 | N |
| 8 | S | 255 | Skip wind display in this caller |

Each label's pointer and digest is pinned without publishing original labels.
The ordinary and missing-speed paths for all nonzero directions actually pass
the corresponding original table pointer to the original formatter. Value 0's
calm meaning comes from its original table label; its dedicated formatter branch
has no direction-label argument. These are native facts. Agreement with a
provider's enum must be established independently before assigning its values.

The native formatter has separate speed-`0xFF` paths. With direction 1 through
16 the complete original formatter returns normally for the tested fixtures.
With direction 0 and selected speed `0xFF`, the actual original caller passes
that exact pair into the formatter, which attempts a two-byte read at address
`0xFF`, instruction `0x8016F574`. Both unit-selector fixtures reproduce it.
The verifier records this **isolated invalid-read boundary**, rather than
claiming that every missing-value combination successfully formats. It does
not establish real-world reachability across every original state or full UI
behavior, and it adds no global builder combination rule or substitute screen.

## Temperature range and rounding limits

The original signed-integer formatter prefix `0x8001D558..0x8001D5BC` receives
a signed integer, uses the existing missing branch for `-128`, and preserves
all other signed-byte integers `-127..127` in its original bounded text output.
The original string/numeric helpers execute unchanged. Execution stops before
object-dependent drawing instructions. The separate static byte consumer at
`0x80007AB0..0x80007AC0` sign-extends a temperature byte and tests `-128`.

This proves integer/missing formatting, not floating measurement rounding,
Celsius/Fahrenheit conversion, field selection in every screen, or a complete
accepted weather dataset. Provider fractional temperatures need an explicit
replacement-policy decision; no original rounding algorithm is inferred here.

## Primary condition keys and secondary graphical selectors

The fields of `WEATHER_CONDITION` (`>HHI`) serve different purposes in the
observed consumers. Complete original getter `0x800203F0..0x8002044C` searches
for the query against the row's first unsigned halfword, then returns the
second unsigned halfword. An absent key returns `0xFFFF`. Guarded synthetic
lookup cases deliberately keep primary IDs and secondary values different;
they include primary 100, 300, `0x1001`, 32767 and 65534. No provider condition
meaning is assigned to those fixtures.

Original rendering call setup at `0x8001D774..0x8001D79C` reads row `+2` before
passing the selector to `0x80020574`. Its numerical dispatch slice
`0x800205B8..0x800208EC` separates bit 15 from the low 15 bits. A table covering
low selectors `0..126` contains 59 graphical definitions: `1..33` and `101..126`.
Selectors 0 and `34..100`, plus out-of-range values, choose the existing fallback
boundary. The high bit is preserved as a separate drawing argument; its full
visual meaning is not established here. No drawing suffix or graphics prefix
is executed by this numerical-dispatch test.

Consequently a real provider's weather identifier can structurally remain a
primary dictionary key independently of the graphical selector. This does not
prove a visual correspondence between JMA conditions and the native graphical
definitions, authorize copying provider numbers directly into the second
halfword, or remove `0xFFFF` missing-condition rules elsewhere in the channel.
Condition labels, native graphic meanings and any provider mapping still need
separate evidence. For example, secondary 100 selects the fallback even though
primary ID 100 can be found in a supplied dictionary.

## Reproducible bounds

```powershell
.venv/Scripts/python.exe -m unittest tests.test_forecast_units_native
.venv/Scripts/python.exe tools/verify_forecast_units.py PRIVATE_ORIGINAL_HAFJ_APP
```

The six-test module includes three public input/error tests and three optional
native tests. Native tests skip truthfully when the pinned private original or
Unicorn is unavailable. The CLI bounds its source read and emits metadata only.

Native coverage comprises 1,152 wind cases (1,142 complete formatter returns,
two recorded invalid reads and eight missing-direction suppressions), 60
complete primary/secondary lookup cases, 262 numerical icon-dispatch cases and
256 signed-temperature formatter-prefix cases. Code stays inside pinned
original text; reads/writes, inputs, settings, output, stack, source bytes,
canaries, instruction counts and per-run time are guarded. No service or helper
boundary is mocked. This is native instruction execution in an offline harness,
not embedded graphics/audio/UI, a provider adapter or a real-console test.
