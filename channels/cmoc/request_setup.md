# Original cached-worker request setup

November 7, 2026. `jwc24.cmoc_request_setup` projects explicit request-setup
metadata for the replacement backend. It extends the existing
[descriptor construction](request_construction.md) with evidence from the
actual cached worker, rather than treating the generic unconfigured SDK branch
as evidence of the configured FD path. It neither sends HTTP nor establishes
authenticated startup.

## Observed construction

The private Japanese HAPJ v512 executable is pinned to SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
The original remains unchanged and outside Git. All request, worker, resource,
SDK, singleton, queue and stack objects in the comparison are synthetic RAM.

The complete worker `0x80072500` obtains the cached request, copies its header
queue, obtains metadata and constructs a twelve-byte descriptor prefix through
`0x8007270C` / `0x80072740`. It calls setup `0x80073E58`, which calls request
construction `0x8007F0D4` and the outer SDK constructor `0x8019C7C4`. The configured
branch executes in this comparison, including its own prefix copies and receive
capacity arithmetic.

| Decision | Observed setup behavior |
| --- | --- |
| Configuration pointer present | Configured construction path, including when resolved sizes are zero |
| Configuration pointer absent | Separate construction path, sets flag `0x80`, capacity `0x30000` |
| Configuration comparison prefix | Copy at most 64 bytes if its pointer is present |
| Cached descriptor prefix | Concrete worker produces twelve bytes, then the setup copy supports at most 64 |
| Configured receive capacity | Resolved worker word `+0xC8` + retained comparison-prefix length + `0x400` |
| Decompressor setup predicate | Configuration word `+0x1C` is nonzero |
| URL byte 4 equals byte 4 of original `https://` | Secure-branch predicate; this alone proves no TLS operation |
| Timestamp metadata present and secure predicate false | Attempt `If-Modified-Since` before `X-APPVER` |
| Every selected setup path | Attempt `X-APPVER`, even when its producer returns a null pointer |

Neither header is renamed an authorization credential. The attempted header
calls, SDK header acceptance, and actual serialized request are separate facts.
This component preserves a null `X-APPVER` value as an attempted call; it does not
manufacture an empty HTTP field or claim that the SDK would accept it.

The resource object's constructor at `0x80064880` copies 32 original bytes into
its `+0x10` block. That on-disk initialization contains zero size words and
pointers to empty storage; it is not evidence of the loaded live resource values.
The setup uses block fields `+0/+4` as a comparison span, `+8/+0xC` in hash setup,
`+0x10/+0x14/+0x18` in cipher setup and `+0x1C` as a decompressor predicate.
Secret material, resource loading, hash/cipher initialization success and the
`.ces` envelope still require separate proof.

`ResourceSetup.hash_span_size` therefore means the **explicitly supplied resolved
worker word `+0xC8`**, not a key, digest algorithm, authenticated checksum or a
claim that the original initialization succeeded. An operator cannot infer it
from an empty on-disk resource block. A present configuration with size zero
remains distinct from no configuration. Optional comparison-prefix pointers
retain null versus present-empty identity in the input object.

Subsequent [original hash-wrapper execution](hash_processing.md) establishes
that `+0xC8` is assigned the supplied or C-string-resolved key length, rather
than the algorithm's fixed twenty-byte HMAC-SHA1 output size. The existing
`hash_span_size` API name remains a projection of that explicit resolved word;
it neither supplies a key nor proves actual resource initialization. Native
final string comparison and full-span binary equality remain separate results.

## Independent backend boundary

`project_request_setup()` requires the URL, method word, optional resolved
resource metadata, cached prefix, timestamp predicate, already-produced date
and application-version header values, and a caller evidence reference.
The reference is an assertion, not authenticated provenance. Private values do
not appear in representations or metadata reports.

The immutable result exposes capacity, retained spans, ordered attempted header
calls and decompressor predicate. It can support a later service adapter without
secret values, a profile, a socket or a mutated native cache. Sizes, ASCII header
bounds and the accepted URL subset are explicit local restrictions. Date values
are limited to 75 bytes plus a terminator in the 76-byte copied date context.
Application-version values are limited to 63 bytes plus a terminator because the
synthetic context puts their string at `+0x18` and the original availability
predicate at `+0x58`. A 64-byte value would overlap that flag. The actual producer's
maximum string length is not proved by this fixture; 63 is a local accepted
subset. The longest accepted values execute in a separate native case. The current
resolved `+0xC8` maximum of 64 is a local supported subset, not a recovered native
capacity check. No method-enum HTTP meaning is invented; the actual FD descriptor
still supplies numeric method word zero.

The separate [receive-geometry composition](receive_geometry.md) now verifies
the embedded `0x440` wire storage and requires the combined resolved span and
retained wire prefix to fit its 64-byte overhead allowance. This setup component
continues to project the original unchecked arithmetic; not every projected
configuration passes that composition check. Actual loaded resource sizes and
SDK chunking remain unverified.

## Original execution comparison and limits

`tools.verify_cmoc_request_setup.verify_request_setup()` begins at the complete
original cached worker and returns from it. It executes the original queue copy
and empty-queue consumer, actual twelve-byte prefix producer, configured request
branch, prefix truncation, URL copy, outer SDK constructor and object zeroing,
and standard header-selection/order logic. It checks SDK callback binding,
request/response capacity, retained prefixes, immutable inputs, object guards,
stack bounds, instruction count and allowed control flow.

Explicit intercepted boundaries are:

- Cached-request lookup, the already-proved configuration-selection predicate,
  singleton/resource lookup and timer-manager lookup.
- Hash/cipher/decompressor initialization, using caller-supplied resolved
  metadata. These are not cryptographic execution comparisons.
- SDK registry, allocator, lower request-record constructor and registration.
  The outer SDK constructor really executes; lower URL parsing, method validation,
  socket serialization and request registration do not.
- Timestamp string producer and application-version context lookup. Original
  date-context copying executes; actual timestamp formatting is not proved.
- SDK header-add, proxy, secure options and async start boundaries. The original
  caller's choices/order execute; SDK acceptance and asynchronous lifetime do not.
- Debug logging. There is no native console, profile, device or network access.

The [validation report](../../research/cmoc_request_setup_validation_20261107.json)
records nineteen native executions: fifteen configured and four unconfigured,
covering HTTP/HTTPS predicates, timestamp absence/presence, zero/nonzero resolved
sizes, null/present-empty comparison spans, 64/65-byte truncation, decompression
zero/nonzero, null application-version producer and both accepted header-length
maxima. All use synthetic FD method
word zero and an empty header queue. Nonempty queue/header serialization, setup
failure, existing-request cancellation, resource acquisition, cache persistence,
actual `.ces` processing, trust, identity and original full UI remain unfinished.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_cmoc_request_setup
```

Six public tests and one nineteen-case native test pass locally. The native
class skips honestly without the pinned private executable or optional
Capstone/Unicorn; the public projection tests remain usable.
