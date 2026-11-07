# Original HMAC-SHA1 and application digest check

November 7, 2026. `jwc24.cmoc_hash` implements a bounded standard HMAC-SHA1
calculation and a separate inspection of the application's actual digest-check
predicate. This replaces an algorithm guess with original execution. It does
not load original secret resources, establish trust, authenticate service data
or activate the existing [callback](callback_lifecycle.md) digest boundary.

## Algorithm evidence

The unchanged Japanese HAPJ v512 executable is pinned to SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
All keys, messages, comparison tags, object storage and stack in the verifier
are synthetic inputs. Original resource/key files, device profiles, backups and
network services are not accessed. No original instructions, resource bytes or
secret values are committed.

`tools.verify_cmoc_hash` executes the original descriptor getter `0x801951EC`,
HMAC setup `0x80195594`, update `0x801957D0`, finalization `0x801957E0`, and their
original SHA1 initializer/update/final/compression functions. None of these
functions, memory helpers or comparisons is stubbed. The descriptor selects a
twenty-byte output, 64-byte block and 96-byte hash context, but those dimensions
alone are not the algorithm proof.

The resulting complete twenty-byte outputs match all seven published
[RFC 2202 HMAC-SHA1 test vectors](https://www.rfc-editor.org/rfc/rfc2202#section-3),
each under three chunk arrangements. The larger-key vectors execute the
original key-hashing branch. Further synthetic cases cover binary keys/messages,
empty data, empty update calls and message lengths 55/56/63/64/65/127/128/129/1024
around hash padding/block boundaries. This establishes HMAC-SHA1 interoperability
for the tested inputs; it is distinct from knowing a genuine service key.

## Actual application wrapper behavior

The complete application wrappers at `0x80079FF8`, `0x8007A0A4` and `0x8007A0E8`
also execute against those original SDK functions. The observed behavior is:

| Supplied state | Observed behavior |
| --- | --- |
| Key pointer absent | Clear worker `+0xC8` and enable byte `+0xCC`; updates return zero and the final check returns zero |
| Key pointer present, size argument nonzero | Use that explicit binary key size, including embedded NUL bytes |
| Key pointer present, size argument zero | Obtain the size through original `strlen` |
| Enabled update | Hash exactly the supplied span and return its byte count |
| Enabled final check | Produce twenty HMAC-SHA1 bytes, then perform the original bounded string comparison with limit worker `+0xC8` |

**Worker `+0xC8` is the resolved key length, not the algorithm's fixed output
length.** Its value is assigned from the supplied size or `strlen`; it also
drives the [receive layout](receive_geometry.md) and final comparison limit.
The SDK's independent HMAC operation supports tested long keys, including 80
and 128 bytes. This does not make the application's overlong final comparison
safe.

The final wrapper calls `0x800DE280`, which stops at the first differing byte,
the supplied count, or an equal NUL byte. It is **not** a binary `memcmp`.
Original execution with a first NUL at digest positions 0 and 8 accepts a tag
whose later bytes differ. A first NUL at position 19 permits a complete
twenty-byte comparison; a mismatch before that position still fails. Tests
record actual compared-byte counts, not just a boolean result.

A present empty C-string key enables hashing but resolves to size zero. The
native final string comparison then reads no digest/tag bytes and returns a
match. This is different from a null key pointer, which disables the check.
Neither zero-length acceptance nor the observed NUL-terminating result is
exposed as service authentication.

With synthetic key lengths 21, 25 and 64, the wrapper computes the correct
twenty-byte digest and supplies the overlong count to its string comparison.
The first twenty expected bytes match and contain no NUL; a dedicated memory
guard traps the attempted twenty-first digest-byte read **before reading an
unrelated stack byte**. This proves the unchecked read attempt for those
fixtures, not a specific hardware crash or trustworthy value for that byte.

## Bounded independent API

`hmac_sha1_digest(key, chunks)` provides standard HMAC-SHA1 over explicit bytes.
`inspect_application_hash(key=..., key_size=..., chunks=..., expected=...)`
separately returns the native predicate, actual comparison count, equal-NUL
termination, and a full-span binary comparison using `hmac.compare_digest`.
That binary result applies only to the explicit span; a short or empty span
does not become a complete twenty-byte MAC or establish source trust.

Nonzero `key_size` requires enough supplied binary key bytes. String mode
(`key_size=0`) requires an actual NUL in the caller's supplied key backing.
Present-empty string mode is `b'\0'`; neither the API nor the native harness
invents a missing terminator. Bytes after the first supplied NUL remain ignored
in that mode, while an explicit nonzero size preserves embedded NULs.

The application inspector rejects a resolved key size above twenty, rather
than inspecting stack data beyond the produced digest. It requires exactly
that many explicit expected comparison bytes. Null-key mode requires a zero
size and empty expected span as a local supported contract. These safeguards
are local restrictions; the original wrapper does not perform all of them.

Standard calculation permits keys up to 4096 bytes, up to 64 immutable chunks
and a total message up to one MiB. The native verifier deliberately limits
total message storage to 4096 bytes; the matrix tests keys through 128 bytes
and messages through 1024. Each inspection is a fresh calculation, not a
claim about repeated finalization, context reuse, cancellation or async state.
Keys, expected tags and computed digests are absent from result representations
and metadata; errors do not echo input bytes.

## Verification and remaining work

```powershell
.venv/Scripts/python.exe -m unittest tests.test_cmoc_hash
```

Six public tests and three native tests pass. Native tests skip honestly without
the pinned private executable or optional Capstone/Unicorn. The
[validation report](../../research/cmoc_hash_validation_20261107.json) records
98 direct SDK cases, 90 application-wrapper cases and three guarded overlong
comparison cases. The matrix covers all resolved application sizes 1..20,
null/present-empty/string/binary modes, mismatches, chunking, all seven RFC
vectors and equal-NUL positions 0/8/19.

The verifier bounds code, reads/writes, instructions, objects and stack; checks
immutable inputs/guards; and executes real SHA1/HMAC and string comparison.
Hash padding uses the original constant byte and a checked eight-byte span
inside the original DOL loader-zero BSS. That exact BSS span is explicitly
admitted and verified unchanged; mapped RAM generally is not accepted as
unsupplied backing. No initializer that loads a service key or secret resource
is executed.

Live resource loading, genuine key/identity/trust provenance, cipher/compression
processing, signed/authenticated envelopes, SDK chunking and context lifetime,
cache persistence and original full channel UI remain unfinished. The existing
callback's explicit digest boundary remains unchanged until a later composed
flow has those inputs and bounds verified.
