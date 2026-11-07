# Nintendo Channel request setup and submission

November 7, 2026. `jwc24.nintendo_request` projects the actual HATJ manager's
request setup, header preparation, cleanup, stage-result conversion and inner
submission. It follows the [existing HTTP restart boundary](http_lifecycle.md)
and retains the callback/context used by the [manager relay](manager_callback.md).
It does not perform SDK calls, use device configuration or contact a service.

The unchanged private Japanese HATJ v1792 DOL is 4,194,944 bytes, SHA-256
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
The [validation report](../../research/nintendo_request_validation_20261107.json)
records code-region hashes and aggregate comparisons, without original code,
configuration values, referenced resources, device identifiers or catalog bytes.

## Actual native sequence

| Original boundary | Observed behavior |
| --- | --- |
| `0x80026C80..0x80026DD0` | Store supplied outer callback/context, create a mode-zero request, obtain initialized configuration, set headers in order, then submit. Failure copies inner `+0x124` to outer word zero before converting the stage result. |
| `0x80027A40..0x80027B60` | Require shared word one/three/five and nonzero receive capacity; clean up an existing handle; prepare inner callback/context and initial numeric words; invoke request creation and selected configuration boundaries. |
| `0x80027570..0x800275FC` | Execute the original opaque SDK configuration sequence and retry-index selection. Return values from these configuration calls are ignored by this original application wrapper. |
| `0x80025860..0x800258BC` | Read an already-initialized configuration string and copy it to a 25-byte temporary buffer. The separate device-derived generator is excluded and forbidden by the verifier. |
| `0x80027880`, `0x80027900`, `0x800277F0` | Set unconditional User-Agent, optional Referer and optional nonzero numeric Range, respectively. Range uses the original `bytes=%u-` format. |
| `0x80027B60..0x80027C10` | Check the shared word again, invoke submission, map failure and clean up; on zero return, set shared word two and store supplied tick words. |
| `0x800281A0`, `0x80028170` | Release an existing handle, reset selected inner words and clear header first bytes, preserving opaque storage elsewhere. |
| `0x800271E0`, `0x8002B6A0` | Apply original stage-result conversion and numeric error-detail mapping. |

The component requires exact supplied opaque storage for the inspected `0x2D3C`
bytes, its runtime object word, shared word and retry selector. This is a local
snapshot size, not a recovered complete object/class schema. No unknown field
is assigned a fabricated meaning. Selected writes preserve other words and
bytes, including header storage after its terminator.

The reference, receive pointer/capacity, callback/context, initialized User-Agent,
optional Referer and Range word are explicit inputs. There is no endpoint,
device-derived string or missing-input success default. The request-creation
boundary receives the actual original inner SDK callback `0x80027E40` and inner
object context; the outer callback remains separately retained.

## Header and cleanup details

The actual initialized configuration getter limits User-Agent to 24 bytes plus
NUL. The header helper limits Referer to 63 bytes plus NUL. Truncation is retained
as native byte behavior, without decoding, URL normalization or claiming that a
truncated value remains usable. Missing Referer skips that header; an explicitly
empty Referer still sets an empty header. Range word zero skips its header.

The initial release, header failure and submission failure have different effects:

- Initial old-handle release resets selected inner words even when the SDK
  release result is nonzero, then stores that failed release result separately.
  Setup stops before creating another handle.
- Header-add failure invokes release, clears the handle and header first bytes,
  and retains inner callback/context. It does not obtain a new last-error value.
  The outer wrapper copies the existing inner detail word, which may be stale.
- Submission failure maps the submission return value itself, attempts cleanup,
  then stores that original submission value even if release returned a different
  error. The outer wrapper copies the mapped detail and returns a negative result.
  A native mapping hole can leave detail zero while setup still fails.

The independent result keeps the actual numeric return separately from stored
detail. A zero detail or a zero setup/submission result is not an authenticated
response, completed download, usable catalog or accepted submission.

## Explicit SDK and timing boundary assertions

`prepare_request()` requires an exact ordered tuple of supplied SDK return words
and a separate tuple of supplied tick pairs. Missing, extra, unsupported or
out-of-order outcomes reject. Local caps are 16 SDK results and one tick pair.
The reviewed retry selector subset is `-1/0/1`: minus one and zero select table
slot zero; one selects slot one. Other values reject locally rather than indexing
unreviewed original storage. References are limited locally to 511 nonempty
NUL-free bytes; configured strings to 4,096 NUL-free bytes; receive capacity to
the existing ListData allocation bound. Zero capacity follows native failure.
These are explicit backend limits, not globally enforced native checks.

`NintendoRequestCall` retains supplied arguments privately. Its `SELECT` call
uses a **normalized descriptor** `(handle, table slot)`, not a literal capture
of the SDK's pointer/length arguments. The native verifier checks those actual
arguments against the correctly indexed original table words. It never reads
the referenced resources, labels them as a particular authority or derives a
key, endpoint or permission from their pointers.

SDK boundaries in this subset return scalar values without mutating application
RAM or invoking asynchronous callbacks. That is an explicit comparison boundary,
not established SDK behavior under concurrent operation. `submit_request()` also
supports direct inner submission, retaining its unnormalized stage result. This
permits an actual comparison of its invalid-state branch without inventing an
asynchronous phase change during setup. Tick pairs are numeric native timer
inputs, never publication, catalog issue or source freshness timestamps.

## Original comparisons and unfinished requirements

```powershell
.venv/Scripts/python.exe -m unittest tests.test_nintendo_request
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_nintendo*.py'
```

The verifier executes the complete selected original wrapper, inner creation,
configuration selector, cleanup, header storage/copy/formatting, submission and
error conversion. Only actual SDK leaves and the tick boundary are intercepted;
their order, return sequence and outgoing arguments are compared exactly.
Initialized synthetic configuration is immutable and the generator's entry
`0x800256A0` is explicitly forbidden. No original resource referred to by the
SDK configuration table is read or substituted into a functioning service.
ABI slots are compared individually so guards do not overwrite adjacent original
literal/table storage. Code/read/write ranges, instruction counts, exact opaque
manager storage, inputs, output state and fixture/stack guards are checked.
Host-side string inspection uses the same read bounds as emulated loads; host
word inspection additionally permits only the exact ABI and indexed table slots.

The 193 native comparisons cover 129 complete setup and 64 direct submission
cases: accepted/rejected shared words, old/absent handles, release failures,
creation errors and numeric mapping domains, every header failure stage,
submission/release error precedence, ignored configuration returns, all reviewed
retry selectors, callback/context zero, capacities, byte truncation, absent/empty
Referer and maximal Range. Public tests also reject incomplete boundary scripts,
unsupported selectors and over-limit inputs. Native tests skip honestly without
the private pinned input or optional Capstone/Unicorn.

All 13 targeted tests and 95 Nintendo regression tests passed. An independent
empty-working-directory run passed twelve public tests and explicitly skipped
the unavailable-private native class.

Actual SDK resource use, configuration generation, callback-produced inner state,
request/response HTTP parsing, asynchronous lifetime/cancellation, trust,
freshness, genuine catalog/media, reviews/bookmarks and original native UI remain
unfinished. This component enables no runtime route, sends no request, generates
no catalog and changes no original file, device profile or console backup.
