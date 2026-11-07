# Real VPFD51 daily-temperature source records

`jwc24.jma_xml_temperatures` parses the daily-temperature portion of JMA's
official VPFD51 XML bulletins into dated source records. It provides actual
05:00 and 11:00 announcement evidence without pretending that XML establishes
the layout of the separate website JSON arrays. It changes no JSON parser,
capture allowlist, native city, active provider, task, profile or native payload.

## Official source and bounded audit

JMA's developer portal advertises public XML delivery. Its VPFD51 specification
describes prefectural forecasts announced at 05:00, 11:00 and 17:00, with
amendments as necessary. These are source publication schedules, not receipt
times or permission to retime old data. [JMA developer portal](https://www.data.jma.go.jp/developer/),
[VPFD51 specification 11301](https://www.data.jma.go.jp/suishin/shiyou/pdf/no11301)

The November 7, 2026 audit made one request for the advertised regular long
feed, followed by two exact Tokyo VPFD51 document URLs advertised in complete
entries within its retained prefix. There were no retries, redirects,
authentication or broad office crawl. Each request used the existing private
audit transport's 2 MiB body bound and 30-second acceptance deadline.

The feed declared **4,592,730 bytes**. Acquisition correctly stopped at the
2 MiB-plus-one overflow sentinel and marked it **failed, incomplete and
unaccepted**. Its 4,285 complete retained Atom entries supplied discovery leads
only; neither the feed nor its partial prefix became accepted source data.
No retry or limit increase obtained the rest. The two document requests then
independently completed with HTTP 200 and their own byte digests/retrieval
bounds: 52,941 bytes for the 05:00 bulletin and 53,848 bytes for 11:00.
Raw bodies, headers and retrieval evidence remain private.

The new `XMLDocumentReceipt` accepts only exact HTTPS URLs under
`www.data.jma.go.jp/developer/xml/data/` with a dated VPFD51 filename and
six-digit office code. It rejects queries, fragments, credentials, explicit
ports, another origin/bulletin family, invalid filename dates, non-200 status,
reversed retrieval bounds, and changed bytes/lengths. This separate contract
rejects raw ASCII whitespace/control characters and DEL before URL parsing,
including characters that `urlsplit` would otherwise remove. It
does **not** broaden `jma_weather.source_path`. A matching digest establishes
consistency with supplied evidence; it does not independently authenticate a
caller-supplied receipt.

## Times, source order and reference identities

Each parsed report retains three separate provider fields:

| Provider field | Meaning retained by this parser |
| --- | --- |
| `Head/ReportDateTime` | Report announcement time, with its original token and UTC instant |
| `Control/DateTime` | Separate control/transmission time, with its original token and UTC instant |
| `Head/TargetDateTime` | Separate report target/reference time, with its original token and UTC instant |

Filename, HTTP dates and retrieval time replace none of them. The local
acceptance policy rejects report/control times after retrieval. Future forecast
targets remain allowed. Parsing a retained report does not establish source-age
acceptance or current weather.

The actual captured reports have `ReportDateTime` **2026-11-07 05:00 / 11:00
JST**. Both contain this daily-temperature definition order:

| Source `timeId` | Target JST | Duration | Published temperature role |
| --- | --- | --- | --- |
| 1 | November 7, 09:00 | `PT9H` | Daytime maximum |
| 2 | November 7, 00:00 | `PT24H` | General maximum temperature |
| 3 | November 8, 00:00 | `PT9H` | Morning minimum |
| 4 | November 8, 09:00 | `PT9H` | Daytime maximum |

This is genuinely **nonmonotonic source order**. The parser binds every
temperature through its `refID` to the matching `timeId`; it never sorts or
deduces the binding from array positions. It preserves target tokens, UTC
instants, derived JST calendar dates, duration/name metadata and all four
temperature properties. The general maximum at definition 2 is not mislabeled
as a morning minimum or discarded because another consumer does not use it.

Both actual documents contain all four temperature points `44132`, `44172`,
`44263` and `44301`, with 16 daily-temperature values per report. Point names
and IDs remain provider identities. No native Forecast city is assigned.
The separate three-hour temperature series is not substituted for the
daily min/max series.

The actual 05:00 bulletin's control time is **04:34:44 JST**, earlier than
its 05:00 report announcement. This is early transmission of a 05:00 report;
it is **not** an actual before-05 `ReportDateTime` sample and does not prove
the JSON selector's before-05-to-`17` behavior. The 11:00 bulletin's control
time is 10:38:43 JST. All original times remain distinct.

## Values and safe parsing

Temperature values retain their original tokens, raw type, raw unit and all
attributes, including unknown qualifiers. Numeric tokens receive a separate
numeric value; null, empty or unfamiliar tokens remain nonnumeric without
becoming zero. An absent temperature element remains an empty property.
Unknown type/unit metadata remains unchanged; the reported `度` unit is retained
and this module performs no unit conversion or native normalization.
Known role annotations require agreement between the property and temperature
type. A numeric token or role annotation is **not** a native-eligibility decision:
unmapped units and condition attributes still require separate review before
conversion or use. Full property/header metadata remains available alongside
the receipt.

UTF-8 is decoded strictly before XML parsing. A UTF-8 BOM is supported;
UTF-16/32, NULs and another declared encoding reject. DTD/entity declarations
reject before parsing. The parser applies streaming depth/node/attribute
limits, final text bounds, exact reviewed namespaces, unique time IDs and
station identities, and complete `refID` bindings. It makes no external
entity/resource requests. This is a bounded source projection, not complete
VPFD51 schema validation or an implementation of every bulletin field.

## Verification and remaining gates

Synthetic tests cover URL/receipt limits, separate clocks, nonmonotonic order,
reference binding, general/daytime/morning role distinctions, real numeric zero,
unknown/missing values, duplicate identities and malformed/unsafe XML. The
optional private test rechecks both successful capture receipts and actual
05/11 report/target definitions and points. Absence is an explicit skip;
tests make no network requests.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_xml_temperatures
```

The actual website JSON 05/11 shapes remain uncaptured. No change to its
increasing/unique target-time guard is justified solely by the XML evidence.
Native identity, source-age/dependency acceptance for this XML input, unit
normalization, attribution, missing-value rendering and full native publication
remain separate work. JMA source credit and processing notices must remain
visible at the eventual genuinely supported native data/credit boundary.
[JMA terms](https://www.jma.go.jp/jma/kishou/info/coment.html)

Measured evidence and remaining requirements are recorded in
[`jma_xml_temperature_validation_20261107.json`](../../research/jma_xml_temperature_validation_20261107.json).
