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

## Native decompression file wrapper (October 23, 2026)

`tools.verify_demae_postal_unpack.verify` now executes the wrapper at
`0x8002D044`, its size reader and bounded decompressor. Only filesystem and
heap calls are mocked. The stock call configuration is used: no post-decode
transform and no source deletion. Original software is required privately;
native tests skip when it is absent, and a fingerprint mismatch is rejected.

Synthetic LZ10/LZ11 data, with and without trailing padding, produces the exact
expected output file bytes. Allocation guards remain unchanged. Injected faults
cover either allocation, source/destination opening, reading, short reads,
writing and either close. The harness checks that all allocated buffers are
freed, handles are closed and the mount is released on the tested paths.
Close failures are injected once; cleanup's retry succeeds. Persistent close
failures and actual filesystem behavior are not covered.

Input shorter than eight bytes, input exceeding the configured capacity and
declared output exceeding that capacity return `0x17`. Allocation failure
returns `0x18`; native decoder rejection maps to `0x1C`. The tested file-service
error value 5 maps to `0x15`, while failed opens and short reads return `0x14`.
These are internal return values, not displayed Wii error codes.

The destination-close failure occurs after the output bytes have been written.
A returned error therefore does not guarantee that output is absent or rolled
back. Any future live recovery logic must account for that distinction. No
transactional storage behavior is established by mocked I/O.

This completes separate synthetic execution checks for decrypt/strip, unpack
and record lookup. The complete native request orchestration, real storage,
WC24 envelope authentication/delivery and UI behavior remain unverified.

## Combined native processing sequence (October 23, 2026)

`tools.verify_demae_postal_pipeline.verify` now enters the original processing
orchestrator at `0x8002E7C8`. One emulated process executes the native decrypt/
strip callback, unpack wrapper, final processed-file reader and postal lookup.
The harness does not replace those routines with Python implementations. A
synthetic in-memory filesystem carries each stage's actual written bytes into
the next stage's reads. Heap, lock, filesystem, initialization and libc services
are mocked; no real WC24 task is registered or downloaded.

An independent decoder and lookup helper provide expected results. The harness
compares the intermediate compressed bytes including padding, final processed
file, native lookup status, all three address fields and result-readiness flag.
Both LZ10 and LZ11 pass exact, alternative and missing-address cases. Additional
fixtures cover duplicate row selection, zero postcodes and maximum UTF-16 field
capacities with surrogate pairs. Allocation guards and resource cleanup pass.

With the synthetic cancellation flag set at entry, this mode still decrypts
and writes its intermediate file before returning at the next checkpoint.
The test verifies return value 1, no published address result and cleanup;
it does not simulate cancellation arriving asynchronously during a service call.

This verifies native **task-file processing orchestration**, extending the
separate stage checks above. It does not establish request registration,
scheduler/download operation, signed-envelope acceptance, real storage behavior,
or on-screen address entry. Those remain the boundary before live integration.

## Combined failure propagation and request reset (October 23, 2026)

The combined harness now injects file-service error 5 at decrypt read/write,
unpack read/write and final processed-file read. Both compression types are
covered. Each tested failure returns internal status `0x15`, retains the
service diagnostic 5 and stops before later stages. Stage counts, file-write/
delete counts, cleanup and allocation guards are checked. Fresh result contexts
remain unpublished. These internal statuses are not displayed Wii error codes.

When the harness seeds an existing ready result, processing failure or
cancellation leaves that flag and its old address fields intact. A separate
native execution check resolves the normal caller boundary: the accepted-request
creator at `0x8002E34C` clears readiness, sets lookup status 2 and clears the
address fields **before** submitting the processing callback/context. After
submission it retains the new requested postcode. Thus the processing routine
alone must not be treated as a result-reset API.

`verify_request_reset` tests the original accepted-request path with formatting,
manager lookup/status and queue submission mocked. It verifies the reset at
submission for zero, a representative postcode and the maximum postcode. This
does not execute a real queue, thread scheduler or WC24 task registration, and
does not prove behavior for every rejected or concurrently issued request.

## Native queue preparation and bucket boundaries (October 23, 2026)

The request-reset harness now executes queue preparation at `0x8002DA48` and
the native status reader at `0x8002DC08`, extending the earlier mocked-queue
check. Only manager lookup, formatting/string helpers, request cleanup,
diagnostics and thread dispatch are mocked in this part of the harness.

The native creator's numeric formatting argument matches the independent stock
bucket calculation at both endpoints of all 100 postcode buckets, covering
0 through 9,999,999. The formatting helper emits synthetic labels, so this
check does not verify the original URL or path formatting.

