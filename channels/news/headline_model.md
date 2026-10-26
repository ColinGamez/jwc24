# Original News article display model and separate ticker limit

October 26, 2026. The independently implemented record encoder now has a
guarded comparison against the complete original Japanese HAGJ v7 article
display-model constructor. This verifies more than the buffer validator's
structural acceptance: supplied article titles and optional source names reach
the original model's display-text buffer without rewriting their text.
It does not establish a consumer for the separate ticker table.

## Original executable evidence

The immutable local application executable is the same 2,018,688-byte HAGJ v7
input used by the [validator investigation](format.md), pinned by SHA-256
`8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852`.
Original executable bytes and derived disassembly remain private.

The full article-model constructor at `0x8000FA38` through its return at
`0x8000FCFC`:

- Resolves the supplied article identifier against the raw header's article
  count/offset at `0x3C`/`0x40`, using the original 44-byte record stride.
- Reads the article's title offset at record `+0x20`, body offset at `+0x28`,
  and title byte length at `+0x1C`. The resulting model retains those pointers.
- Resolves optional source and location references through their native tables.
- Allocates the display buffers and copies the title with the original UTF-16
  copy routine. When a source is present, it appends the original UTF-16 single
  space at `0x803567D0`, then the supplied source name. With no source it copies
  the title unchanged, including supplied Japanese text, whitespace and
  surrogate pairs.

The larger model constructor's call at `0x800106FC` corroborates this routine's
place in the application's article-data construction. Its fields at model
`+0x60` and `+0x64` are a selected raw-buffer pointer and topic-model pointer;
they must not be mistaken for raw-header ticker fields. In particular,
`0x80010010` stores the selected buffer at model `+0x60`, while `0x800102B8`
stores allocated topic models at model `+0x64`.

## Executed comparison

`tools/verify_news_headline_model.py` executes the complete article constructor
and original string routines at `0x801881BC`, `0x801881D8` and `0x80188238`.
Only allocator `0x80040A48` is mocked with a bounded guarded heap. Original
register-base values come from initialization at `0x80004224`/`0x8000422C`.
The caller supplies a synthetic timestamp/identifier reference derived from the
chosen test record; slot and topic indices are zero and the constructor's
boolean input is one. These fixtures do not verify the application's live
article-selection or flag-setting behavior.
No string operation or constructor branch is mocked or replaced with a Python
equivalent. The harness returns booleans and execution counts, never title text,
source names or raw buffers.

Seven completed comparisons cover all-table records, absent references, a later
article in the native ID search, and three distinct explicit ticker lists.
An eighth comparison supplies an invalid title pointer and verifies that the
original copy triggers the harness's input-bound guard. Input/model/heap/stack
guards and unchanged input are checked after completed runs. These are synthetic
records from the encoder, not publisher articles or recovered Nintendo content.
The [validation report](../../research/news_headline_model_validation_20261026.json)
records exact results and execution scope.

## Separate ticker table remains unverified

The 8-byte table at raw-header `0x60`/`0x64` still has the separately attributed
third-party format evidence described in [the structural investigation](format.md).
Targeted tracing of the pinned application did not recover its actual original
table consumer. Passing the article constructor must not promote that table to
an original native contract or claim a restored Wii Menu ticker/banner.

The constructor never reads the ticker header fields or table in these runs.
A deliberately impossible ticker count/offset is an explicit negative scope
control: the independent inspector rejects this buffer, but the article
constructor still produces its expected display text. That malformed control is
never signed, published or accepted as valid News data. This demonstrates the
constructor's limited coverage; it does not prove that no other original code
ever consumes the ticker table.

## Verification and remaining gates

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_news_headline_model.py -v
```

The private executable and optional `capstone`/`unicorn` dependencies are required
only for the native test class; public tests report its absence as a skip. The
harness has a 64 KiB input bound and an instruction cap, which are local tooling
policies rather than original channel capacities. Buffer validation, signature
trust, IOS/WC24 delivery, native allocation failures, fonts, text layout, actual
rendering and the separate ticker consumer remain outside this comparison.
