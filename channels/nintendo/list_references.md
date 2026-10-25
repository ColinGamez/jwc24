# CSData follow-on list references

October 26, 2026. The [CSData framing check](csdata_contract.md) now has a
separate next-stage reference planner and native construction comparison.
This identifies the bytes passed toward a subsequent download. It does not
recover the list's record schema or provide a usable Nintendo Channel catalog.

## Actual construction

The original HATJ v1792 consumer at `0x800324D0` was executed through its return,
including the construction that the previous header harness stopped before:

```text
configured service prefix
  + CSData reference bytes at offset 0x35
  + /list/
  + country component
  + /
  + language component
  + /
  + unsigned decimal BE32-at-0x0C
  + .LZ
```

The original country resolver maps country value 1 to `JP`. The original
language resolver maps values 0 through 6 to `ja`, `en`, `de`, `fr`, `es`, `it`
and `nl`. The public planner supports that Japanese-country selection, with
an explicitly supplied language code and service prefix. It does not inspect
the owner's console region, choose endpoints or infer runtime configuration.

BE32-at-`0x0C` is used as a filename identifier. Its date, generation or catalog
version meaning is not established here. No such semantics are fabricated.
Country/language resolution and byte construction are separate from whether
the channel's downloaded language list permits the selected language.

| Native anchor | Observed behavior |
| --- | --- |
| `0x80032618..0x800326CC` | Appends configured prefix, reference, separators, list component, locale components, decimal word and extension into the consumer's 512-byte string storage. |
| `0x800085E0` | Original bounded append helper; remains native in the comparison. |
| `0x80008AE0` | Original unsigned decimal formatting wrapper and its formatter execute, including 0 and `0xFFFFFFFF` synthetic cases. |
| `0x80031710` | Appends the separately resolved country and language components with separators. |
| `0x80031DD0`, `0x800321F0` | Original country and language resolvers execute from explicitly supplied synthetic configuration. |
| `0x8002678C..0x80026824` | Downstream caller obtains the constructed string through `0x80032880`, copies it to its own storage and passes it to the manager. A tick/time helper is stubbed in this isolated slice. |
| `0x8002BCF0..0x8002BD40` | Original manager copies the reference again and prepares its virtual callback. The harness intercepts that callback before any transport implementation executes. |

The callback boundary proves string handoff in synthetic state, not an HTTP
method, header set, completed request or server response. Earlier load checks,
language eligibility, allocation and manager initialization are separate from
the executed downstream slice. Those initial states are supplied by the harness.

## Independent component and limits

`jwc24/nintendo_references.py` builds this reference only after the existing
CSData inspector accepts the supported framing subset. Its return object's
reference and identifier are excluded from `repr`; metadata contains lengths
and explicit unverified scope. No output is published or requested.

The native helpers concatenate bytes directly. The independent planner likewise
preserves repeated separators, relative segments, spaces, punctuation and
non-UTF-8 bytes. This is not URL parsing, normalization, escaping, endpoint
authorization or permission to fetch a reference. An eventual network adapter
must apply its own reviewed endpoint policy separately.

The planner rejects a result of 512 bytes or more rather than using a silently
truncated request. A 511-byte constructed reference matches the native output
in the guarded test. A missing/empty service prefix, embedded NUL, unknown
language or invalid CSData is rejected. No original service URL is a default.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_nintendo_references
```

Ten tests exercise byte construction, unsigned decimal boundaries, all seven
language components, supported compressed inputs, opaque paths, capacity
limits and original construction/handoff. Native tests require the private
original DOL and Unicorn. The complete source fingerprint remains
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.

The harness checks the source hash and executable code ranges, bounds
instructions and native writes, protects object/input/configuration/stack
storage with checks and compares both copied references with the independent
plan. The configured prefix/country/language/length slot, downstream context,
manager fields and callback table are synthetic RAM. The decimal formatter,
resolvers, append and copy helpers are not mocked. Logs and the isolated
downstream time service are the only called helper stubs; transport is stopped
before execution. Original files are unchanged and remain outside Git.

## Remaining requirements

Recover and independently decode the downloaded list records, their software
and media references, authentication and freshness rules. Establish the actual
manager initialization, HTTP behavior, load failures and cross-file lifetimes,
then verify search, ranking, details and video/download UI. The supported-language
selection path must also be connected before a real request can be prepared.
This new component supplies no catalog fixture, server endpoint, native review
success or restored browsing claim.
