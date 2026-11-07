# Dated XML daily extrema to native temperature fields

`jwc24.jma_xml_projection` converts one explicitly selected VPFD51 temperature
slot into the native Celsius/Fahrenheit integer pair. It retains the exact
station, source value, receipt and provider announcement/transmission/target
dates. The whole supplied parsed source also remains attached, including its
status, information kind/version, office metadata and complete header/series
qualifiers. Numeric conversion does not accept a training/cancellation report
for publication; a later source-eligibility policy must inspect those fields.
It supplies no native city, native clock, complete forecast day, source
age acceptance, provider activation or published payload.

## Source roles and conversion policy

The caller selects the parsed series position, station ID, reference ID,
expected role and expected JST calendar date. Values remain bound to their
actual reference definitions; source order is never sorted into an assumed
low/high pair. The reviewed period subset is:

| Source role | Local start and duration | Native field eligibility |
| --- | --- | --- |
| Daytime maximum | 09:00, `PT9H` | Daily high |
| Morning minimum | 00:00, `PT9H` | Daily low |
| General maximum | 00:00, `PT24H` | Retained source value; no daily high/low substitution |

Wrong dates, unfamiliar periods, dangling/ambiguous references and incorrect
selection reject. In the actual 05:00/11:00 reports, today's general maximum
is **not** today's morning minimum. This component does not manufacture an
absent daily low or a complete native day from those values.

JMA describes prefectural maximum/minimum forecasts as Celsius quantities:
[forecast explanation](https://www.jma.go.jp/jma/kishou/know/kurashi/yoho.html),
[temperature terminology](https://www.jma.go.jp/jma/kishou/know/yougo_hp/kion.html).
The conversion accepts only the reviewed source unit `度`, matching role/type,
consistent `refID`/unit/type attributes and a finite original numeric token.
The current [official XML schema](https://xml.kishou.go.jp/tec_material.html)
declares `description` separately from `condition` on the temperature type.
The display description remains unchanged source metadata; it is not parsed
into a second numeric value. Unknown attributes, any condition qualifier,
unreviewed units/types or unavailable values produce native missing values
`-128/-128` with explicit reasons. An absent reference cannot be invented.

Policy `jwc24-jma-xml-daily-extrema-v1` requires the same explicit
`nearest_half_away_from_zero` choice as the existing measurement converter.
It converts the **original decimal token** with exact rational arithmetic,
rounds Celsius and Fahrenheit independently, and rejects native range overflow.
It never rounds Celsius before computing Fahrenheit, clamps a value, wraps a
byte, substitutes zero or invents a reading.

## Actual verification and limits

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_xml_projection
```

Ten focused tests passed with both private morning captures available.
Each genuine report has 12 converted extrema and four separately retained
general-maximum slots. The tests preserve exact source objects/dates/receipts,
cover decimal ties, Fahrenheit conversion, raw/parsed disagreement, missing and
qualified readings, period/reference drift and explicit selection. The
optional captured-source test skips when the private documents are absent.
No test makes network requests or writes a native payload.

The schema ZIP linked by the official technical page was fetched once under
a separate 128-KiB/30-second research bound; its raw bytes and receipt remain
private. This is schema evidence, not a new weather capture or independent
authentication. The accepted source-record parser and its separate document
receipt remain documented in [jma_xml_temperatures.md](jma_xml_temperatures.md).

Native city/source identity, current-source acceptance, full forecast assembly,
weather/precipitation/index availability, missing-value rendering, attribution
placement, signatures and native UI/hardware validation remain separate gates.
