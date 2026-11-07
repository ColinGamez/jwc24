# Nintendo Channel SDK event-four state producer

November 7, 2026. `jwc24.nintendo_callback` connects the original event-four
state producer to the existing [manager relay](manager_callback.md) and HTTP
consumer. It projects explicitly supplied SDK getter observations and ticks;
it implements no network transport and selects no genuine catalog or media.

The unchanged private Japanese HATJ v1792 DOL is 4,194,944 bytes, SHA-256
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
The [validation report](../../research/nintendo_callback_validation_20261107.json)
contains numeric regions, hashes and aggregate comparisons, with no original
software, SDK resources, device identifiers, request data or catalog bytes.

## Complete selected original chain

| Original boundary | Verified selected behavior |
| --- | --- |
| `0x80027E40..0x80027E90` | Preserve the SDK callback's handle/event/descriptor, obtain inner context through getter `0x802A9EA0`, dispatch, then return zero. |
| `0x80027E90..0x80027ECC` | Original numeric dispatch selects event four. Other event values have separate unfinished paths. |
| `0x80028068..0x80028158` | Complete event-four branch: shared-word transition, conditional timing calculation, header clearing, conditional SDK metadata updates and retained inner callback invocation. |
| `0x803405BC` | Original signed 64-bit division executes, including negative/high-bit and wrap cases. |
| `0x800282B0` | Original header helper clears four first bytes, retaining other storage. |
| `0x80026AE0`, `0x80026B10` | Actual retained callback thunk and complete manager relay construct the final six-word frame. |
| `0x800287C0..0x80028914` | Actual loader-context wrapper and complete callback body apply their phase/error/retry behavior. |

This is original source execution in bounded synthetic RAM. It is neither a
live Dolphin run nor proof of the complete original worker or SDK lifecycle.
Only SDK metadata getters, tick and callback timer reset/start boundaries are
intercepted; selected application wrappers and arithmetic helpers are not.

## Inner metadata and conditional observations

The SDK wrapper's supplied handle and the handle retained inside the object are
separate inputs. The context getter receives the wrapper handle. Later metadata
getters receive the retained inner handle. Exact outgoing arguments are checked;
the adapter does not infer that these handles denote the same live SDK request.

Shared word two becomes three and enters the timing calculation; four becomes
five without it. Other words remain unchanged. The event then clears header
first bytes and assigns the SDK error getter's result to inner `+0x118`.
Only error value 14 obtains another getter result for inner `+0x11C`; otherwise
the old detail word remains untouched.

The supplied SDK request-state getter is compared **signed** against four.
Only a value at least four calls the response getter and updates inner `+0x120`.
Lower or negative values retain the previous word. [Request setup](request_setup.md)
initializes that word to 200, so retained numeric 200 is not evidence that an
HTTP response was observed or accepted. `response_getter_called` and
`prior_response_word_retained` preserve this difference explicitly. Even an
invoked getter is a supplied SDK observation, not independently authenticated
network history.

The final retained callback receives pointer and length zero. Header clearing
does not destroy the handle, clear every opaque word, or complete its lifetime.
The existing relay independently converts current inner/shared words to its
callback frame. No source bytes are copied during this event-four callback.
Previously retained loader bytes and skipped-input history remain intact.

## Timing arithmetic and result distinctions

With initial shared word two, the original subtracts the stored tick pair from
the supplied current tick pair modulo `2**64`, then interprets that difference
as signed. It divides by the explicit frequency word shifted right two using
signed division toward zero. The subsequent test examines only the quotient's
low 32 bits. A zero low word stores zero; otherwise the inner counter is divided
by that low word using unsigned division and stored at inner `+0x100`.

This preserves the original negative/high-bit and low-word behavior. It does
not rewrite the result as a reliable elapsed-time, throughput, timeout or source
freshness measurement. Frequency and ticks are supplied numeric machine-state
observations. A frequency below four rejects locally to avoid an undefined
division; this is not an original validation check.

The SDK callback wrapper returns zero even when the downstream loader enters
an error or retry state. Its return, the relay's derived error and the existing
poll normalizer's result stay distinct. A public composition case preserves
wrapper zero, derived error `-107`, raw poll `-109` and normalized result `-107`.
The new native verifier executes the producer/relay/consumer; that additional
poll assertion uses the separately verified existing projection, without
claiming the poll ran inside this new native slice.

## Explicit context and safety subset

Inputs require the exact opaque request snapshot, explicit loader snapshot and
identity, event word, SDK handle, descriptor bytes, frequency, ordered SDK getter
returns and tick pairs. The two snapshots must agree on their shared retry word;
after a downstream retry transition the returned request snapshot records the
same updated retry word as the loader.

The context getter must identify the supplied inner object. Missing inner
callback, zero inner context, missing outer callback and zero loader context
remain four separate paths. A different nonzero callback/context cannot be
silently redirected to the supplied manager/loader. These pointer restrictions
are local bounds on the reviewed original chain, not recovered native rejection
rules for every possible callback. The original SDK wrapper itself does not
check a null context before its inner dispatch.

Only event four is implemented here; other values explicitly reject as
unfinished behavior. The descriptor is inert, bounded to 256 supplied bytes and
unchanged; this selected event does not read its fields. Getter outcomes are
bounded to five and tick outcomes to one. Missing, additional, unsupported or
out-of-order outcomes reject. Callers cannot obtain implicit success defaults.
Opaque storage, descriptors, words and returned values are excluded from default
representations and metadata. Getter boundaries return without additional RAM
side effects or recursive callbacks in this selected comparison; real SDK
concurrency remains unproved.

## Verification and remaining requirements

```powershell
.venv/Scripts/python.exe -m unittest tests.test_nintendo_callback
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_nintendo*.py'
```

The 345 original comparisons check complete source execution, conditional reads,
all four callback/context absences, separate handles, exact frame/runtime context,
retry coupling, preserved response/detail words, signed request-state boundaries,
response/error mappings, and tick zero/wrap/negative/high/low-word cases. Code,
memory reads/writes and instruction counts are bounded. Host-side inspections
share the same read bounds. Exact descriptor/opaque storage, loader bytes/state,
original callback return, metadata call order/arguments and guards are checked.
Native tests skip honestly without the pinned private original or optional
Capstone/Unicorn. Public stories or production catalog fixtures are not created.
All eleven targeted tests and 106 Nintendo regression tests passed. An independent
empty-working-directory run passed ten public tests and skipped the private-input
native class.

Events one/two/three, chunk descriptor ownership, the SDK's actual context and
metadata production, request/response parsing, concurrent worker lifetime,
cancellation and late callbacks, trust/freshness, genuine catalog/media,
reviews/bookmarks and original UI remain unfinished. No getter projection proves
an actual HTTP response, authentication or channel completion. No original file,
resource, credential, profile or console backup is changed or activated.
