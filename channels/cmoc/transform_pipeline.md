# Configured callback with actual hash, cipher and decompressor

November 7, 2026. `tools.verify_cmoc_transform_pipeline` closes the isolated
algorithm-to-callback verification gap for an explicit synthetic success domain.
It executes the complete original event-2/event-4 dispatcher with actual
HMAC-SHA1, AES-CBC, streaming LZ10/LZ11, prefix comparisons and final digest
comparison. No transform or digest result is stubbed. This is an offline native
execution proof, not an activated service or authenticated resource envelope.

The private Japanese HAPJ v512 executable remains pinned to SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
Original files remain unchanged and outside Git. Only synthetic keys, IVs,
ciphertext, digests, prefixes and explicitly supplied padding are used.

## Actual composition

The verifier invokes the original hash-descriptor getter and application hash,
cipher and decoder initializers before entering dispatcher `0x8007F3F0`.
Each configured body callback executes this original sequence:

1. Hash the actual rounded wire ciphertext span.
2. Decrypt that span into the intermediate buffer.
3. Store the actual cipher application return as its intermediate count.
4. Decode that many intermediate bytes through the actual streaming decoder.
5. Accumulate its actual application return and run the original prefix checks.

It checks the call order and actual arguments at these entries, exact decoded
bytes after each callback, flags, decoded-size counter and SDK descriptor reset.
The actual cipher output, return, write-address span, untouched intermediate
tail and CBC chain are compared against independent AES-CBC. The decoder's
remaining/cached counts, header/flag/reference state and output are compared
against the independent streaming projection. The finalizer executes original
HMAC finalization and the original digest string comparison.
Decoder stream state and CBC chaining state are compared after each event;
hash verification compares the actual final digest and comparison result, not
every internal SHA1/HMAC context word after each update.

The actual twenty-byte digest must equal standard HMAC-SHA1 over the supplied
ciphertext chunks. The native comparison result and actual count of compared
digest bytes must separately equal the original-wrapper projection. They are
not inferred only from a response flag that could already have been set.

An explicit test gives the correct digest's first NUL byte followed by a
different later byte: the original comparison stops at the equal NUL and
reports a match, while the full binary digest comparison is false. This known
native behavior is retained and reported, never described as authentication.
The original binary wire/cache prefix comparisons also execute unchanged.

## Explicit supported geometry

This first composed verifier requires:

- An explicit twenty-byte HMAC key and twenty supplied expected-digest bytes.
- An AES key of 16/24/32 bytes and an explicit sixteen-byte IV.
- One to four nonempty complete-block ciphertext chunks, at most 1,024 bytes
  each, and an explicit logical received size for each chunk.
- Actual supplied ciphertext backing for every byte the callback rounds up to
  a block boundary. Logical receive size and supplied backing remain distinct.
- At most 64 combined wire-prefix/digest bytes, within the original configured
  buffer geometry; cached prefixes remain bounded to 64 bytes.
- Successful synthetic IOS acquisition and cipher output extent equal to its
  application count. The actual equality is verified after every cipher call.
- Decoder application counts equal to actual new writes and no negative SDK
  decoder result. Total decoded backing remains bounded to 4,096 bytes.

The verifier never encrypts, pads, unpads, guesses missing bytes or substitutes
decrypted output. Tests create their explicitly labelled synthetic ciphertext
and padding before invoking it. A disabled decoder copies the actual decrypted
bytes; it does not strip a compression header or reinterpret those bytes.

Cipher acquisition failure, non-block cipher rejection, decoder error after
writes, capped-output count mismatch and malformed counter-underflow composition
are **outside this composed domain**. Their standalone behavior remains
verified in [cipher.md](cipher.md) and [compression.md](compression.md). Such
branches can retain old intermediate bytes independently of returned count;
this tool does not replace that backing with empty or zero-filled input.
Future failure-path composition must supply exact persistent backing and count
separately. The raw `0x80` callback branch is also outside this tool's domain.

## Native boundaries and evidence

Only SDK application-object lookup and IOS open/close success are synthetic
runtime boundaries. Original acquisition/release helpers, hash/cipher/decoder
initializers, software cores, callbacks, copies and comparisons execute.
There is no network operation, real IOS/device access, original secret-resource
loading or emulator/profile modification.

Memory hooks admit supplied objects, initialized contexts, bounded stack,
specific original public-algorithm tables/descriptors, the original SHA1 `0x80`
finalization byte and its checked loader-zero padding span. No unrelated
original resource or credential spans are admitted. Cipher intermediate reads
require actually written backing; LZ backreferences require actual decoded
history. Every event verifies exact output write addresses, bytes and untouched
tail, and immutable inputs and all outer guards remain intact.
The host-side final digest snapshot additionally requires its entire twenty-byte
span inside the supplied mutable hash-worker context or bounded stack; its
pointer cannot select arbitrary original or mapped memory.

Seven focused tests passed, covering 28 complete pipelines, 89 dispatcher calls,
132 original AES blocks and 138 SHA1 compression calls. Tests cover all three AES
key sizes, both LZ formats, one/two/three body events, logical receive lengths
shorter than supplied rounded backing, mismatch/latch branches, incomplete cache
prefix finalization, disabled decompression and the equal-NUL digest behavior.
See the [metadata-only report](../../research/cmoc_transform_pipeline_validation_20261107.json).

Run `python -m unittest tests.test_cmoc_transform_pipeline -v`. Native tests
require the private pinned executable and optional crypto, Unicorn and Capstone
packages; absence produces an explicit skip. The exact-source guard test needs
no optional packages. No actual Wii backup, NAND or device credentials are used.

Real resource acquisition and `.ces` envelope framing, ownership/identity/trust
provenance, SDK/network/cache lifecycle, failure-path persistent backing,
complete original startup and native UI/hardware validation remain unfinished.
