# Dated JMA source input

JWC24 can now acquire and parse one explicitly selected Japan Meteorological
Agency forecast office and one observation station into dated source records.
This is an opt-in input utility. It does not change the active Forecast provider,
create native payloads, choose native locations, sign files, update tasks, or
touch a Dolphin/Wii profile. The previous private Weathernews experiment remains
unchanged.

## Source and reuse evidence

JMA's current terms apply Public Data License 1.0 unless another rights notice
applies. Reuse requires source credit and the relevant URL; processing also
requires a separate processing notice without implying that JMA created the
modified product. Agency logos are excluded. The source-record export includes
credit URLs and identifies JWC24's parsing. This does not resolve attribution
inside the original channel's existing credit boundary. [JMA terms](https://www.jma.go.jp/jma/kishou/info/coment.html)

Preserve the actual published forecast areas and values. A station measurement
does not become a measurement at a different city by selecting a nearby station.
JMA's reuse guidance distinguishes republishing forecasts from independently
creating forecasts, including changing target areas. This implementation performs
no interpolation or city downscaling. [JMA reuse guidance](https://www.data.jma.go.jp/developer/ryuui.pdf)

## Reviewed public source contract

The original public JMA website client—not an independently versioned API
specification—establishes these routes. Their availability and format may change.

| Input | Exact official route below `https://www.jma.go.jp` |
| --- | --- |
| Office forecast | `/bosai/forecast/data/forecast/{six_digit_office}.json` |
| National latest observation time | `/bosai/amedas/data/latest_time.txt` |
| Station identities and coordinates | `/bosai/amedas/const/amedastable.json` |
| Selected station window | `/bosai/amedas/data/point/{five_digit_station}/{YYYYMMDD}_{HH}.json` |

The forecast client displays each report's `reportDatetime` as its announcement
time. `timeSeries[].timeDefines` are separate target times. The parser retains
each report's date, publishing office, area identity and exact value tokens.
Empty tokens remain missing. Short-range `temps` remain a provider sequence
until their specific min/max roles are verified. Forecast wind text is not
numeric wind; JMA weather codes are not native Weathernews codes. Climatological
averages remain separate metadata. [Official forecast client](https://www.jma.go.jp/bosai/forecast/)

The AMeDAS client derives station filenames from the national latest time using
JST and eight three-hour windows per day. Observation keys contain the complete
JST date and time. Measurement pairs carry the raw value and QC separately.
Its normal-data predicate accepts non-null values with QC 0 or 1; QC 1 retains
`)`, QC 4 retains `]`, and other presentation qualifiers are preserved. This
parser conservatively requires an explicit integer QC in 0–7. It never treats
an unavailable numeric zero as a good measurement. The consumer's direction
table uses 0 for calm, 1 for NNE, 4 for E, 8 for S, 12 for W and 16 for N.
[Official AMeDAS client](https://www.jma.go.jp/bosai/amedas/)

Temperature is Celsius, wind speed m/s, rainfall mm, snow depth cm and humidity
percent. The client distinguishes ten-minute sunshine in minutes from hourly
sunshine in hours. Values, units and available period lengths remain typed in
the export; no conversion or rounding occurs. Not every station measures every
element. [JMA observation explanation](https://www.jma.go.jp/jma/en/Activities/amedas/amedas.html)

## Implementation and use

`jwc24.jma_weather` provides frozen typed forecast/station/observation records,
raw tokens, qualifiers, explicit missingness and source receipts binding exact
bytes, URL and retrieval bounds. HTTP Date, Last-Modified and retrieval time
are never substituted for provider issue/observation time. Future forecast
targets are accepted; issue/observation times after retrieval reject under an
explicit local consistency policy. Older dated records parse unchanged;
parsing is not a claim of current weather or a source-age acceptance policy.
Unknown observation units stay unknown. No single common report date is invented.

The capture utility makes at most four sequential requests, without retries,
redirects, cookies, authentication or environment proxies. Each has a 2 MiB
body bound and a 30-second elapsed acceptance deadline with remaining socket
timeouts. OS DNS resolution can return late; an overlong interval still rejects.
Responses, headers, digests and retrieval bounds are written only into a new
directory. Existing directories reject. The record export is written exclusively
to a pending file, flushed and closed, then atomically renamed; a failed write
removes its pending file. Partial/failed bundles retain raw evidence and a failure
manifest without an accepted record export. A digest binds stored bytes; it does not authenticate a hand-edited
receipt or a caller-supplied transport. The manifest distinguishes that transport
from the default official GET path. Tests never access the network.

```powershell
.venv/Scripts/python.exe tools/capture_jma_weather.py `
  --office EXPLICIT_JMA_OFFICE --station EXPLICIT_JMA_STATION `
  --output private/forecast/NEW_CAPTURE_DIRECTORY
.venv/Scripts/python.exe -m unittest tests.test_jma_weather tests.test_jma_capture
```

`source-records.json` is a provider-source boundary, **not** the existing native
`current`/`long`/`compact` schema or a fabricated source-freshness receipt.
Office area forecasts and station observations are separate identities. Choosing
both does not establish that the station represents all forecast areas.

## Actual verification and remaining gates

Nine bounded representative responses were captured privately on 2026-10-28:
the two clients, forecast data, latest time, station table, area metadata,
observation explanation, forecast area metadata and one station window. The
optional private test verifies all nine hashes/bounds and parses the four data
resources without a new request. Absence is an explicit skip. Synthetic public
tests exercise source origin, dates, target/issue distinction, shape, QC,
missingness, identity, acquisition limits and exclusive output.

A separate default CLI run then made four real official GETs for the same
explicit representative office/station. All returned HTTP 200 within bounds,
producing a complete private bundle and source-record export: two reports,
five series, eighteen area-series and seven observation records. Stored raw
digests and intervals were independently rechecked. This verifies the real
transport path as well as the offline replay; it is not evidence of national
coverage or automatic provider activation.

The captured source has actual forecast issue dates and full observation dates.
Its selected station lacks a current sky condition; no inference fills it.
UV/laundry/pollen are absent and remain unavailable. JMA's Japanese areas and
stations do not cover the native globe. Current source age must be evaluated
again before publication. An existing-capture replay is historical evidence,
not a new live refresh.

Native mapping still requires explicit area/station provenance, weather-code
mapping, verified temperature roles and missing-field/rendering behavior. Native
Japanese wind formatting selects a km/h byte, whereas these source records
retain m/s; conversion and quantization need their own explicit policy. Calm
with a missing speed must not be emitted as a guessed zero or north. Attribution
must fit a genuinely existing data/credit boundary; existing provider credits
must not falsely attribute another provider's data. None of these gates is
relaxed by a successful parse. See the [native evidence](native_clock_and_missingness.md)
and [source freshness boundary](source_freshness.md).

Capture metadata and aggregate verification are recorded in
[`research/jma_source_validation_20261028.json`](../../research/jma_source_validation_20261028.json).
