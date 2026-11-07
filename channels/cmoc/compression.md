# Original incremental decompressor and wrapper counts

November 7, 2026. `jwc24.cmoc_compression` supplies an independent bounded
streaming LZ10/LZ11 projection, compared with the unchanged original Japanese
HAPJ v512 initializer, decoder and application wrapper. It retains partial
header/reference/flag state across the caller's actual chunk boundaries. It
does not infer a complete stream from successful transport or a numeric return.

The private executable remains pinned to SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
Its bytes remain private and unchanged. Public code contains no copied SDK
instructions, proprietary resource files or device keys. Synthetic streams use
the existing JWC24 LZ encoders/decoders and explicit literal/overlapping-reference
fixtures, including every LZ11 reference-length form.

## Verified original paths

Application setup `0x80069428` stores the output pointer and an explicit enabled
predicate. Enabled setup calls SDK initializer `0x80177BE4`; a positive output
limit is stored in the SDK context. Decode `0x800694EC` calls streaming decoder
`0x80177C58` and computes an application count from separately retained remaining
sizes. Disabled decoding copies input to the retained output cursor and advances
it. No automatic compression detection occurs on that branch.

The streaming decoder accepts types `0x10` and `0x11`, little-endian three-byte
declared sizes and their eight-byte extended-size headers. It retains partial
headers and partially read references. Complete LZ10 and LZ11 streams decode to
the same bytes as the existing independent JWC24 one-shot codecs; the new tests
also execute the original decoder at every tested two-chunk cut. One-shot
agreement alone is not used to claim incremental state agreement.

The SDK's remaining count, the application's cached remaining count and the
actual output cursor are different quantities:

| Observed path | SDK / application / output behavior |
| --- | --- |
| Partial SDK header | Can return `-1` while retaining header bytes and size state; a later chunk can resume |
| Ordinary partial input | Return remaining output count from SDK; application reports the difference from its cached count |
| Declared size 3, explicit output limit 2 | Write two bytes; SDK returns zero; application returns three |
| More than 32 bytes left in the completing input chunk, no positive output limit | SDK returns `-3` after writing the decoded bytes; application returns zero and retains its prior cached count |
| Reference length exceeds remaining output, no positive limit | SDK returns `-4`; earlier writes in the same call survive; application returns zero |
| Positive output limit and reference crosses remaining count | Restrict the copy to the remaining count; the limit does not allocate output backing |
| Already complete application decoder | Return zero without invoking SDK again; ignore later input |
| Disabled application decoder | Copy exactly the supplied bytes; do not initialize or invoke the compressed-stream decoder |

The 32-byte trailing rule is observed original behavior, not permission to invent
network or cipher padding. Every supplied byte remains an explicit caller input.
Negative SDK results do not erase already written output or reset stream state.
Successful completion does not establish a valid resource or authenticated body.

## Backing and local bounds

The application's original size helper at `0x801783D0` reads four bytes, or eight
when the short size is zero, independently of the input-length argument. The
public application projection requires that whole first header in supplied
backing. Direct SDK mode separately supports partial headers. A short first
application header is a local guard failure; no zero bytes are supplied for it.

The API requires explicit enabled state, output limit and output capacity, at
most 64 immutable chunks and 4,096 input/output bytes. A declared output larger
than 4,096 is outside this local inspection contract. A positive decoder limit
and allocated capacity remain independent. References before supplied output
history and writes beyond capacity reject rather than reading surrounding RAM,
wrapping, clipping to an invented capacity or fabricating bytes.

`tools.verify_cmoc_compression` takes the exact pinned executable as an argument.
Original initializer, size helper, decoder, application copies and wrapper
arithmetic execute without decoder stubs. Only supplied context, input chunks,
output backing and stack are admitted by memory hooks; no original static data
or credential/resource spans are read. Every object has guards. Each step checks
the exact contiguous set of written output addresses, complete written prefix,
untouched initial output tail, both remaining counters, header/reference/flag
state and SDK/application returns. Guard failures are independently exercised
through the actual original code.

## Callback ordering and remaining integration

Targeted original callback instructions establish this configured event-2 order:

1. Hash the rounded wire-input span through `0x8007A0A4`.
2. Invoke cipher `0x80069388` into the explicit intermediate buffer.
3. Store the cipher's application return as the intermediate count.
4. Invoke decompressor `0x800694EC` with that count.
5. Add the decompressor's application return to the decoded-size counter.

The hash input is therefore the rounded wire ciphertext span on this path,
before decryption. This call-order evidence does not yet prove a complete
configured transform execution. Existing callback tests still use explicit
transform boundaries. A separate integrated verifier is planned using only
synthetic encrypted streams, keys, IVs, digests and actual supplied padding.
Resource acquisition, genuine `.ces` framing, key/ownership provenance,
concurrent transport/cache behavior, full native flow and authentication remain
unfinished.

Run `python -m unittest tests.test_cmoc_compression -v`. Public projection tests
need no optional packages. Native comparisons additionally require Unicorn,
Capstone and the private executable; absence produces an explicit skip.
The [metadata-only report](../../research/cmoc_compression_validation_20261107.json)
records the actual tested scope. No network request, profile, NAND, original Wii
backup, installation or native user interface is changed by this component.
