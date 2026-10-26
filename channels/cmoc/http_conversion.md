# Original SDK HTTP header lookup and numeric conversion

October 26, 2026. `jwc24/cmoc_http.py` supplies an explicit, bounded adapter from
SDK-equivalent response status/header state into the existing
[completion gate](response_gate.md) and [FD decoder](startup_record.md).
It does not contact a server, parse HTTP from a socket, or claim authentication.

## Evidence-backed behavior

The immutable Japanese HAPJ v512 executable remains SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
The completion caller at `0x80072D58` supplies original format `%03d` from
`0x8042AEAC` to numeric wrapper `0x8007A21C`. This is a **three-character scanf
field width**, including a sign, after any leading scanf whitespace. It is not
a four-digit integer conversion or a transport-success enum.

| Supplied `X-RESULT` field | Observed signed result |
| --- | --- |
| absent, empty or `abc` | 0 |
| `001` | 1 |
| `0100` | 10 |
| `100` | 100 |
| `9999` | 999 |
| `-100` | -10 |
| `+100` | 10 |
| leading tab then `100tail` | 100 |
| `0x64` | 0 |

The wrapper initializes its output integer to zero, looks up the header through
the original SDK, calls the original scanf routine, and returns that integer
without interpreting scanf's return value. Original scanf returns early on a
null or empty input; an absent/malformed value therefore leaves zero. This is
an observed conversion result, **not an authenticated successful response**.

The original SDK lookup compares names without ASCII case sensitivity and
returns the first matching field. Its returned value skips leading ASCII spaces
only. Trailing spaces and leading tabs remain. The independent decoder preserves
that behavior, including for `X-MC-HOST`, while keeping host values out of
representation and metadata.

The status path `0x8007A19C` calls original SDK getter `0x8019D5B0`. A null or
unresolved response returns -1. The SDK getter requires its object word at
`+0x14` to be nonzero, then reads the signed status word at `+0x18`; otherwise
it returns -1. The SDK header accessor also refuses lookup when that word is
zero. The API's explicit boolean `response_ready` models only this observed
zero/nonzero predicate, not a proven native connection-state name or a claim
that the underlying network operation completed. Tests use zero/one values.

## Backend contract and safe subset

`decode_completion_transport()` requires explicit `status_field` (signed 32-bit
integer or null), `response_ready`, and ordered header name/value byte pairs.
Null status represents unavailable SDK response storage. Status-line parsing
from actual wire bytes is outside this contract: the status word is supplied by
the caller, not inferred from a header string or manufactured as HTTP 200.

The local supported subset permits at most 64 ASCII-token header names of at
most 64 bytes, values of at most 256 bytes containing printable ASCII and tabs,
and at most 1024 serialized header bytes including the synthetic test status
line. CR/LF injection, NUL and other unreviewed forms reject. These bounds and
input restrictions are local safeguards, not native HTTP capacity claims.
Whitespace is preserved except for the observed SDK leading-space behavior.

`inspect_first_data_http_completion()` combines this conversion, the observed
ordered completion gate, and the existing safe FD framing/record checks. A
converted `0100` enters the gate as 10; `100` takes its original numeric error
branch. The handoff rejects unavailable/nonready SDK state even though some
native zero-completion paths do not prove a checked body. It also rejects
duplicate selected headers as local ambiguity policy and rejects present host
overrides until that separate state/configuration consumer is implemented.
Those restrictions do not claim the original SDK rejects the same inputs.

Existing APIs and live experiments are unchanged. The adapter returns inspection
objects; it does not write native state, generate a response, persist an entry,
submit a Mii or declare a working startup/menu flow.

## Original execution and verification

`tools/verify_cmoc_http.py` executes the actual application wrappers, SDK status
getter, SDK header lookup and copy, original case-insensitive comparison, and
the original scanf/decimal conversion. Only SDK registry resolution and heap
allocation/free boundaries are mocked. The SDK response object, inline HTTP
header storage, response handle, output buffers and stack are synthetic RAM.
No header lookup, numeric conversion or status getter is replaced with a stub.

The synthetic inline header storage uses a fixed HTTP status-line fixture;
the separate SDK status field is supplied explicitly. This deliberately does
not exercise the missing socket/status-line-to-SDK-object construction path.
The code runs within bounded original code ranges, may read original static
locale/conversion data, and can write only synthetic stack, allocated buffers
and the SDK response's observed temporary header pointer at `+0x24`. Original
inputs remain private and unchanged; no strings or raw bytes appear in reports.

The [validation report](../../research/cmoc_http_validation_20261026.json)
records 32 actual native comparisons for missing/malformed/width-limited values,
signed values, first-match duplicates, case, whitespace, empty/present hosts,
unavailable response and the SDK status/word-`0x14` predicate. Heap/input/stack
guards remain intact in every case.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_cmoc_http.py -v
```

Five public synthetic tests cover conversion, bounds, privacy and FD handoff.
The native class skips when the private pinned executable or optional
Capstone/Unicorn is absent. No 284-flag sweep is needed for this separate
accessor comparison; the earlier full-handler proof remains separate evidence.

Next gates are actual request and socket/SDK response construction, host-override
state handling, cryptographic trust/envelopes, genuine records, cache lifecycle,
Mii-list/menu consumers, authorization and original UI. These tests do not turn
an absent header's initialized zero into a service or authentication guarantee.
