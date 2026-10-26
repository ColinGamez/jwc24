# Nintendo Channel language gate and downloaded-list installation

October 27, 2026. The new offline handoff connects the existing
[CSData inspection](csdata_contract.md), [reference planner](list_references.md)
and [selected ListData records](listdata_contract.md) through the actual
pre-download language predicate. A separate harness executes the original
context assignment, language loop and copy/decompression-to-publication slices.
It supplies no genuine catalog, transport, media or replacement screen.

The private Japanese HATJ v1792 executable remains pinned by SHA-256
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`,
4,194,944 bytes. Original software, disassembly and any proprietary input remain
private and outside Git. A source fingerprint identifies this input; it does
not establish a recovered catalog's provenance or permission to redistribute it.

## The actual language condition precedes catalog download

The original worker at `0x800266A8..0x80026724` calls the CSData language
accessors, obtains the configured language through the original configuration
getter, and searches the accepted entries before the list allocation/request.

- `0x800327F0` counts the prefix of CSData bytes `+0x18..+0x27` below seven.
  The first value of seven or greater stops the count; at most sixteen entries
  are considered. Entries after that point are not searched.
- `0x80032850` addresses the selected entry using `index & 15` and returns its
  remainder modulo seven. Within the counted prefix all entries are already
  below seven. Order and duplicate entries are retained.
- The worker compares each result with the supplied configuration's language
  byte. The harness executes the real accessors and configuration-getter path
  using an explicit synthetic configuration object. The getter's absent-object
  fallback, the live console setting and its surrounding initialization are not
  exercised.
- If no entry matches, the worker publishes the CSData pointer with a null
  ListData pointer, sets context word `+0x27A4` to zero and exits without the
  subsequent list allocation/request. A zero worker return therefore cannot
  establish that a catalog was loaded or that the channel is restored.

`jwc24.nintendo_load.plan_japanese_list_load()` validates the supported CSData
framing/CRC first, retains that exact language prefix, and prepares the existing
Japanese-country reference only when the explicit language is eligible.
Unknown configured language bytes prepare no follow-on reference. No language
is inferred from a Japanese region label, endpoint spelling or country alone.
The configured service prefix is explicit and has no default or authorization.

`inspect_japanese_list_download()` then sends supplied list bytes through the
existing bounded ListData decoder. An ineligible language rejects this handoff;
it does not become an empty or successful catalog. Existing strict UTF-16,
table/link bounds and format-six policy remain in force. The API does not
establish that bytes actually arrived from the prepared reference, and it does
not install a native object, publish a response or change application state.

## Received data is distinct from the native allocation

The actual retail caller at `0x800482BC` passes `0x1FC7CC` through `r10` to
`0x80026590`. The harness decodes the original caller's capacity setup and
relative call instruction and executes the context stores at
`0x800265B4..0x800265D0`. That argument becomes context word `+0x27A0`.

Static tracing of `0x80026728..0x80026744` shows that the worker allocates this
full temporary input budget. The later raw-data branch passes that configured
budget to the original copy helper; it does **not** pass the received body
length. The new native fixtures therefore distinguish:

1. Exact synthetic body bytes, independently decoded with their actual length.
2. The full synthetic native input allocation, whose unused tail is explicitly
   filled with `0xA5` for observation.
3. The full synthetic output allocation, initially filled with `0xCC`.

For the raw branch, original copying preserves the entire allocation, including
the synthetic tail. For LZ10/LZ11, the native decompressor writes the decoded
body and leaves the output tail unchanged. Neither tail represents downloaded,
historically captured or genuine Nintendo catalog data. The independent
handoff accepts exact supplied body bytes and continues to reject raw padding
when the declared size differs from available bytes.

The actual heap allocator, transport buffer filling and asynchronous object
ownership are not executed. Full retail-size raw allocation/copy cases are
executed; the local harness limits meaningful decoded body bytes to 64 KiB and
nonempty synthetic tables to the already decoded software/link tables, with
at most 64 rows each. Those local test limits are not native schema limits.

## Original installation and its different state effects

At `0x80026950`, the worker examines the high nibble of the first input byte.
The executed supported branches are raw input, LZ10 and LZ11:

| Original boundary | Executed behavior |
| --- | --- |
| `0x80100A20` / `0x80100A60` | Original advertised-size and decompression helpers |
| `0x80004364` | Original raw copy, including floating-point load/store instructions |
| `0x80026988..0x80026998` | Calls real ListData constructor and selected validator |
| `0x800269A4..0x800269C4` | Failed validator: numeric error boundary, temporary release, zero exit |
| `0x800269C8..0x800269F0` | Passed validator: publish CSData/ListData pair, system boundary, context result, temporary release, zero exit |
| `0x80026A10` | Original temporary descriptor destructor; actual free is intercepted |

The harness enables the PPC floating-point facility so the original raw copy's
`lfd`/`stfd` instructions execute. It does not replace copying, decompression,
the constructor, validator or publication stores with Python stubs.

On a passed validator the pair receives the supplied CSData and ListData object
pointers and context word `+0x27A4` receives the earlier normalized load result.
That explicit result is restricted to zero or one: `0x80026A80` permits these
nonnegative continuation values; their additional service/UI meanings are not
invented. Both complete and failed installation paths exit with zero, and both
release the temporary allocation once. The failure case's intercepted error
arguments are the observed numeric pair `-209`, `262000`.

**Preserving the published pair does not mean complete rollback.** The native
ListData constructor assigns its separate global pointer before the validator
runs. The rejected-record comparison proves that this global pointer still
changes while the published pair and context result remain unchanged. The new
backend inspector performs no corresponding native mutation. Cache lifetime,
concurrent readers and enclosing failure recovery remain unfinished.

The selected original header gate admits the tested format-seven fixture,
whereas the existing backend deliberately supports format six only. The native
comparison records that difference instead of treating local rejection as
proof that the original rejects the same input. This does not establish a
complete format-seven schema or permission to publish unsupported data.

## Verification and remaining work

```powershell
.venv/Scripts/python.exe -m unittest tests.test_nintendo_load
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_nintendo*.py'
```

Twelve targeted tests cover the language prefix, duplicates/sentinels, supplied
configuration, compressed and raw handoff, strict record policy, privacy and
software fingerprint refusal. Thirty-five native comparisons exercise thirty
language cases and five installation cases, including full retail-size raw
copy, LZ10, LZ11, rejected enum and the native/backend version difference.
The [validation report](../../research/nintendo_load_validation_20261027.json)
records aggregate evidence without catalog titles, request references or input
contents. Native tests skip honestly without the private original or optional
Unicorn; public tests still exercise the independent handoff.
The full Nintendo-specific regression passed all 52 tests in 15.875 seconds.
An independent run from an empty temporary working directory passed all eight
public tests and explicitly skipped the unavailable-private-input native class.

Only error reporting, system/scheduler boundary `0x8021EF80` and actual freeing
are intercepted. The latter system boundary is not called a timestamp writer.
The harness bounds instructions, exact control/read/write ranges and synthetic
objects, and verifies immutable inputs and object/output/configuration/stack
guards. Three separate slices execute: context stores, language gate, and
post-download installation. It deliberately skips the intervening asynchronous
setup, HTTP manager, allocation, polling and earlier CSData loading.

Recover those missing real I/O/error/lifetime paths, the remaining ListData
tables and software/media relationships, genuine catalog provenance, trusted
delivery/freshness and the original complete list/search/detail/video UI.
Review/bookmark/usage submissions remain separate work. These checks do not
make Nintendo Channel browsing, authentication or content acquisition complete.
