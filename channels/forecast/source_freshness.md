# Forecast source-time gate

The Weathernews permission and confidentiality direction are recorded in the
[channel source policy](README.md#weather-data-source-policy). This batch did
not independently inspect the owner's permission letter or contact a provider.
No credential value was used or emitted. Provider-specific selectors, endpoints,
code and captures remain
private. No live acquisition, signing, server update or profile/task operation
was performed.

The existing private refresh pipeline must **not be used as the accepted current
data refresh path** in its audited form. Its assembly stage replaces record
times with the build clock and substitutes missing international weather using
a historical reference payload. Its normalizers also use parsing time without
preserved independent observation/issue-time receipts. Thus a new file mtime or
new envelope window cannot establish current observations. The pipeline was
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
| `normalization_retimed` | Boolean `false` |
| `reference_weather_substituted` | Boolean `false` |
| `datasets` | Exactly `current`, `long`, `compact` receipt objects |

Each dataset object contains `normalized_sha256` binding its exact input bytes,
and `entries` covering every unique native location key in that document.
An entry has exactly `key` (country/region/location integers), `source_sha256`,
`source_ref`, `time_basis`, `source_time_utc`, `retrieved_utc`, `valid_until_utc`,
and `utc_offset_minutes`. The permitted time basis is `provider_observation` or
`provider_issue`, never fetch/parse/build time. Source time, fetch time and
expiry use integer UTC Unix seconds; the offset explicitly reconstructs the
native local clock field. No original/provider sample is committed.

The gate checks document digests, unique complete receipt keys, no conflicting
duplicate rows, bounded fields and receipt flags. Provider source time must be
no later than retrieval, retrieval no later than now, and supplied expiry later
than now. Source age must be strictly less than the explicit policy. Each
normalized local timestamp must equal its receipt's UTC source time plus its
explicit offset. Identical repeated normalized rows are retained and counted.
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
that a new fetch cannot refresh old source data, a retimed row fails even with
a recomputed normalized-document hash, and parse-time/historical-reference
attestations, expired/future inputs and incomplete provenance reject.

This is not a complete Forecast builder/publication orchestrator. After genuine
fresh acquisition succeeds, the existing paired binary/signature validator is
still required. A future publisher must cap delivery at the earliest supplied
source expiry as well as both native validity-window ends; a passing envelope
does not extend provider data life. Record construction must preserve source
dates, missing-weather sentinels and actual data rather than retiming a past
fixture. Original client trust, native weather rendering and Wii no Ma's panel
still need the coordinated end-to-end check.
