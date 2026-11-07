# JMA observation measurement conversion

`jwc24.jma_measurements.project_observation` converts measurements from one
explicitly selected, already parsed observation record. This is part of the
replacement adapter, not the original provider's rounding algorithm. It does
not choose a station, native location, latest record, acceptable source age,
condition icon, forecast, native clock or publication destination.

The result retains the exact typed source record, station metadata and source
receipt alongside the converted integers. Raw fractions, QC, dates and unknown
source fields remain available. Conversion does not authenticate supplied
receipts or make an October capture current in November.

## Explicit replacement policy

The caller must pass `rounding="nearest_half_away_from_zero"`. Policy identifier
`jwc24-jma-measurements-v1` fixes the following decisions:

- Only explicit QC 0 measurements are eligible. JMA's own client also accepts
  qualified QC 1; this local projection retains that qualifier and marks the
  native measurement unavailable. Absent, null and qualified values have
  separate reason codes. A real unqualified numeric zero stays zero.
- Celsius is rounded directly. Fahrenheit is computed from the unrounded
  Celsius value using `C * 9/5 + 32`, then independently rounded. Thus 0.3 C
  becomes native 0 C and 33 F; converting an already rounded zero would lose
  information. Exact rational arithmetic avoids binary tie behavior and
  dependence on a caller's decimal precision context.
- Wind speed in m/s becomes km/h using `18/5`, and mph using `3125/1397`
  (one international mile is 1609.344 m). Each is independently rounded.
  The original Japanese metric formatter consumes km/h, not m/s.
- The source's reviewed 0-calm/1-NNE/.../16-N direction enum matches the
  [original native labels](native_units_and_conditions.md). No north or calm
  reading is inferred from absent direction data.
- Wind speed and direction must both be eligible from the same selected
  observation. If either is unavailable, all three native wind fields become
  `FF`. In the verified original caller, `FF` direction skips both speed reads.
  This avoids emitting the isolated invalid-read pair calm `0` / speed `FF`.
  It does not claim that all full channel states/screens have been exercised.
- Rounded temperature values must fit `-127..127`; `-128` is reserved for
  missing temperature. Speeds must fit `0..254`; `255` is reserved. Overflow,
  negative wind, invalid units/periods and malformed typed measurements reject.
  Values never wrap, clamp or become a missing marker through overflow.

The rational input is the decimal spelling of the already parsed numeric
value. This does not add arbitrary-precision JSON number parsing; the capture's
exact raw bytes remain bound by its source receipt. The typed observation and
the conversion policy must both accompany later transformation provenance.

## Verification and remaining integration

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_measurements
```

Synthetic public tests cover independent physical-unit rounding, positive and
negative ties, every direction, zero, QC 1..7, absent/null distinctions, unsafe
calm/missing-speed suppression, range boundaries, source identity/date retention,
explicit record selection and malformed caller-constructed records. They make
no network requests and need no original software. A composition test packs
the converted measurements into the existing short-file builder with explicit
synthetic identity/clock and missing sky condition, then validates and inspects
its actual native fields. No active payload is written.

A separate private replay on November 7 projected all five observations from
the retained October 28 source sample. Source hashes were rechecked by the
parsers, and every original record, station, date and receipt remained intact.
That sample had complete eligible temperature/wind pairs. It is historical
pipeline evidence, not a new request, current weather or national coverage.

The existing [original-unit execution proof](native_units_and_conditions.md)
establishes the downstream integer consumers. This projection's rounding and
QC choices are explicitly JWC24 policy, not a newly discovered native algorithm.
Source station/area-to-native location mappings, daily/weekly temperature roles,
weather graphics/text, provider-specific freshness, original credit boundaries,
global coverage, signing/trust/delivery and full native UI remain separate gates.
