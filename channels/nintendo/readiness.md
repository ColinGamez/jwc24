# Nintendo Channel restoration gates

October 26, 2026. The extracted Japanese HATJ v1792 client is available as a
private input. Its service has not been restored. The original main DOL's
SHA-256 is `aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
See [the initial inventory](research.md) for the verified title and resources.

The bounded local follow-up confirms `csdata.LZ` is returned by an original
filename accessor at `0x800314D0`, and `CSData.bin` is passed by the original
configuration path around `0x8002A518`. This establishes references, **not** a
CSData schema. Nearby generic CRC/string helper routines must not be labeled
catalog validators solely because they occur near that accessor.

The private Nintendo collection index was searched for the literal path
`CSData`; it returned no rows. The index covers selected documents and prior
archive listings, not every opaque payload, so that result does not establish
that the collection lacks the format. Filename hits such as `entd` also match
unrelated words and do not establish a recovered service source tree.

Before native browsing can be offered, the remaining gates are:

1. Trace the actual catalog load path from the file/cache callback through
   decompression, allocation bounds, integrity checks and record consumers.
2. Recover software, video and download identifiers and their record layouts;
   independently validate current or historically captured data and provenance.
3. Establish WC24 registration and direct-fetch contracts separately, including
   first-run prerequisites and freshness behavior.
4. Preserve original list, search, rankings, details and video UI. Confirm the
   actual movie format before preparing playable media.
5. Recover review/bookmark/usage submission contracts independently; never
   report an accepted submission merely because transport succeeds.

No emulator was launched, service host contacted, data submitted, WAD modified,
or real-console backup accessed during this follow-up. The original files and
derived disassembly remain private. A broad project preflight must report
this channel as unfinished rather than pass it on filename evidence.

The subsequent [CSData framing recovery](csdata_contract.md) now connects that
lead to the actual load/consumer path, whole-file CRC, supported version and
reference checks, and native LZ10/LZ11 helpers. A bounded independent inspector
and synthetic native comparisons are implemented. Record semantics, the full
I/O/load sequence, authentic catalog data and native browsing remain unfinished.
