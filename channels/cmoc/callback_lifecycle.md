# Original response callback and finalization lifecycle

November 7, 2026. `jwc24.cmoc_callback` supplies an immutable, bounded projection
of the cached-request event-2 body callback and event-4 finalizer. It extends
[configured request setup](request_setup.md) and explains which callback flags
reach the existing [completion gate](response_gate.md). No listening service,
device identity, cryptographic envelope, profile, cached Mii or original UI is
created or changed.

The private Japanese HAPJ v512 executable remains pinned to SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
Original bytes stay outside Git and are unchanged. All execution fixtures are
synthetic memory, including arbitrary flag combinations whose reachability
from a genuine setup is not claimed.

## Full callback path

The original dispatcher `0x8007F3F0` resolves its application object and calls
`0x8007F468` for event 2 or `0x8007F720` for event 4. The complete selected
dispatcher, body callback, finalizer, flag operations, size arithmetic and
prefix comparisons execute in the native harness. The original byte comparison
routine at `0x800D9EB8` is not replaced with a comparison stub.

| Condition | Observed behavior |
| --- | --- |
| Flag `0x80` set in event 2 | Set decoded size directly from the SDK descriptor's total received count; decoded bytes already occupy the raw receive buffer |
| Flag `0x80` clear in event 2 | Compute configured input span, invoke hash/cipher/decompressor boundaries and add the decompressor's produced size to decoded size |
| Flag `0x08` absent | Compare a nonempty configured wire prefix, set `0x40` on mismatch, then latch `0x08` |
| Flag `0x04` absent and decoded size at least cached-prefix size | Compare a nonempty cached prefix, set `0x20` on mismatch, then latch `0x04` |
| Empty prefix | Latch its checked bit without a byte comparison |
| Flag `0x08` / `0x04` already set | Do not repeat the corresponding comparison when later bytes change |
| Event 4 with `0x04` absent | Force both `0x20` and `0x04`, even without a completed cached-prefix comparison |
| Event 4, `0x80` clear and hash-enable byte nonzero | Consult the explicit digest boundary; set `0x10` on a false result |
| Every selected event-4 path | Set `0x02` |

**Flag `0x20` is not a global “changed data” indicator.** Event 2 can set it
after a cached-prefix mismatch; event 4 also forces it when that check never
completed. Conversely, a checked equal prefix can leave it clear, yielding the
completion gate's zero result without a newly checked body. The local safe FD
handoff continues to require an actually passed body-header gate. A zero numeric
completion alone does not establish valid new service data or startup.

## Explicit buffers and transform boundaries

For the configured branch, the source offset is the resolved worker word
`+0xC8` plus the retained wire-prefix length. The original callback rounds
`receive_end - source_offset` upward to a multiple of sixteen before invoking
its transform boundaries. It does not itself prove that those padded bytes
were received from the network. `process_body_event()` requires the caller's
explicit backing snapshot to include the whole rounded span. Missing padding
is rejected locally; it is never generated from zeros or guessed.

The wire-prefix comparison has no received-length check at that point in the
original callback. The local API requires explicit backing for every byte that
the selected comparison reads. The digest harness similarly requires captured
backing for its supplied expected span even though the digest result is mocked.
Memory hooks reject a read outside supplied spans rather than treating mapped
synthetic RAM as evidence that unprovided bytes existed.

The independent API accepts explicit decompressor output chunks on configured
events. The native harness uses an explicitly labelled identity intermediate at
the cipher boundary, supplies each decoded output chunk at the decompressor
boundary, and supplies a boolean at final digest verification. These are
**boundary inputs, not verified cryptographic results**. Native accumulation,
prefix comparisons, latches, finalization and SDK descriptor pointer/count reset
are compared after each event. The raw `0x80` branch performs its original total
size assignment and bypasses those transform boundaries unchanged.

`CallbackState` retains exact prefix/body bytes outside representations and
metadata. Current local limits are 64-byte prefixes, resolved `+0xC8` up to 64,
wire backing up to `0x440` bytes, rounded transform input/output up to `0x400`
bytes per event and decoded body up to 4096 bytes. The native decoded allocation
is larger; these are local supported bounds. A lifecycle accepts at most eight
events in the verifier. Invalid state, incompatible raw/configured inputs,
insufficient spans and unsupported bounds reject without echoing payloads.

The earlier setup component projects capacity as `+0xC8 + wire-prefix size +
0x400`; it does not prove real resource sizes, actual SDK chunk guarantees or
that every projected capacity fits the underlying buffer. The observed wire
storage interval has `0x440` payload bytes. The new
[receive-geometry check](receive_geometry.md) independently proves that storage
and requires the combined offset to be at most 64 bytes. Actual loaded resource
sizes and SDK chunking/initialization guarantees remain unverified. This callback
component requires supplied backing to fit that interval and does not silently
change the older setup API or claim that all runtime configurations are safe.

## Verification and remaining restoration work

The [metadata-only validation report](../../research/cmoc_callback_validation_20261107.json)
records 840 native lifecycles / 1652 dispatcher calls: 812 body callbacks and 840
finalizers. There are 420 configured and 420 raw initial states. The matrix
covers every incoming flag byte with matching, mismatching and short bodies,
prefix lengths 0/1/12/64, first/middle/last mismatch positions, incremental
delivery, already-latched comparisons, finish without a body callback, and
hash-enable/result branches. These synthetic states do not establish that all
flag combinations occur in a genuine request.

Only SDK application-object resolution and configured hash update, cipher,
decompressor and final digest boundaries are intercepted. Original dispatcher,
prefix comparison, flag mutations, raw body handling and finalizer are not
stubbed. Guarded reads/writes, stack/object guards, immutable prefixes and
configuration, instruction limits, descriptor state, body bytes and flags are
checked after every event. A separate negative test proves that even a supplied
digest result cannot authorize missing expected backing in the harness.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_cmoc_callback
```

Eight public tests and two native tests pass locally; the native class skips
honestly without the pinned private executable or optional Capstone/Unicorn.
The public tests also compose the resulting flags with the existing completion
gate for unchanged, changed and truncated synthetic headers.

The [hash](hash_processing.md), [cipher](cipher.md) and
[streaming decompressor](compression.md) now have separate original-code proofs.
A subsequent [configured pipeline verifier](transform_pipeline.md) executes all
three inside the original callbacks for its explicit synthetic success domain;
this earlier callback harness retains its stated transform boundaries.

Live resource acquisition, genuine envelopes and trust, failure-path persistent
backing/count integration, transport chunking, response lifetime/error handling,
cache persistence,
authenticated identities, genuine FD records, Mii/contest/menu consumers and
original full UI remain unfinished. An explicit true digest-boundary result
and passing header correlation are not authentication evidence.
