# Today and Tomorrow Channel Japan — HAVJ

First service-role audit, October 26, 2026. The owned package is title
`000100014841564A`, version 512, requiring IOS35. All twelve extracted contents
match their source TMD sizes and SHA-1 hashes. The Nintendo TMD signature has
not been independently verified. Original files remain private.

## Baseline classification

**Treat the core as a local-channel track, rather than inventing a hosted fortune
feed.** Its application image has bundled fortune/affinity resources and a local
save name. No application URL literal or named active HTTP/DWC entry was found
in the selected application scan. This is bounded static evidence, not proof
that every possible feature is offline or that the native experience is tested.

The real application is LZ11-compressed content index1, not the small boot DOL
at index11. Its SHA-256 is
`fdf597412f5dedf2dd4b9388204ed35a52ad3624282a23c08bb54d29f237f0d2`.

The initializer at `0x8009B770` reads a resource-table entry and calls consumer
`0x800A7780` at `0x8009B854`. The original stored entry selects content archive6
and `etc/affinity.bin`. That archive contains the corresponding **20,580-byte**
resource, SHA-256
`f871fb665fc76ae87c970e2c5ec9d0c74f04020af716331a059c6e2a95bed25c`.
The application also references local save `uranai6.dat`. The table and save
contents have not been interpreted as a complete prediction algorithm.

Common platform strings such as scheduler resume/shutdown and WC24 file paths
also occur in this image. Their inclusion does not establish a channel-specific
download task. A bundled Opera/manual resource similarly does not establish an
online forecast provider.

## Still required

- Verify original date/birthday/Mii flows and save behavior in the controlled
  native test pass, including date rollover and unavailable/invalid local data.
- Recover any remaining prediction-table/controller semantics needed for a
  particular failure, without generating replacement fortunes or custom screens.
- Trace a concrete channel-specific request before adding any hosted task or
  treating generic SDK code as a service dependency.

No service manifest, replacement data, patch, installation or emulator launch
was added by this audit. No actual Wii backup or personal save was read.
See the [shared provenance and scope](../../research/additional_channel_services_20261026.md).
