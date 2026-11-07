# Selected JMA source ages

`jwc24.jma_freshness.check_jma_age` checks explicitly selected parsed inputs
against an explicit local operating policy. It does not select a city, station,
report or observation, authenticate supplied objects, acquire sources, construct
a native payload or publish weather.

The caller supplies all five bounds in `JMAAgePolicy`; there are no default
cadences or claims that these are JMA-recommended limits. Observation, forecast
issue, national latest observation, metadata cache and relative station lag are
separate limits.

| Input | Age basis |
| --- | --- |
| Each selected forecast report | Its own provider `reportDatetime` |
| Selected station record | Its original JST record key / observation instant |
| National latest response | Its full provider observation timestamp |
| Station and association catalogs | Their receipt's retrieval end (cache age) |
| Optional area hierarchy / condition client | Their own retrieval end (cache age) |

Metadata retrieval age is a cache check, never a substitute weather issue or
observation time. Fetching old weather again does not renew its eligibility.
Each checked source expires at its basis plus its own explicit limit; the
check rejects at the exact expiry. Provider times after retrieval, retrieval
after the check clock, raw/parsed date disagreement, incorrect office or point
window, ambiguous observations and incomplete association receipts reject.

Station lag is national observation time minus the selected station observation
time, and must be nonnegative and strictly below its explicit bound. It is a
relative consistency check; it does not replace either source's age limit.

The returned earliest expiry is the minimum of all checked source/cache
deadlines. A future publisher must check **all of its actual dependencies** and
cap publication at this deadline and the native format's validity limits. It
must not turn a new build, fetch or native clock into a new source issue time.

The required metadata consists of the station catalog and all four association
catalogs. Area hierarchy and condition-client receipts are accepted only as
explicit extra dependencies. Duplicate URL snapshots reject. Receipts must use
the reviewed exact JMA HTTPS routes, successful status, bounded body size,
digest syntax and consistent retrieval intervals. These are consistency checks
on caller-supplied parsed objects, not independent authentication of their
contents or provenance. The age component cannot rehash raw bodies it was not
given. Existing byte parsers remain responsible for receipt/body binding.

## Verification and limits

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_freshness
```

The 13 focused tests passed on November 7, 2026. Synthetic cases check exact
deadlines, old weather with new receipts, independent report ages, station lag,
explicit selection, malformed receipts, incomplete dependencies and separate
metadata expiry. An optional replay reads the retained October 28 capture and
association bundle, checks it at its historical retrieval time, and rejects the
same unchanged records at a November 7 clock. No source dates are rewritten and
no network requests occur. Missing private captures produce an explicit skip.

Native city identity, complete field availability and condition mappings,
attribution placement, native time windows, payload consistency, signing and
hardware rendering remain separate requirements. The result's metadata keeps
these limits explicit and never reports native publication or independent
source authentication as completed.
