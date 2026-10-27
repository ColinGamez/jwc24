# Original FD request descriptor and target construction

October 28, 2026. `jwc24.cmoc_request` provides explicit first-data descriptor
construction and canonical target decoding. It connects a source-supported
request prefix to the existing [HTTP conversion](http_conversion.md),
[completion gate](response_gate.md) and [FD record decoder](startup_record.md).
It does not create a listening endpoint, choose genuine service values, send a
request or declare authenticated startup.

## Actual constructor path

The private Japanese HAPJ v512 executable is pinned by SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
The source file is unchanged and remains outside Git. All emulated descriptor,
configuration, singleton and stack storage is synthetic.

The complete request wrapper at `0x80069A18` calls the original 32-byte seed
constructor `0x80069A58`, then the complete descriptor constructor `0x80074330`.
The descriptor copies the tag and words at offsets 4 and 8, and obtains its
bytes 2 and 3 from the singleton's bytes at `+0x10` and `+0x11`. It does not copy
the seed's other twenty bytes into the target. **Target bytes 12 through 31
remain unchanged.** The independent producer requires those bytes explicitly;
there is no assumed all-zero cached header.

The FD branch at `0x80074520` selects numeric family word 0 and native method
word 0. The full URL formatter at `0x80074904` runs the original `snprintf`
three times, concatenating original origin, `/first/%u` using word 4, and the
selected suffix. Word 8 remains part of the cached correlation prefix and is
not used in that particular URL template. Neither word is renamed a device ID,
account ID, revision or timestamp without evidence of that meaning.

| Observed input / destination | Preserved behavior |
| --- | --- |
| Tag | `FD` (`0x4644`) |
| Singleton bytes `+0x10`, `+0x11` | Target cached-header bytes 2, 3 |
| Supplied unsigned word 4 | Target word 4 and unsigned decimal `/first/<value>` |
| Supplied unsigned word 8 | Target word 8 |
| Prior target bytes 12..31 | Unchanged, not copied from zero-initialized seed |
| Configuration predicate false | `.ces` suffix |
| Configuration predicate true | `.bin` suffix |
| Descriptor words `+0x20`, `+0x24` | Both zero for the FD branch |

The suffix selector `0x80074A48` invokes `0x80074248`, which obtains an index
through manager word `+0x2C` and evaluates a configuration-table predicate.
Its underlying original lookup supports indexes 1 through 32. The native
comparison supplies index 1 and an explicit zero/nonzero table entry and runs
the actual lookup and boolean conversion. This is not a string-emptiness test.
The setting's complete product meaning and `.ces` envelope/cryptographic format
remain unverified; the independent API uses the neutral name
`configuration_2c_predicate`.

The original FD origin is `http://miicontest.wapp.wii.com`. The independent
producer requires an explicit operator-selected origin, so it can describe a
replacement service without pretending that its URL was captured from Nintendo.
The native comparison uses only the original origin from the pinned executable.
No hostname override, DNS rule or original profile is changed.

## Usable offline backend boundary

`build_first_data_request()` requires both uint32 words, both uint8 bytes,
exactly twenty opaque cached-header bytes, the explicit configuration predicate,
origin and a bounded nonempty caller evidence reference. The reference is only
a caller assertion; it does not authenticate values or grant source rights.
Its immutable result keeps the URL and cached header out of representation and
metadata. The cached header is a native descriptor/correlation observation, not
proof that those bytes are sent as the HTTP request body.

Origins use a local HTTP(S)-origin subset without credentials, path, query,
fragment, controls or non-ASCII text. The completed URL must fit the original
128-byte descriptor buffer including its terminator. Overflow rejects locally;
the independent producer does not imitate truncation or publish an alias.
These origin/ambiguity restrictions are local safeguards, not recovered native
HTTP acceptance rules.

`parse_first_data_target()` decodes only canonical
`/first/<uint32-decimal>.ces` or `.bin` paths. Signs, leading-zero aliases,
percent escapes, queries, case variants and overflows reject. It exposes the
opaque numeric word and suffix selector for later backend routing, without
declaring identity or authorization. No route or synthetic response is enabled.

The integration test uses the produced cached correlation header with an
explicit synthetic FD record through actual header conversion and the existing
safe completion/FD decoder. It does not simulate an actual socket, server,
cryptographic envelope, account, Mii cache or restored menu.

## Complete original execution and limits

`tools.verify_cmoc_request.verify_first_data_request()` executes the complete
seed/wrapper, descriptor tag switch, prefix setters, suffix selector,
configuration predicate and original unsigned formatting. Only singleton and
manager lookup boundaries are intercepted. No copy, zeroing, `snprintf`,
suffix/configuration branch or numeric conversion is stubbed.

The harness pins the executable, caps instructions, bounds code/read/write
ranges and checks exact descriptor, opaque tail, input/configuration, heap-free
synthetic objects and stack guards. It executes 23 native cases covering both
suffixes, uint32 decimal boundaries, independent word-8 variation, byte-2/3
boundaries and all-zero/nonzero opaque tails. Every result matches the
independent constructor, including three original formatting calls per case.
The [validation report](../../research/cmoc_request_validation_20261028.json)
contains only scope/counts, not payload values or original instructions.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_cmoc_request
```

Six public synthetic tests and one native test pass locally. The native class
skips explicitly without the private pinned executable or optional
Capstone/Unicorn. The public constructor/target/FD integration tests remain.

The real cached-request worker at `0x80072500` invokes setup at `0x80073E58`,
which in turn reaches request creation `0x8007F0D4` and SDK constructor
`0x8019C7C4`. Those callers also pass resource/configuration and metadata
structures. Their complete construction, HTTP header setup, actual SDK
method-enum meaning, async lifetime and socket serialization are **not** proved
by this descriptor harness. Executing a convenient generic no-config SDK branch
would not establish the real FD worker path, so it is not substituted here.
Actual `.ces` processing, verified service values, host override/state handling,
authorization and complete native startup/UI remain separate unfinished work.
