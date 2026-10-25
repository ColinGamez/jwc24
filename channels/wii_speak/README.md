# Wii Speak Channel Japan — HCFJ

First service-role audit, October 26, 2026. The owned package is title
`000100014843464A`, version 512, requiring IOS56. All nine extracted contents
match their source TMD sizes and SHA-1 hashes. The Nintendo TMD signature has
not been independently verified. Original files remain private.

## Baseline classification

**This needs separate online-communication and version-download investigations.**
A generic WC24 HTTP listener or a catalog of friends does not restore voice
communication. The application contains DWC/NAS/GameSpy evidence, separate
WC24 download/scheduler API markers, and an application-level version descriptor.
Compiled SDK endpoints are leads; their presence does not establish that every
listed domain is used by this channel.

The real application is LZ11-compressed content index1, not the small boot DOL
at index8. Its SHA-256 is
`7da329f17754d3199b6254f26c3e059913671820f9017c2424236430aa64eff3`.

In initializer slice `0x800B9624..0x800B9718`, native code references
`http://nwcs.wapp.wii.com/hcf/version.enc`, places that pointer in a descriptor,
and passes the descriptor to consumer `0x800423B4` at `0x800B9714`. Packaged
crypto-resource selectors are loaded nearby; their bytes stay private. That
does not yet recover the envelope, signature/decryption rules, task registration,
descriptor field meanings or successful callback behavior.

The endpoint above is concretely a **version-file reference**. It must not be
renamed into a proven voice broker just because it is a Nintendo service host.
Separately, NAS/GameSpy/DWC markers support tracing authentication, presence,
matching and peer communication, without assuming their exact retail call chain
or compatibility with any present-day provider.

The shared `network.csv` resource is localized UI text, not a provider settings
file. Native letter/photo-related resource names are also not proof of accepted
mail, delivery or receipt of a voice message.

## Still required

- Complete the version descriptor-to-downloader/crypto/callback path and recover
  the real payload contract before generating or serving a feed.
- Trace the channel's actual authentication/friend/voice and microphone/device
  consumers; preserve voice, network and Message Board semantics separately.
- Verify any proposed WFC provider for this exact channel. JWC24's general
  Wiimmfi/WiiLink planning does not establish Wii Speak compatibility.
- Test native UI, hardware/audio, connection failure and delivery behavior in
  the coordinated controlled-device pass.

No server route, provider redirect, account, voice session, mail or emulator
launch was created. No actual Wii backup or device credential was read.
See the [shared provenance and scope](../../research/additional_channel_services_20261026.md).
