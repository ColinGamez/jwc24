# Forecast source-time gate

The Weathernews permission and confidentiality direction are recorded in the
[channel source policy](README.md#weather-data-source-policy). This batch did
not independently inspect the owner's permission letter or contact a provider.
No credential value was used or emitted. Provider-specific selectors, endpoints,
code and captures remain private. No live acquisition, signing, server update or profile/task operation
was performed.

The existing private refresh pipeline must **not be used as the accepted current
data refresh path** in its audited form. Its assembly stage substitutes missing
international weather using a historical reference payload, and its outputs
lack independent provider observation/issue-time receipts. The native row clock
fields are a separate matter: rebuilding a local/UTC clock anchor is not proof
that provider dates were fabricated. Original code uses the difference between
those fields to derive a location calendar, as detailed in the
[native clock and missingness evidence](native_clock_and_missingness.md).
A new file mtime or envelope window cannot establish current weather. The pipeline was
inspected without running or importing its top-level execution code; it was
left unchanged to preserve the prior experiment.

`jwc24.forecast_freshness.check_forecast_sources` adds a provider-neutral,
read-only acquisition boundary. It accepts three exact normalized JSON byte
documents (`current`, `long`, `compact`), explicit source-time receipts, current
UTC time, and an explicit maximum source-age policy. It does not infer provider
permission, an observation date from parse time, or a default weather value.

Each receipts document has exactly these top-level fields:

| Field | Required value |
| --- | --- |
| `schema_version` | Integer `1` |
| `rights_ref` | Nonempty bounded private source/rights review reference |
| `provider_times_retimed` | Boolean `false`; provider source-time evidence was not replaced with fetch/parse/build time |
| `reference_weather_substituted` | Boolean `false` |
| `datasets` | Exactly `current`, `long`, `compact` receipt objects |

Each dataset object contains `normalized_sha256` binding its exact input bytes,
and `entries` covering every unique native location key in that document.
An entry has exactly `key` (country/region/location integers), `source_sha256`,
`source_ref`, `time_basis`, `source_time_utc`, `retrieved_utc`, and `valid_until_utc`.
The permitted time basis is `provider_observation` or
`provider_issue`, never fetch/parse/build time. Source time, fetch time and
expiry use integer UTC Unix seconds. There is no native-clock offset in this
receipt schema and no equality requirement between a provider source time and
the normalized `local_unix_timestamp` field. No original/provider sample is committed.

The gate checks document digests, unique complete receipt keys, no conflicting
duplicate rows, bounded fields and receipt flags. Provider source time must be
no later than retrieval, retrieval no later than now, and supplied expiry later
than now. Source age must be strictly less than the explicit policy.
Native clock fields are not used as source times; metadata explicitly reports
`native_clock_fields_used_as_source_times: false`. Their correctness belongs to
the separate native clock/locale/build contract, not this provider-age check.
Identical repeated normalized rows are retained and counted.
Missing native fields or receipts reject; no record is silently filled or
replaced. Current and at least one forecast dataset must be nonempty.

A caller can falsely attest to a source time or source digest. Therefore output
explicitly keeps provider timestamp extraction and rights independently
unverified. Passing this gate proves consistency with supplied receipts, not
that the private provider parser extracted truthful data or that every catalog
location has weather. That adapter must be reviewed and changed to preserve
real provider-origin times and source provenance first. Existing private
normalized files do not contain these receipts and were not accepted merely
because they already exist.

```powershell
.venv/Scripts/python.exe tools/check_forecast_sources.py `
  --current PRIVATE_CURRENT --long PRIVATE_LONG --compact PRIVATE_COMPACT `
  --receipts PRIVATE_RECEIPTS --max-source-age-seconds EXPLICIT_LOCAL_POLICY
.venv/Scripts/python.exe -m unittest tests.test_forecast_freshness
```

The CLI uses bounded reads, reports aggregate metadata only and leaves inputs
unchanged. It neither imports the private adapter nor emits keys, source URLs,
location names, weather rows or reference contents. Synthetic regressions verify
that a fresh provider receipt can accompany an independently rebuilt native
local clock, while old provider evidence still fails despite a current native
clock, fetch time and document hash. Parse-time/provider-retiming/historical-reference
attestations, expired/future inputs and incomplete provenance reject.

This is not a complete Forecast builder/publication orchestrator. After genuine
fresh acquisition succeeds, the existing paired binary/signature validator is
still required. A future publisher must cap delivery at the earliest supplied
source expiry as well as both native validity-window ends; a passing envelope
does not extend provider data life. Record construction must preserve source
dates, missing-weather sentinels and actual data. It must not present historical
weather as newly observed merely by rebuilding native clock fields. Original
client trust, native weather rendering and Wii no Ma's panel
still need the coordinated end-to-end check.
