# Explicit News buffer graph checks

The [single-buffer inspector](format.md) deliberately leaves cross-buffer
references unresolved. The separate `jwc24.news_bundle.inspect_news_bundle`
now checks those references against an explicitly supplied set of 24 buffers.
It neither fetches content nor registers hourly tasks or serves a response.

Topics refer to an article identifier in a buffer identified by the header's
update timestamp at offset 12. Article image references likewise use a target
buffer timestamp plus image index. The checker requires those target buffers,
articles and images to exist. No-image sentinels remain missing images, not
invented artwork. Source/location indices are already checked inside each
buffer by the individual inspector.

The exact 24-slot input shape follows the examined native validator, but does
not identify real hourly URLs or task registration. Identical snapshots may
repeat; that does **not** establish 24 hours of news. Different bytes for one
snapshot timestamp are rejected as ambiguous. Countries/languages must agree
under this local policy. Content digests distinguish supplied bytes only;
they do not establish publisher provenance, signature trust or Nintendo origin.

The [native graph report](../../research/news_bundle_validation_20261026.json)
records four comparisons. Three synthetic test methods execute the original Japanese validator and CRC
with actual cross-buffer topic/image references. Valid references pass without
pruning; an invalid image index in a resolved buffer returns native `-1`.
The original validator can prune an unresolved topic and still return zero,
and can accept an unresolved image timestamp. The strict bundle checker
rejects those incomplete graphs rather than silently dropping articles or
calling missing pictures available. This is explicitly stricter local policy.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_news tests.test_news_bundle
# Supply exactly 24 files; add --raw if they are already decompressed.
.venv/Scripts/python.exe -m tools.inspect_news_bundle <explicit-private-files>
```

The CLI reads only explicitly selected files and emits counts/scope. Paths,
article text, identifiers, links, opaque media and content digests stay out of
its output and representations. Aggregate supplied **and advertised decoded**
bytes are bounded at 32 MiB before any decoding; per-buffer/text/reference
limits from the individual inspector also apply. Parsed Python objects and
temporary text are additional memory, so this is not a 32 MiB process-memory
claim or a native capacity measurement.

Envelope handling remains structural and does not check signatures. Slot/time
mapping, current validity, provider observation/content currency, original
media decoders, native delivery and rendering remain unverified. Passing this
check never creates a successful native startup, publisher feed or on-console
news service. The implementation supplies no dummy articles or original assets.
