# Nintendo Channel manager callback relay

November 7, 2026. The [existing HTTP projection](http_lifecycle.md) previously
required the callback's six supplied words. `jwc24.nintendo_manager` now derives
that frame from the actual upstream manager's supplied state and composes it
with the existing callback buffer/error/retry projection. It adds no live
transport, catalog data, replacement UI or accepted submission response.

The unchanged private Japanese HATJ v1792 DOL is 4,194,944 bytes, SHA-256
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
The [validation report](../../research/nintendo_manager_validation_20261107.json)
contains numeric regions, checksums and aggregate comparisons. Original code,
resources, request data, catalog records and device identities remain private.

## Actual upstream-to-consumer connection

| Original boundary | Verified connection |
| --- | --- |
| `0x80028490` | Existing loader restart calls manager wrapper `0x80026C80`, passing callback `0x800287C0` and the loader object as runtime context. |
| `0x80026C94..0x80026CC4` | Manager retains that callback/context at `+0x29AC/+0x29B0`, and passes its own callback thunk and manager context toward request creation. This setup is static caller evidence; request creation is not executed by the new verifier. |
| `0x80026AE0..0x80026B04` | Complete original thunk reshuffles received pointer/length/manager arguments and skips a missing manager. |
| `0x80026B10..0x80026C78` | Complete relay skips an absent configured callback, otherwise builds a six-word stack frame and invokes that callback with the actual retained runtime context. |
| `0x80027D70`, `0x80027DD0`, `0x80027E00` | Combined predicate, accepted inner-error predicate and signed response-range predicate run unchanged. |
| `0x8002B6A0`, `0x8002B780`, `0x8002BA20` | Original numeric error/detail mappings and response-detail arithmetic run unchanged. |
| `0x800287C0..0x80028914` | Actual callback wrapper skips a zero runtime context; otherwise its complete body copies fitting bytes and applies the existing state/retry branches. |
| `0x80004364` | Original byte-copy implementation executes; output bytes are compared exactly. |

The manager input retains native numeric words: shared word at
`r13-0x4E30`, manager `+0x2C20`, inner error `+0x2D28`, inner detail `+0x2D2C`,
response `+0x2D30` and flag `+0x2D38`. The extra meanings of these words are not
guessed as permission, timeout, catalog generation or authentication state.

The output frame's words are received pointer, received length, shared word,
manager `+0x2C20`, derived error and derived detail. These correspond exactly
to the existing callback's chunk and `word_08/word_0c/word_10/word_14` inputs.
The independent component retains actual supplied chunk bytes and the separate
runtime context word; it creates no pretend received pointer or network event.

## Numeric classification and precedence

Inner error zero or eight passes the first predicate. Signed response values
200 through 299 pass the second. Both predicates passing leave derived error
and detail zero. A zero derived error is only this numeric classification.

When the inner error fails, its own numeric error/detail map takes precedence
over the response value. Inner error 14 uses the separate detail map; other
values use the error map. Explicit zero entries and out-of-range zero fallback
are retained. Derived error is `-110` only when the supplied flag equals
exactly one; otherwise it is `-109`.

When only the response predicate fails:

| Response value | Derived error |
| --- | --- |
| 503 | `-107` |
| 404 | `-108` |
| 304, 401, 403, 500 | `-209` |
| Other failing values | `-110` if flag equals one, otherwise `-109` |

The derived detail is response plus 268000 modulo `2**32`. Signed predicate
checks and unsigned stored-word arithmetic remain distinct. No reason phrase,
service-specific interpretation or endpoint acceptance is invented.

## Composition preserves absence and incomplete bytes

`build_manager_frame()` distinguishes no callback invocation from a present
frame whose runtime context is zero. `apply_manager_callback()` preserves that
distinction: absent manager/callback leaves the loader untouched; zero context
executes the original wrapper's bypass. A different nonzero context is rejected
by the local composition API rather than silently redirected to the supplied
loader snapshot. This rejection is local safety policy, not a native rejection
of all other callback contexts.

Received bytes can still be copied before the callback handles an error, and
shared word two still bypasses later state/error handling after a fitting copy.
Original retry detail values reach the actual downstream retry branch only
from the supplied retry word `-1`. Existing skipped-input history survives.
An oversized chunk can reach the native non-error phase while retaining none
of that chunk; the stricter existing ListData handoff still rejects that body.

All presence predicates, context, inner words, loader state and bytes must be
explicit. Local type/size/32-bit bounds reject invalid supplied snapshots even
when a native missing-pointer branch would not read their fields. Existing
allocation/chunk bounds keep native count addition below unsigned wrap; corrupt
native counters and overflow behavior remain outside this backend subset.
Context words, raw bytes and native opaque values are excluded from default
representations and metadata.

## Verification and remaining work

```powershell
.venv/Scripts/python.exe -m unittest tests.test_nintendo_manager
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_nintendo*.py'
```

The new verifier executes the complete original thunk, relay, predicates,
numeric maps, runtime context handoff, downstream wrapper/body and copy in one
run. Only timer reset/start boundaries are intercepted, with their supplied
object pointer checked. No SDK request, callback producer, status observation,
whole asynchronous worker or timer implementation is stubbed and then claimed
as executed. Those operations are outside this selected slice.

The 311 comparisons cover mapping holes and domain edges, accepted-error and
signed-response boundaries, response precedence, flags zero/one/two, shared
phase bypass, retries already latched, empty/exact-fit/overflow chunks, missing
manager/callback, zero context, a larger copy and compressed ListData bytes.
All original code/read/write ranges and instructions are bounded; exact manager
and chunk immutability, output buffer/state, frame/context and guards are checked.
The synthetic compressed body also reaches the existing language/ListData
handoff in a public test; this is no genuine catalog or source assertion.

All 12 targeted tests and all 82 Nintendo regression tests passed. An independent
empty-working-directory run passed ten public tests and explicitly skipped the
private-input native class. Native tests also skip honestly without optional
Capstone/Unicorn or the pinned original. The SDK callback's production of these
inner words, request setup, header values, HTTP parsing, freshness, provenance,
authentication, genuine catalog/media, review/bookmark contracts and full native
UI remain unfinished. This module enables no runtime server route or channel
activation and modifies no original file, device profile or console backup.
