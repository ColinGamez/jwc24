# Goldmine WC24 and postal-tool follow-up

October 22, 2026. The collection index led to **13 verified members** of the
local apps archive: three PDFs and ten source/header encounters, representing
12 unique payload hashes. Two face-library headers are identical copies.
Original files were read only; no original tool, installer or build was run.

## Recovered references

| Reference | Scope | Evidence level |
| --- | --- | --- |
| WiiConnect24 programming guidelines v0.25 | 30 pages, April 4, 2008 | Exact archive member recovered, text indexed, selected tables visually checked |
| WiiConnect24 message list v0.25 | 3 pages, April 4, 2008 | Exact member recovered; error table visually checked |
| Postal-file tool manual | 9 pages | Exact member recovered; update workflow reviewed and visually checked |
| Postal converter/checker sources and headers | Seven encounters | Selected format, capacity and lookup sections reviewed privately |
| Backup-disc WC24 administrative header | One encounter | Administrative/development context identified; no operations executed |
| Face-library WC24 headers | Two encounters, one distinct payload | Metadata/source reference only; not a complete core WC24 SDK |

This is **42 additional PDF pages** beyond the initial 19-PDF review. The
networking limitation in the early 2006 SDK still applies to that release;
these later materials provide a separate, more relevant WC24 reference set.

Private originals, extracted PDF text, selected-page renders, exact member
paths and SHA-256 provenance are under `private/goldmine_wc24/`. No original
source, documentation, executable, message wording or cryptographic material
is published with this note. Key/credential members were not extracted.

## What changes our investigation priorities

### Native readiness is separate from individual download success

Guideline pages 13-17 distinguish library-open errors, transient busy states,
readiness checks and individual task errors. They recommend bounded retries
for temporary library contention and separate checks for the task whose data
will be read. They also warn that successful API checks alone do not prove
that a payload is the newest version; internal sequence/timestamp evidence
can still be needed. Page 29 discusses allowing scheduler operation during
application execution.

For JWC24, this reinforces checking the whole path: task registration,
scheduler state, individual result, VFF destination, payload validation and
native UI use. HTTP 200, a listening server or an enabled global WC24 setting
alone cannot establish restoration of a channel.

### Mail limits have distinct scopes

Pages 18-20 distinguish permitted data types, pre-MIME application-data send
budgets, optional automatic messaging and non-guaranteed delivery. Pages
24-26 separately discuss automatic posting to one's own Message Board,
manual posting and notification behavior. Those are distinct operations.

The historical per-launch application budgets must not be substituted for
`jwc24/mail.py`'s per-message transport cap. Nor should the older guide's
two-task/application and combined-download budget be imposed on the shared
120-entry task table or every special Nintendo channel. These are versioned
application guidelines, not proof of universal IOS wire-format limits.

Queueing or handing a message to the transport is not proof of receipt,
display or final provider ordering. Demae's explicit phone confirmation and
durable notice queue remain separate from verified native notice delivery.

### Errors need context, not guesses

The message list gives representative mappings for library/file failures,
disabled settings, network/service problems, outgoing-mail capacity and
download-task errors. These are diagnostic categories rather than unique
root causes. The same general family can occur under different API contexts.
Some error messages also depend on client version and region.

The new read-only helper can be used without touching a profile:

```powershell
python tools/explain_wc24_error.py 107305
python tools/explain_wc24_error.py 336195
```

`107305` is categorized as a reference download-task error; the helper still
requires inspection of the task result and payload. `336195` stays unknown:
this WC24 list does not establish a Demae-specific meaning for it. The helper
does not reproduce original UI text, diagnose restaurants being unavailable,
retry requests, change settings, delete data or synthesize channel success.

### Postal framing now has corroborating production-tool evidence

The manual describes a Japan Post CSV conversion and a separate on-device
update checker. Reviewed converter/checker sections corroborate the processed
format already recovered independently from HCCJ: a big-endian postal-code
integer followed by terminated UTF-16BE prefecture, municipality and town
strings. The checker has 32/32/64-code-unit output buffers and a 256 KiB
decompressed-data budget. Its default grouping step is ten leading-three-digit
units, consistent with the existing bucket calculation.

The checker also has a rounded-postcode alternative-search path that continues
looking for an exact match. That is a follow-up lead for the particular HCCJ
consumer, not a reason to silently discard ambiguous Japan Post records or
change the public geographic directory's all-matches behavior.

Application-level AES, `zpcd` and compression are distinct from the outer WC24
download envelope. These references do not establish retail signature trust,
native acceptance of newly generated data, or Demae delivery eligibility.
No original converter was executed and no source data was served to a Wii.

### Administrative headers are not retail service implementations

The recovered administrative header belongs to backup/development tooling
and includes facilities outside the ordinary public application API. It is
a lead for provenance and interoperability research, not permission to reset
mailboxes, regenerate identifiers, alter friend data or change a live NAND.
The face-library headers similarly cover one integration area, not the whole
WC24 transport or Message Board implementation.

## Channel/service work this supports

| Area | Next evidence-driven work |
| --- | --- |
| Shared WC24 / TV no Tomo / Forecast / News | Capture readiness, per-task results, freshness and native consumption separately; preserve observed channel-specific registrations |
| Wii Mail | Compare queue, mailbox capacity and native receipt/display semantics; distinguish transport limits from per-session application budgets |
| Demae address helper | Exact/alternative selection now matches the stock native consumer on synthetic checks; download acceptance and live integration remain open |
| Demae ordering | Continue verified variant/menu/item/basket contracts; postal tools do not solve ordering APIs |
| Wii no Ma | Keep interaction receipts, actual media codec and native notification delivery as separate verification targets |
| CMOC / Nintendo Channel / Body Check | Recover each client's payload and prerequisites; shared WC24 guidance does not substitute for those formats |

