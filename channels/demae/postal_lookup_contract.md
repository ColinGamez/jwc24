# Processed postal lookup contract

Verified October 22, 2026 against HCCJ v2 function `0x8002EBCC` in the private
executable with SHA-256
`640982489f7cc7924da52602130dcf3f100054dd8f907a467759356f1659fbfc`.

`jwc24.demae.lookup_processed_postal` accepts processed records and a postcode
integer from 0 through 9,999,999. It is an offline inspection helper. The
production postal route and public Japan Post lookup are unchanged.

Records contain a big-endian 32-bit postcode followed by three terminated
UTF-16BE strings. Source order matters:

- The first exact match returns `exact`, even if an alternative came first.
- Without an exact match, the last record matching `postcode // 100 * 100`
  returns `alternative`. Queries below 100 therefore use zero as the fallback.
- With neither match, the result is `not_found` with no record.

The helper validates the entire buffer, including data after an exact match,
and caps processed input at 256 KiB. Selected strings may contain at most
31, 31 and 63 UTF-16 code units. These are conservative safeguards: the native
consumer returns early on an exact match and truncates oversized selected text.
The helper rejects malformed framing, malformed UTF-16 and selected text that
would be truncated. It does not collapse duplicate records or claim delivery
eligibility from a postal match.

`tools.verify_demae_postal_lookup.verify` loads the fingerprinted executable
into Unicorn and executes the original lookup routine. Only memcpy and memset
are mocked. Synthetic fixtures compare return status, selected code, all three
zero-padded output fields, and unchanged output on a miss. Cases cover both
match orders, duplicate exact/fallback rows, zero, missing records, Japanese
text and surrogate pairs. The native fixture test skips when private source
software is unavailable; the independent helper tests remain runnable.

This verifies processed-record selection, not WC24 delivery, encrypted
download acceptance, the address save, native UI operation or restaurant
coverage. No historical address dataset, device identifier, real save or key
is needed for these checks.

## Application header gate follow-up (October 23, 2026)

`tools.verify_demae_postal_header.verify` executes the original `0x8002E954`
header gate without mocking its instructions. Its 266 synthetic cases cover
all 256 offset-byte values, declared lengths zero through four, each incorrect
magic byte, and a longer valid buffer. Successful calls write one big-endian
word containing byte 4; rejected calls preserve the output. Guard bytes around
that word remain unchanged.

The gate checks a minimum length of five and the four `zpcd` bytes only. It
accepts offset zero and offsets beyond the supplied buffer. This is evidence
about this gate, not proof that later processing accepts those inputs. The
independent decoder deliberately keeps its stricter offset bounds.

An additional synthetic integration test encrypts both LZ10 and LZ11 processed
fixtures with an explicitly supplied test key/IV, decodes them, then checks
exact, alternative and missing lookup results. This connects the independent
offline components; it does not execute the native download callback or prove
transport authentication, real-Wii acceptance or UI behavior.

## Native decrypt-and-strip callback (October 23, 2026)

`tools.verify_demae_postal_callback.verify` now executes the original callback
at `0x8002D370`, including native AES initialization/decryption and the header
gate, against independently encrypted synthetic fixtures. Filesystem, heap,
lock services and debug output are mocked; original keys are not used.

The callback writes the decrypted bytes after the header offset to an
intermediate file. Synthetic LZ10 and LZ11 fixtures confirm byte-for-byte output
including trailing block-alignment padding. This callback does **not** perform
decompression; that is a later processing stage.

Failure checks cover ciphertext shorter than a block, incomplete blocks,
input exceeding the configured capacity, bad header magic and failures of
either allocation. Observed native return values are `0x17` for size rejection,
`0x18` for allocation failure and `0x1B` for header rejection. These internal
return values are not user-facing Wii error codes. The harness verifies that
allocated buffers are freed, opened handles closed and locks released on these
paths. Unsafe header offsets are excluded before emulation.

This narrows the unverified boundary to subsequent decompression/storage and
the surrounding download transport. Mocked file I/O does not establish real
filesystem behavior, signed-envelope acceptance, authenticity or UI operation.

## Native bounded decompressor (October 23, 2026)

`tools.verify_demae_postal_lz.verify` executes the native size reader at
`0x80160AA0` and bounded LZ consumer at `0x80160D80` without mocking either.
Synthetic output is compared byte-for-byte, with guards before and after the
declared output buffer. This verifies the routines called by the filesystem
wrapper at `0x8002D044`; that wrapper itself is not yet executed by this harness.

Passing fixtures cover LZ10/LZ11 literals, overlapping distance-one copies,
both extended LZ11 copy-length forms, extended output-size headers and trailing
padding through 32 bytes. Negative fixtures cover unsupported compression,
truncated literals/tokens, references before the output buffer and excessive
trailing bytes. Native routine statuses observed are `-1` for unsupported
type, `-2` for truncation, `-3` for more than 32 unused trailing bytes and `-4`
for the tested invalid references. These are routine statuses, not displayed
channel error codes. They do not describe every possible malformed input.

The independent Python LZ11 decoder now explicitly checks every copy-token
length before reading, consistently raising `ValueError` for truncation.
This also keeps truncated input inside the postal decoder's format-error path.
The independent decoder's padding policy remains permissive; native tests do
not establish that all inputs accepted by Python will pass the Wii consumer.

Remaining acceptance work includes the filesystem wrapper's failure paths,
the complete native pipeline and actual WC24 delivery/authentication. No live
route or emulator profile is changed by these offline checks.
