# Original cipher and application wrapper

November 7, 2026. `jwc24.cmoc_cipher` implements a bounded offline AES-CBC
projection, checked against unchanged Japanese HAPJ v512 code using synthetic
keys and messages. This replaces an unverified cipher boundary with executable
algorithm evidence. It does not yet connect that implementation to the
[response callback](callback_lifecycle.md), recover a genuine resource envelope,
or establish service authentication.

The private executable is pinned to SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
Its original bytes and static tables remain private and unchanged. Public code
uses PyCryptodome through the optional `crypto` extra; it does not copy Nintendo
or SDK cipher tables or implement a second AES core.

## Algorithm and original paths

The complete original key expansion at `0x80196580`, selected through
`0x80196730`, accepts sixteen-, twenty-four- and thirty-two-byte keys. The
original decoder at `0x8019673C` dispatches sixteen-byte blocks to `0x80196890`
and the unchanged software block core at `0x80196194`. Full plaintext and final
CBC chaining state match the public [NIST SP 800-38A](https://csrc.nist.gov/pubs/sp/800/38/a/final)
F.2.2/F.2.4/F.2.6 vectors
for all three key sizes, across whole-message, one-block and empty-interleaved
chunk arrangements. Separate output and exact in-place buffers are covered.

`decrypt_aes_cbc()` requires an explicit sixteen-byte IV and complete blocks in
every chunk. It neither pads nor unpads. Empty chunks retain the chain. CBC
chaining uses the last ciphertext block, including in-place decoding. These are
algorithm results, not proof of the provenance or authenticity of an input.

## Application semantics

The complete setup `0x8006924C`, decode `0x80069388` and cleanup `0x80069330`
execute in the native verifier. Their behavior differs from the strict direct
algorithm API:

| Original application path | Observed result |
| --- | --- |
| Null key pointer | Disable cipher; later decode copies the supplied input and returns its size |
| Nonzero key size | Use that many explicitly supplied binary key bytes |
| Zero key size with a nonnull key | Resolve the actual NUL-terminated string length; only lengths 16/24/32 enable AES |
| Null IV pointer | Setup explicitly constructs sixteen zero bytes on its stack |
| Setup acquisition fails or SDK rejects key size | Clear enabled flag and resolved key size; later decode uses the copy path |
| Enabled decode acquisition fails | Return zero, leave caller output and chain untouched, retain enabled state |
| Enabled decode receives a non-block size | SDK returns false without writing; application nevertheless returns the requested size |
| Enabled decode succeeds | Return requested size and write the exact decoded bytes |
| Cleanup acquisition fails | Retain enabled flag and resolved key size |
| Cleanup acquisition succeeds | Clear enabled flag and resolved key size; no key/chain erasure is established |

The setup function's `r3` value is not a meaningful boolean success contract.
For example, the null-key branch can leave the context pointer in that register.
The projection inspects the actual enabled flag and resolved size instead.

`inspect_application_cipher()` requires explicit setup, chunk and optional
cleanup acquisition outcomes. A result's `written=None` means no write to the
caller's existing output. It is distinct from `b''`, an empty successful write,
and from the disabled copy path. Requested size, application return size and SDK
acceptance are retained separately. Invalid sizes and failed acquisitions never
advance its CBC chain. The API does not retry or fabricate output. Keys, decoded
bytes and chaining state are excluded from result representations and metadata.

The original acquisition helper at `0x80195DFC` and release helper at
`0x80195E8C` also execute. Failed close leaves the synthetic global handle
retained, so a later acquisition can succeed without a new open. The application
projection takes the **observed helper outcome**, rather than equating each
acquisition with an IOS open. Underlying IOS open/close calls and diagnostics are
explicit synthetic boundaries; this verifies neither real IOS nor concurrency.

## Verification and limits

`tools.verify_cmoc_cipher` accepts the exact executable as a byte argument. It
does not discover files, credentials or profiles. Native fixtures admit at most
64 chunks / 4,096 input bytes and 64 key bytes. The public direct API is bounded
to 64 chunks / one MiB. Every native input, output, context and stack has explicit
backing and guards. The original string scan is stopped at the supplied backing
boundary if a required terminator is missing; a guard's bytes do not count as
provided key data.

Read hooks admit only supplied objects, the bounded stack, the synthetic handle,
the exact AES table spans `0x802DDB98..0x802DDDB8` and
`0x802DE1B8..0x802DE5B8`, and descriptor `0x8042F008..0x8042F010`.
Writes are confined to supplied mutable objects, stack and handle. No original
resource or device key span is admitted. Cipher/key expansion, copies, flag
changes, length checks and acquire/release helpers are not stubbed. Output write
counts, unchanged backing, return values, flags and final chain are compared
against the independent projection.

Run `python -m unittest tests.test_cmoc_cipher -v`. Algorithm tests require the
optional `crypto` extra; native tests additionally require Unicorn, Capstone and the
private pinned executable. Missing optional material produces explicit skips,
not native verification. The metadata-only [validation report](../../research/cmoc_cipher_validation_20261107.json)
records the tested scope.

The subsequent [configured callback proof](transform_pipeline.md) verifies actual
hash/cipher/decompression order and output on explicit synthetic success cases.
Failure-path persistent backing/count and genuine chunk-capacity integration
remain separate. Remaining work includes real envelope framing, original
resource formats and ownership, actual IOS/SDK transport, concurrent handle use,
cache lifecycle, server authentication
and complete native channel flow. Successful AES vectors prove none of those.
No device credentials, original resource keys, emulator profiles, actual Wii
backup, network service or native user interface are modified by this work.
