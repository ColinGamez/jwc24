# Paired Forecast publication checks

The individual `forecast.bin` and `short.bin` validators check their native
structures separately. Before a coordinated test or publication, the read-only
bundle check also joins current-weather rows to the full location catalog and
weather-condition dictionary. It rejects conflicting current location rows,
missing locations or conditions, different country/language fields and validity
windows that do not overlap. Current observations may cover a subset of the
catalog. The missing-condition value `0xFFFF` remains missing weather.
Identical repeated rows are retained and counted, rather than silently deleted.

These are explicit JWC24 publication policies built on the recovered layouts,
not newly established native rejection behavior. They cannot establish that
every catalog location has an observation or that a provider's report is true.
They do not pick a location, change save data, refresh timestamps, publish files
or launch Dolphin.

```powershell
.venv/Scripts/python.exe tools/validate_forecast_bundle.py `
  private/forecast/generated/current/forecast.bin private/forecast/generated/current/short.bin `
  --public-key private/forecast/jwc24-forecast-public.pem --require-current
```

With `--public-key`, OpenSSL checks each file's existing 256-byte RSA/SHA-1
signature over the compressed body against the supplied key. Failed verification
stops validation. Without the option, structural historical inspection remains
available and the JSON output explicitly reports that signatures were not
verified. The 64-byte reserved prefix is outside that signed body.

A valid signature against a supplied JWC24 key does **not** prove that the
installed channel trusts that key, that a stock Nintendo client accepts a
replacement payload, or that WC24 delivery and rendering work. The public key
must match the explicitly prepared isolated test client's working-copy trust
patch. Stock software, original trust resources and private keys stay private.

`--require-current` independently checks both half-open validity windows at the
current time. Omitting it permits historical inspection. Output contains counts
and validation scope, without city names, provider details or key contents.
This checks the files' envelope validity windows, not the observation timestamps
inside their records. An old observation can appear in a newly generated file;
the report explicitly sets `observation_timestamps_checked` to `false`. Provider
acquisition/provenance checks must establish observation freshness separately.
This tool does not invent a provider-specific maximum observation age.
The bounded reader's 20 MiB limit is local tooling policy, not a measured native
download limit. Original single-file tools and live publication paths are
unchanged; this new check has not been wired into a private refresh job.
