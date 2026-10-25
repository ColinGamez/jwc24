# HATJ CSData framing and native boundaries

October 26, 2026. This independently implemented inspector covers selected
framing and integrity checks from the original Japanese Nintendo Channel
HATJ v1792 main executable. It does not implement a usable software/video
catalog, submit reviews or restore browsing.

## Evidence chain

The original private DOL is 4,194,944 bytes, SHA-256
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
The existing extraction record verifies the supplied title's contents against
its TMD; this identifies that local build, not every Nintendo Channel release.

Tracing now connects filename/configuration evidence to the actual
`LoadToCSDataBuffer` diagnostic path and the subsequent consumer. The selected
private Nintendo collection index returned no literal `CSData` path rows; no
Nintendo service-source schema or authentic catalog sample was recovered by
that search. The following contract comes from the fingerprinted executable,
not a third-party recreation or unrelated nearby helper.

| Anchor | Verified role and limit |
| --- | --- |
| `0x80029550` | Loads/downloads bytes through other services; if the first byte's high nibble is `0x10`, allocates a `0x142EE`-byte working buffer and invokes the native decompressor before copying the result back. I/O, allocation and the complete load have not been executed by the new harness. |
| `0x800296E0` | Calls that loader, then the CSData consumer, and separately checks header prefix/version and an opaque status byte. Its complete service path has not been executed. |
| `0x800324D0` | Stores the input pointer and rejects a declared size outside `0x136..0x142EE`; invokes the CRC and format/reference checks. Harness execution stops before reference/URL construction. |
| `0x80032890` and `0x802A2250` | Saves BE32 at offset 8, zeros that word, runs the actual native CRC routine over BE32-at-4 declared bytes, restores the original word and compares. Synthetic tests match Python CRC-32. CRC integrity is not signature authenticity. |
| `0x800326F0` | Requires BE16-at-0 to be zero and byte 2 to be at least 6. Later outer checks reject versions above 6. The independent normal-data subset supports exactly 6. Byte 3 remains opaque. |
| `0x800328F0` | Rechecks size/CRC, requires termination within 256 bytes from offset `0x35`, then compares reference length with a separately configured limit. The harness substitutes that limit explicitly; it does not establish the real runtime configuration value. |
| `0x80100A20` and `0x80100A60` | Original uncompressed-size helper and LZ decompressor. Standard and extended-size LZ10/LZ11 synthetic fixtures produce the independent decoder's expected bytes. These checks do not verify malformed-input safety in the native decoder. |

The native prefix routine returns success early for some future-version or
nonzero-status cases. Those paths do not reach normal reference construction;
the outer caller separately rejects them. The independent inspector rejects
these unsupported cases rather than calling an early return a restored catalog.
No meaning is assigned to the status byte or the other opaque words.

## Independent bounded decoder

`jwc24/nintendo_csdata.py` accepts raw bytes or known `0x10`/`0x11` compression
framing. It checks the advertised output length **before** decompression, then
requires `0x136..0x142EE` available bytes, matching declared length, the CRC,
the supported normal-data prefix and bounded reference termination. The
reference is opaque bytes, excluded from `repr` and metadata output. This is
not UTF-8 validation, URL authorization or a request to that reference.

The original compression dispatcher accepts a `0x10` high nibble; the public
implementation deliberately supports only verified standard type bytes
`0x10` and `0x11`. Requiring exact available/declared length, bounding compressed
input and rejecting unsupported version/status cases are explicit safe-subset
policies. Retained bytes are not made current by passing these checks.

```powershell
.venv/Scripts/python.exe tools/inspect_nintendo_csdata.py private/path/csdata.LZ
.venv/Scripts/python.exe -m unittest tests.test_nintendo_csdata
```

The CLI reads at most the local input cap plus one byte, prints only validation
scope/counts and never publishes a payload. Fifteen tests cover supported size
boundaries, malformed input, CRC coverage/restoration, opaque private references,
read-only bounded CLI behavior and selected original consumer/decompressor paths.
Native tests skip when the private original or Unicorn is unavailable.

The native harness pins the complete executable fingerprint, enforces an
instruction limit and allowed code/write ranges, and checks input/object/output/
stack guards. Logging alone is stubbed in header-prefix mode. The configured
reference-length slot and initial object/stack are synthetic. Decompression is
checked only after the independent decoder has rejected unsafe streams.
Neither wrapper executes real filesystem, scheduler, allocation or network code.

## Remaining work

Recover record/table consumers, software/video identifiers and the relationship
between CSData references and subsequent catalog files. Bound the complete
loader's returned lengths and ownership/lifetime behavior, execute its actual
I/O/decompression/consumer sequence, and establish download/authentication and
freshness requirements. Then verify original search, rankings, details, video
and download flows. Review/bookmark/usage contracts remain separate. The new
component supplies no server route and no synthetic catalog for native browsing.