## Private index enrichment and checks

The local index now links the 13 recovered members to verified private files,
hashes and exact archive origins in `verified_archive_evidence`. Their texts
are searchable, bringing the selected-document total from 821 to **834**.
Baseline physical-tree and imported-catalog counts remain the original snapshot;
this is selective verified recovery, not a new full archive audit.

All selected members were found and their saved bytes matched the recorded
hashes. SQLite integrity and enriched text searches were checked. Five focused
tests cover the new diagnostic categories, families, leading-zero handling,
malformed inputs, unknown channel codes and CLI output. No production server,
account, task, emulator profile, order or mail queue was changed.

## Follow-up: native postal selection verified

The recovered checker behavior was compared with HCCJ v2's actual postal
consumer at `0x8002EBCC`. Exact matches select the first matching row;
without one, the last rounded-hundred fallback wins. Synthetic execution
compared status, selected postcode and every output text field, including
Japanese and surrogate-pair text. Missing records preserve native output.
The independent bounded helper intentionally validates malformed trailing
data that the native early-return path might not visit. See the
[postal lookup contract](../channels/demae/postal_lookup_contract.md) for
limits, source fingerprint and verification scope. This does not change
the manual-selection fallback or prove encrypted download acceptance.

On October 23, the original `zpcd` header gate at `0x8002E954` was also
executed against 266 synthetic cases. It accepts every offset byte after
checking the magic and minimum length; buffer-offset validation remains a
deliberate safeguard in our independent decoder. Synthetic LZ10/LZ11 encrypted
fixtures now exercise that decoder through exact/fallback/missing record
selection. These checks do not establish native download callback acceptance.

A further harness now executes the original decrypt-and-strip callback at
`0x8002D370` with synthetic file I/O, heap and lock services. Native AES and
the native header gate produce the expected compressed intermediate bytes,
including trailing block padding, for synthetic LZ10 and LZ11 inputs. Size,
header and allocation failures release their resources in the tested paths.
Native decompression and real download acceptance remain separate open checks;
the full scope is recorded in the postal lookup contract linked above.

The native bounded decompressor (`0x80160D80`) and size reader (`0x80160AA0`)
now also pass guarded synthetic comparisons. Coverage includes literal and
overlapping-copy LZ10/LZ11 data, long LZ11 tokens, extended size headers,
truncation, invalid references and trailing padding. The native consumer
rejects more than 32 unused trailing bytes. An independent Python decoder fix
makes all truncated LZ11 token forms raise `ValueError` consistently. The
filesystem decompression wrapper and full native download path remain open.

Subsequent synthetic execution now covers that decompression wrapper at
`0x8002D044`, including file open/read/write/close and allocation failures.
The original wrapper, size reader and decoder execute with only file/heap
services mocked. Expected output, allocation guards and cleanup pass for the
tested cases. A destination-close error follows an already completed write;
it does not imply that the output was rolled back. Complete native request
orchestration, real storage and WC24 delivery/authentication remain open.

The original task-file processing orchestrator at `0x8002E7C8` now also passes
a combined synthetic execution test. Actual native intermediate writes feed
the next native stage's reads in one emulated process, from ciphertext through
address-result publication. Both compression types, exact/fallback/missing
results, duplicate rows, UTF-16 capacities and a cancellation checkpoint are
covered. This closes the separate-stage-only gap for task-file processing;
request registration, WC24 delivery/authentication, real storage and UI behavior
remain unverified. See the postal lookup contract for precise mocked services.

Combined fault injection now covers read/write errors at decrypt/unpack and the
final processed-file read. Tested failures retain their file-service diagnostic,
stop later stages and clean up. Processing by itself retains a preexisting ready
result, but native execution of the accepted-request creator (`0x8002E34C`)
confirms that it resets that result before submitting the callback. Formatting,
manager status and queue submission are mocked; real registration and scheduling
remain unverified. This separates caller reset behavior from worker processing.

The request harness subsequently replaced mocked queue preparation/status with
the original `0x8002DA48` and `0x8002DC08` routines. It verifies numeric bucket
arguments at all 200 endpoints of the full seven-digit range, synthetic crypto
parameter/context transfer and pending state before mocked thread dispatch.
Same-bucket reuse, changed-bucket refresh and forced refresh follow the expected
native branches. Formatting still emits synthetic labels: original URL/path
construction, real dispatch and WC24 task registration are not established.

On October 24, the request harness also began executing the original message
queue initialization/send/receive routines. The request descriptor pointer
survives a native queue round trip; empty reads preserve output and full sends
preserve FIFO contents across wraparound. Queue storage guards remain intact.
Only interrupt/wake-up services are mocked at that boundary. Blocking/races,
actual worker scheduling and WC24 delivery remain unverified.

A controlled native worker iteration now also passes: the original worker
receives one queued descriptor and invokes its stored processing callback,
which executes the combined postal pipeline. Synthetic successful task
completion is supplied at the download-routine boundary. Processing failures
and cancellation reach the manager's callback-status field; the observer then
requests a stop and the native loop exits. Real thread creation/scheduling,
task completion, registration and network delivery remain unverified.

Worker failure tests now inject internal task statuses `0x28`/`0x29`/`0x2A`.
Native code skips postal processing, replaces seeded diagnostics and clears
synthetic request buffers, crypto parameters and callback/context fields. The
request-resource cleanup service and SDK error getter remain mocked. These
numeric internal statuses do not establish meanings for displayed channel
errors or actual download root causes. A previous address result is retained
until the caller's separately verified reset runs.
