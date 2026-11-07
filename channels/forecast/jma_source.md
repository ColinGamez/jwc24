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
| Short area / all forecast temperature points | `/bosai/forecast/const/forecast_area.json` |
| Weekly published groups / representative points | `/bosai/forecast/const/week_area.json` |
| Short-area alternate weekly group candidates | `/bosai/forecast/const/week_area05.json` |
| Published weekly group names | `/bosai/forecast/const/week_area_name.json` |

The forecast client displays each report's `reportDatetime` as its announcement
time. `timeSeries[].timeDefines` are separate target times. The parser retains
each report's date, publishing office, area identity and exact value tokens.
Empty tokens remain missing. Short-range `temps` remain a provider sequence in
the base parser; the separate explicit association projection described below
assigns reviewed source roles with date/count guards. Forecast wind text is not
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

## Published associations and dated temperature roles

`jwc24.jma_associations` accepts four separately receipted metadata resources.
It retains the office, `class10`, `class20` and **every** short-range temperature
point. Weekly associations retain their published `srf`, `week`, representative
temperature point and Japanese/English group names. The alternate-group table
is retained in published order. Candidate queries return every alternative
with separate weather-area, temperature-area, temperature-field and exact
observation-catalog membership flags. Callers can filter `forecast_present`;
the module selects no first candidate. A temperature forecast can exist even
when its point is absent from the observation catalog, and an observation
station can exist without the required forecast field.

An explicit catalog association, temperature point and report index are required
for temperature projection. The result preserves that report's original
`reportDatetime`, issued UTC instant, raw tokens, each `timeDefines` target and
JST calendar date, Celsius unit, and forecast/association/catalog receipts.
No common issue time or retrieval-time date replaces these source times.
Weekly rows keep the published group identity and representative point identity;
an island group is not relabeled as a member city or a measurement at that city.

The captured official client's pure selector chooses an issue bucket using JST:
before 05:00 or from 17:00 it uses `17`; before 11:00 it uses `05`; otherwise
`11`. For `17`, short-range slot 0 is next-day morning minimum and slot 1 is
next-day daytime maximum. For `05`/`11`, slot 0 is current-day daytime maximum,
slots 2/3 are next-day morning minimum/daytime maximum, and slot 1 is unused
by that selector. **All raw slots remain in the projection**, including unused
slot 1, null and empty tokens. Weekly `tempsMin`, `tempsMax` and their published
upper/lower arrays retain their own field roles and dates.

Local acceptance requires exactly two short-range slots for `17`, four for
`05`/`11`, and selected-role calendar dates consistent with the issue date.
It does not invent uncaptured 05/11 target hours or assign a role to slot 1.
Weekly targets must have unique consecutive JST dates beginning on the issue
date or following date. These and the base parser's increasing/unique target
time requirement are **local restrictions**, not established universal JMA
format guarantees. An unfamiliar shape rejects for review instead of being
repaired, retimed or silently mapped to another point.
In particular, a before-05:00 report is classified into `17` by the captured
selector, but no actual before-05 report/target combination was captured.
The projection still requires next-day targets relative to that report's JST
calendar date; a different shape rejects under the local guard. Its behavior
is covered synthetically and is not a proven provider-wide early-morning rule.

The metadata and actual forecast sample were captured on **2026-10-28 JST**.
Offline replay checked 58 offices, 142 short rows, 92 weekly rows / 91 distinct
weekly groups, and 142 candidate lists; 37 lists have multiple groups. All
weekly representative points occur in the captured observation catalog, while
short-range forecast points `63576` and `73136` do not. The actual `17` sample
has next-day 00:00 / 09:00 JST targets and matches the selector's min/max roles.
For `05`/`11`, only synthetic probes of the captured pure selector and synthetic
dated projection tests have been performed; **actual provider response shapes
for those buckets remain uncaptured**. All captures are historical evidence,
not a live refresh or present-day national data-coverage claim.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_associations
```

These source associations still assign no native Forecast city, infer no
nearest station, alter no published target area and activate no provider.
Evidence and measured test outcomes are recorded in
[`research/jma_association_validation_20261028.json`](../../research/jma_association_validation_20261028.json).

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

Native mapping still requires explicit native-city-to-published-area/station
provenance, weather-code mapping, actual 05/11 temperature shape evidence and
missing-field/rendering behavior. Native
Japanese wind formatting selects a km/h byte, whereas these source records
retain m/s. The separate [measurement projection](jma_measurements.md) now
converts units using an explicit JWC24 rounding/QC policy and suppresses
incomplete wind pairs. It does not choose native cities or publish weather.
[Original resource evidence](condition_resources.md) establishes actual
textures and numerical selector membership; JMA condition equivalence remains
unverified. [Source attribution](ATTRIBUTION.md) accompanies these tools and
must remain with service distribution/provenance. The original manual's
historical provider credit and an interrupting native message field are not
a verified inline credit path for replacement data. None of these gates is
relaxed by a successful parse. See the [native evidence](native_clock_and_missingness.md)
and [source freshness boundary](source_freshness.md).

Capture metadata and aggregate verification are recorded in
[`research/jma_source_validation_20261028.json`](../../research/jma_source_validation_20261028.json).
