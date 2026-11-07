# JMA daily condition projection

`jwc24.jma_conditions` now implements an explicit replacement policy for five
reviewed JMA condition meanings. It combines actual official source labels with
the inspected original Japanese channel pictures. This is JWC24's replacement
mapping, rather than a recovered Nintendo or Weathernews provider dictionary.
It creates an individual dictionary row and dated projection; it publishes no
Forecast data and changes no channel assets, configuration or profile.

| JMA primary code | Official source label | Native secondary selector | Original picture |
| --- | --- | --- | --- |
| 100 | 晴 | 1 | Sun |
| 200 | 曇 | 10 | Cloud |
| 300 | 雨 | 19 | Umbrella |
| 400 | 雪 | 26 | Snowman |
| 101 | 晴時々曇 | 2 | Sun with intermittent cloud |

Code 101 is grounded in the retained original manual's actual forecast-screen
image and caption, not inferred by applying the meanings of the four individual
pictures to every composite. The separate [condition semantics proof](condition_semantics.md)
records that evidence, actual original component math and its limits. Policy
`jwc24-jma-daily-conditions-v2` replaces the initial four-category v1 policy.

The official JMA client captured on October 28, 2026 contains 118 `TELOPS`
entries. The parser accepts only that reviewed snapshot, pinned by its
199,327-byte length and SHA-256
`2219c9b3f581d0e69857eeb4c98e1ebb8059269b73d7886f9ecc9a676b124a50`.
An exact official HTML route, HTTP 200, body digest/size and retrieval interval
must agree with its `SourceReceipt`. The parser reads the bounded data literal
with JSON decoding and duplicate/Unicode/shape guards. It executes no downloaded
JavaScript. A changed future client requires review, rather than automatic
acceptance based on a familiar variable name.

The parser retains every source catalog entry in memory. The full table and
captured client remain outside Git. Only the five needed source labels and
mapping choices appear here. Reuse requires JMA source credit and a processing
notice: [official forecast client](https://www.jma.go.jp/bosai/forecast/),
[JMA terms](https://www.jma.go.jp/jma/kishou/info/coment.html), and the project's
[source attribution](ATTRIBUTION.md). A consistent receipt is not independent
authentication of a caller-constructed object.

## Explicit selection and missing behavior

`project_daily_condition` requires an explicit report index, series index,
published area and target index, plus the parsed catalog. It preserves the
original publishing/target dates, UTC instants, area identity, raw condition
token, detailed `weathers` description when present and both receipts. An absent
description field, an empty description and null are distinct. The primary
dictionary key remains the JMA code; the secondary value selects the separately
verified original picture. The Japanese dictionary label comes directly from
that source catalog entry.

“Pure” here describes the four reviewed catalog categories. It does not assert
that an area's detailed forecast sentence has no qualifications: the actual
captured code 100 is paired with a sentence including night-time cloud. The
canonical catalog label and complete detailed sentence remain separate fields.
The component must not be used to claim those detailed qualifications are absent.

All other 113 known catalog codes raise `JMAUnsupportedCondition`, an unknown
code raises `JMAUnknownCondition`, and an empty/null condition raises
`JMAConditionUnavailable`. Nothing silently becomes `0xFFFF`, a generic icon or
the first available category. No bit-15/night decision is supplied. The catalog
has no pure thunder entry: its thunder conditions also describe rain, snow or
other qualifications. A lone lightning picture would lose those meanings.

The retained old lookup XML is third-party WiiLink material. It is useful as a
comparison lead, but cannot establish the original provider's dictionary.
The original manual supplies the bounded category evidence for selector 2.
The arrow's temporal meaning and the other composites' qualifications remain
unproved by their appearance. Unsupported composites remain unfinished.

## Native text consumption evidence

`tools/verify_forecast_condition_text.py` uses the pinned original HAFJ v7
application. It executes complete original primary lookup `0x800203b4`, then
caller fragment `0x8001d7e4..0x8001d7f8`: the wrapper's text pointer at `+4` is
passed unchanged to fitting function `0x8001c89c`. Five actual JMA label/code/
selector tuples and ten synthetic boundary strings are checked.

The complete original UTF-16 length helper `0x8016f56c` executes from both
original width (`0x800d5700..0x800d5724`) and height
(`0x800d59ac..0x800d59d0`) prefixes: 30 cases. Empty text, LF, tab, a surrogate
pair and lengths through 1,024 UTF-16 code units remain unchanged. The limit is
a test fixture bound, not an invented native character limit. A separate
38-case original integer prefix distinguishes LF, tab and ordinary/control
code units at `0x800d03e4`.

Static inspection connects the fitting function's width/height measurements to
line-bound calculation `0x800d69f0`; it compares available dimensions, scales
text and issues two drawing calls for its existing shadow/foreground rendering.
The SDK line handler's LF branch advances using line height and resets the
horizontal position. These broader functions were inspected, **not fully
executed** by the new verifier. Actual font resources, complete width/height
metrics, fitting calculations, glyph traversal, multiline drawing and screen
legibility remain unverified. Passing a long string through its original
length prefix proves no final text-layout quality or safe universal maximum.

## Verification and remaining integration

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_conditions tests.test_forecast_condition_text
```

The 14 focused tests include public malformed-literal/receipt/selection tests,
optional pinned-source replay across all 118 catalog codes and actual native
consumer comparisons. The historical dated forecast contains 33 code slots:
13 project under this five-category policy, while 20 explicitly report
unsupported mappings. These are October source records, not present-day weather.
Missing private inputs/dependencies produce explicit skips in their respective
optional tests. No test makes network requests.

Remaining work includes composite/qualified conditions, legitimate native
location associations, per-source age acceptance, inline provider attribution,
current sky observations, complete payload generation/validation and coordinated
native UI checks. The [resource audit](condition_resources.md) establishes
picture evidence; it does not remove these gates.
