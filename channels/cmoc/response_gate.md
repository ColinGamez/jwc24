# Original HTTP-completion and body-header gate

October 26, 2026. `jwc24/cmoc_response_gate.py` connects the recovered
[response framing](framing.md) and [FD startup record](startup_record.md) through
the original completion handler's ordered transport/header/state checks. It is
an offline backend component, not a listening startup/authentication service.
No response, Mii, vote, notice or device/profile state is published or changed.

## Native path and independent API

The private Japanese HAPJ v512 DOL remains pinned by SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
The complete handler at `0x80072CE0` through `0x80072F68` consumes a cached
request, parsed HTTP status/`X-RESULT`, a response-object flag byte, body bytes
and two singleton-state bytes. Its order is:

| Observed condition | Numeric completion |
| --- | --- |
| Cached request absent | zero, without checking transport or body |
| Parsed signed HTTP status at least 300 | status plus `0x3EFD0` |
| Parsed signed `X-RESULT` at least 100 | result plus `0x3EBE8` |
| Response flag `0x40` set | `0x3D8C5` |
| Response flag `0x10` set | `0x3D929` |
| Response flag `0x20` absent | zero, without checking body |
| Body shorter than 32 bytes | `0x3D98D` |
| Header tag/word-4/word-8 differ from request | `0x3D98E` |
| Header byte 2 equals 255 | `0x3D8C6` |
| Header byte 2 exceeds singleton byte at `+0x10` | `0x3D8C7` |
| Singleton byte at `+0x11` is known and differs from header byte 3 | `0x3D8C8` |
| Remaining header path | zero; learn byte 3 if singleton byte was 255 |

These offsets, predicates and completion numbers are observed native behavior;
the opaque state bytes and response flags are not renamed authentication,
eligibility, region, consent or service-version fields. Signed transport values
below normal HTTP ranges are represented faithfully for comparison, not endorsed
as sensible server responses. HTTP error-result addition retains the native
unsigned 32-bit completion representation.

`evaluate_response_gate()` requires every parsed transport/flag/state value and
the expected 32-byte request explicitly. Missing cache is represented by an
explicit null request. Its immutable result distinguishes numeric completion,
an actually passed body-header gate, which checks ran, and the next opaque byte-3
state. Opaque learned values are excluded from representation and metadata.
It returns a state decision without persisting it.

`inspect_first_data_completion()` is a usable backend handoff: it requires the
body-header gate to pass, then invokes the existing bounded framing, exact FD
tag, request-correlation and FD-record decoder. It preserves their stricter local
ambiguity and bounds policies. A zero completion with no checked body is rejected
by this handoff; it is never converted into a successful startup result. Existing
framing/FD APIs and experiments remain unchanged.

## Complete original-handler comparison

`tools/verify_cmoc_response_gate.py` executes the whole original completion
handler, error-result arithmetic, framing object/header access, correlation,
byte predicates, learned-state update and framing destructor. Guards constrain
all reads/writes, the singleton's one allowed changed byte, fixture objects,
immutable input, stack, control flow and instruction count.

Only these boundaries are intercepted:

- Cached-request lookup `0x800721F8` returns explicit synthetic header storage
  or none.
- HTTP accessors `0x8007A19C` and `0x8007A21C` supply explicit parsed numbers.
- Header accessor `0x8007A1E8` supplies no host-override header in these cases.
- Singleton accessor `0x80064EF4` returns explicit synthetic state storage.
- Completion callback `0x8006EAE4` records its numeric argument without running
  the surrounding asynchronous service or UI.

No header-check, correlation or state-update branch is stubbed. All 284 native
comparisons match the independent component: every possible flag byte plus
HTTP/result boundaries, each correlation field, short bodies, byte-2 sentinel
and limit boundaries, byte-3 learning/mismatch and missing request. Each run
reaches one completion callback and preserves its input/state/stack guards.
The [validation report](../../research/cmoc_response_gate_validation_20261026.json)
contains aggregate scope and counts, without identifiers, state values or payloads.

## Verification and unfinished service gates

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_cmoc_response_gate.py -v
```

Four public synthetic tests check independent behavior and the framing/FD
handoff; the native test class skips honestly when the pinned private input or
optional Capstone/Unicorn is unavailable. Fixtures are synthetic bytes only.

The parsed HTTP values are deliberate harness inputs: original numeric-header
parsing, absent/malformed-header behavior and host-override processing remain
unverified here. The response flag meanings, actual request construction,
cryptographic envelope/trust, genuine startup records, cache persistence,
first-run prerequisites, subsequent menu/Mii-list records, identity/submission
authorization and original UI completion remain unfinished. A passed header
gate is not proof of authenticated or current service data.
