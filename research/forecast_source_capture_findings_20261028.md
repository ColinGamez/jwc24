# Forecast source capture and timestamp evidence

October 28, 2026. Two bounded, read-only source requests were captured to inspect
actual timestamp provenance and available weather fields. This is source
evidence for the next adapter step, not an activated weather refresh or proof
of a complete current-data feed.

Provider-specific request details, selectors, code, raw responses and header
values remain in ignored private storage under the existing
[source policy](../channels/forecast/README.md#weather-data-source-policy).
No credentials, cookies, authentication, account creation or bulk collection
were used. This work does not establish additional provider permissions.

## Captures retained privately

| Capture | Observed result | Bounds |
| --- | --- | --- |
| Public HTML response | HTTP 200, 553,086 bytes, complete within the limit | One request, 2 MiB accepted-body limit, 30-second timeout, no followed redirects |
| Weather JSON referenced by that actual page | HTTP 200, 268 bytes, complete within the limit | One request, the same size/time limits, no followed redirects |

Raw response bodies, complete response headers, retrieval start/end times and
SHA-256 digests are preserved in
`private/forecast/source-audit-20261028/`. The second request was derived from
an actual function in the first captured response. It was not a guessed API,
credentialed endpoint or a request repeated until acceptable values appeared.
No raw material or exact request/selector details are included in Git.

## Timestamp findings

The HTML displays an observation time-of-day, but this capture did not establish
a complete provider observation or issuance timestamp with calendar date and
timezone. Its relevant inline current-date variable comes from the browser's
clock. The captured page metadata did not establish a weather issue date.
HTTP response time and retrieval time remain transport evidence, not a
replacement for a provider-origin timestamp.

The referenced JSON includes two daily-forecast timestamp candidates. They are
one day apart, align with consecutive local-calendar midnights, and one is in
the future relative to retrieval. Together with their daily-record context,
this is evidence consistent with forecast **effective dates**, not established
issuance times. Their exact source semantics remain unverified. They cannot be
promoted to observation/issue receipts merely because they are full epochs.

No truthful source-age receipt was produced from these responses. Neither a
new envelope window nor a newly rebuilt native location clock repairs that
missing evidence. The existing [source-time gate](../channels/forecast/source_freshness.md)
continues to require the independent observation/issue basis; it was not relaxed
to accept a fetch clock or forecast target date.

## Available fields and the old adapter

The JSON supplies a limited daily forecast: condition, high/low temperature
and daily precipitation probability are present. This capture does not supply
current observations, wind, the four explicit six-hour condition/probability
slots, or the complete native index fields. A daily probability must not be
repeated into four slots, nor should missing wind or indices become fabricated
measurements.

A non-executing shape comparison also found that the old private adapter's
observation selector has no match in this HTML, while its hourly-forecast
selector does match. Its existing fallback would select forecast data when an
observation is missing. That would not establish a genuine current observation.
This finding applies to the one retained capture; it does not prove a site-wide
change or coverage for every native location.

The old adapter was inspected without import or execution and remains unchanged
as a prior experiment. No historical reference weather, invented source date,
fallback observation or normalized dataset was generated or substituted.
Active payloads, signing keys, tasks, profiles and devices were untouched.

## Next acquisition requirement

Use an authorized response or provider specification that establishes full
observation timestamps and actual forecast issuance metadata separately from
forecast target times. Then preserve source fields, units, missingness,
corrections/expiry and transformation provenance before constructing native
records. The two captures do not establish that no suitable provider interface
exists; they establish that these particular inputs do not yet close the
current-data provenance gate.
