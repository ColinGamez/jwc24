# News structural decoder and native validation

October 26, 2026. `jwc24/news.py` provides independent offline inspection of a
single decompressed News buffer. This is a protocol component, not a restored
news service, publisher feed, native UI or successful first-run response.

## Evidence and provenance

The private Japanese HAGJ v7 application DOL is pinned by SHA-256
`8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852`.
Static tracing links the startup state machine's call at `0x800084E8` to the
buffer validator at `0x8000AFC8`. The original DOL, resource files and derived
disassembly remain private and unchanged.

Separately, the public [WiiLink News generator](https://github.com/WiiLink24/NewsChannel/tree/daccc47b22a6a045aaaa7d5b86548525c3c2ea7c)
supplied semantic-name, headline-table and envelope leads. It is a third-party
restoration implementation, not Nintendo source or a JWC24 dependency. It was
read, not built or run. [An independent researcher's USA-v7 notes](https://gist.github.com/quatric/e571ed2400339867bf9d52701e59db24)
also supplied address leads; this pass checks the stated Japanese fingerprint
directly rather than assuming another regional client's behavior is identical.

## Native execution scope

`tools/verify_news_native.py` executes the **complete** original buffer validator
at `0x8000AFC8` through its return, the original CRC routine at `0x8007621C`, and
the original register-save/restore helpers. Only current-time, tick and calendar
services are mocked. Its inputs are exactly 24 synthetic bytes-or-empty slots.
No file system, network, keys, signature verifier, title installation or native
screen runs in this harness.

Native execution verifies:

- Each present buffer's declared size must equal its supplied actual size.
  CRC32 covers bytes 12 through the end. Damage rejects the buffer with `-1`.
- The version's upper sixteen bits must be zero; nonzero yields `-3`. This
  does not require the lower bits to equal the third-party generator's 512.
- The language list has a terminating `0xFF` within sixteen bytes; preceding
  codes are below seven. Two independent header flags are below two.
- Five native tables have four-byte-aligned offsets and strides of 12, 44,
  28, 16 and 24 bytes: topics, articles, sources, locations and images.
- Latest-topic timestamp/ID pairs are resolved through the hourly buffers,
  then referenced articles' source/location/image indices and text spans are
  checked. Source, location and image records receive their native checks.
- The active slot is selected using the secondary timestamp. Missing hours
  produce a refresh mask and `-2`, separately from one buffer's structure.

The returned native status is not a complete service result. A synthetic set
of 24 valid buffers returns zero, but an expired set containing a server-message
offset also returns zero in this routine. The later original UI has separate
server-message handling. The decoder exposes only a `server_message_present`
boolean in metadata and claims no freshness or displayed articles.

The native close-time comparison accepts equality. The secondary timestamp is
checked against the supplied time plus 1440. These are observed boundaries in
this routine; the independent decoder leaves current-validity checking false.

## Bounded structural inspection

The decoder validates the 104-byte header, size, CRC, language list, flags,
message span and six table ranges. It reads article text as strict UTF-16BE,
checks source/location/image references within the same buffer, validates
bounded media spans, and resolves local topic timestamp/ID references. It does
not decode JPEG pictures or prove their native decoder accepts them.

The headline/ticker table is a separate 8-byte-entry layout corroborated by the
public generator. **This native validator does not check that table.** Its
inspection is an explicit extra safeguard; banner rendering remains unverified.

Some native behavior is intentionally not reproduced:

- Arithmetic does not wrap. Native table-size multiplication can wrap on
  malformed counts and eventually read outside the supplied body; the harness
  traps such reads. The decoder rejects oversized counts before iteration.
- Tables cannot overlap the header or each other. Text/media cannot overlap
  table storage. UTF-16 sizes must be even, terminated and bounded. Those
  safeguards are stricter than this original validation pass.
- The original latest-topic pass removes unresolved references and article
  bodies of at least 20000 bytes from its synthetic in-memory topic list. The
  independent inspector rejects missing **local** article references and such
  body lengths; it never silently rewrites input or claims a missing article
  became available.
- References naming other hourly buffers are retained as unresolved counts.
  `cross_buffer_references_checked` stays false; one file is insufficient to
  prove a complete 24-hour article/image graph.

Local bounds are 4 MiB decompressed input, 5 MiB envelope input, 4096 entries per
table, 65536 topic references and 8 MiB aggregate unique decoded text. Reused
text spans are cached to prevent repeated-reference expansion. These are
inspection policies, not native channel capacity claims.

The envelope helper recognizes the 320-byte-envelope/LZ10 shape corroborated
by the public implementation and invokes JWC24's existing independent LZ10
decoder with a decompressed-size bound. **It does not verify the signature.**
Original signature trust, native compression/envelope execution and WC24
authentication remain unfinished. A zero-filled synthetic envelope is accepted
only for structural testing and is never served as channel data.

## Checks and remaining work

```powershell
.venv/Scripts/python.exe -m unittest tests.test_news tests.test_news_native
.venv/Scripts/python.exe tools/inspect_news.py <private-local-file> --raw
```

Tests use generated synthetic Japanese/surrogate text and opaque media bytes,
not actual articles, original pictures or publisher copy. Native tests skip if
the pinned private DOL or optional Unicorn package is unavailable. The harness
enforces code/read/write ranges, bounded instructions, buffers and stack guards;
only the observed topic-pruning stores may alter synthetic body storage.
Reports contain counts, statuses, selected slots and mutation counts, never
article text, media, credentials or original code.

Next work is native envelope/decompression and trust handling; the actual WC24
registration, URL suffix and refresh contract; independently licensed current
Japanese news inputs; complete cross-hour references; and the original banner,
globe, categories and article UI. No server route, scheduled publication,
original asset replacement or console/profile change was made in this pass.