Queue preparation retains the processing callback and result-context pointer,
copies synthetic key/IV parameters and prepares pending state 2 before the
mocked dispatch. Its work-capacity slot receives the caller's 256 KiB capacity
plus 32 KiB (`0x48000`). This slot arithmetic does not change the independent
256 KiB processed-data limit or prove a transport allocation policy.

An existing identical bucket label without force-update selects the native
reuse path and clears the refresh flag. A missing/different label or a forced
update invokes the mocked prior-request cleanup and sets that flag. These
are preparation decisions; they do not prove that cached files exist, are
fresh/authentic, or that a scheduler actually performs a new download.

Real dispatch, concurrent request behavior, task registration, WC24 delivery,
storage and UI acceptance remain unverified.

## Native message handoff (October 24, 2026)

The request harness now executes the send wrapper at `0x8002C9F8` and receive
wrapper at `0x8002CA28`, including the underlying queue initialization, send
and receive routines (`0x8013DEDC`, `0x8013DF3C`, `0x8013E004`). The earlier
mocked dispatch boundary is replaced by an observer that allows native
instructions to continue. Interrupt disable/restore and thread wake-up services
remain mocked; no real thread is started or blocked.

Native initialization prepares a two-slot synthetic ring buffer. Request
preparation enqueues its descriptor pointer, which the original receive code
retrieves unchanged. The descriptor retains its processing callback/context.
An empty nonblocking receive returns zero without changing the output pointer.
Further synthetic messages verify FIFO order across ring wraparound and that a
full nonblocking send returns zero without replacing the queued messages.
Queue occupancy returns to zero, and buffer guards remain unchanged.

The production-shaped request send uses flag 1, but the synthetic queue has
space, so this does not exercise waiting under that flag. Capacity/empty cases
use flag zero. Blocking, wake-up races, concurrent threads and actual worker
execution after receipt are not covered. This verifies message transport
within the emulated queue, not WC24 network delivery or scheduler operation.

## Native worker consumption and callback (October 24, 2026)

The combined processing harness now has a `worker=True` mode. It prepares a
synthetic manager/request, initializes the native queue and enqueues one request
descriptor using the original send wrapper. Instead of directly calling the
processing orchestrator, it manually enters worker `0x8002DE70`. The worker's
native receive, descriptor check and request processor (`0x8002DF34`) invoke
the processing callback through the stored function pointer and result context.
The native queue/request creator is tested separately; this experiment seeds
the manager directly rather than running registration and creation end to end.

The task-download routine at `0x8002CC04` is mocked to report success with the
synthetic encrypted task file already present. The worker then executes the
native decrypt/strip, unpack, final read and lookup sequence. Both compression
types pass exact/fallback/missing results. Injected processing file failures
and cancellation propagate into the manager's stored callback status without
publishing a fresh address result. Allocation and queue guards remain intact.

After the single request returns to the loop, a harness observer sets its stop
flag. The worker executes its own stop branch, records state 3 and returns zero;
that return is distinct from the callback status stored at manager offset
`0x760`. Queue occupancy must be zero, and all processing resources must be
released. Unexpected idle sleeping fails the experiment rather than invoking
real kernel services.

This verifies a controlled native worker iteration, not OS thread creation,
concurrent scheduling, actual task completion or network delivery. Kernel
synchronization and storage remain mocked. The deliberately supplied task
success does not establish download-entry registration or authentication.

## Worker task-failure boundary (October 24, 2026)

The task-result mock now also supplies internal statuses `0x28`, `0x29` and
`0x2A`, with synthetic detail zero or -100. The native worker and diagnostic
mapper execute unchanged. These are injected internal values, not observed
real download failures or user-facing Wii error codes.

All tested failures skip the processing callback: no decrypt/unpack/file-read
stage starts, the encrypted fixture remains untouched, and no new address is
published. The worker stores the task status, invokes a mocked request-resource
cleanup service, then natively clears the request/URL buffers, synthetic crypto
parameters, mount/file labels, capacity, callback and context fields. It restores
the request-mode byte before returning to the controlled stop checkpoint.
This checks native field reset; actual cleanup of registered WC24 resources is
not executed by the mocked cleanup service.

The diagnostic mapper replaces seeded prior diagnostics. Detail zero clears
the category and SDK-error slots. For the tested detail -100, status `0x29`
selects category 11; the other two statuses select category 10. A mocked SDK
error getter supplies -12345, which is retained in the diagnostic slot. These
numeric branches do not establish semantic category names or specific network
root causes. Prior address results remain unchanged until the caller resets
them, as in the earlier processing-failure tests.

Success and failure of real task registration/download, genuine SDK error
sources, thread scheduling and UI error presentation remain unverified.
