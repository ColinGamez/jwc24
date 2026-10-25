# Provider catalog publication integrity

The retained Rakuten directory experiment is separate from Wii no Ma's
unfinished original Flash shop and native checkout. This publisher change
does not implement either, make a product orderable, or establish authentic
Nintendo artwork or metadata.

`rakuten.write_catalog` now uses the existing stable identity registry when
refreshing a catalog. Removed entries retain reserved identities, so a later
returning product cannot collide with another entry's in-channel identifier.
The same cross-process directory lock covers reading the old catalog,
assigning identities and publishing the complete new document. Invalid old
state fails before publication instead of resetting identities silently.

The writer uses a unique temporary file in the destination directory, rejects
nonfinite JSON numbers, flushes/syncs the complete file and atomically replaces
the catalog. Bounded retries cover transient Windows reader-sharing failures;
other errors preserve the old bytes and remove the temporary file. This is
single-file publication integrity, not a transaction across artwork or proof
that provider availability and price observations are current.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_shop_catalog tests.test_rakuten_publication
```

Ten tests pass without private provider assets, including two independent
publisher processes, identity retention, malformed previous state, failed
replacement, cleanup and transient Windows sharing. Synthetic product prices
exist only inside tests, never as published default products or restored
original-channel data. No provider was contacted or live catalog refreshed.
