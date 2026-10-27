# Nintendo ListData inline names and identifier relations

October 28, 2026. The existing [partial ListData decoder](listdata_contract.md)
now reads selected fields in descriptor tables one and two. This adds real
name/code lookup relationships to the existing software/title and linked rows.
No production catalog, screen, label, image or provider data is generated.

The original Japanese HATJ v1792 executable remains private and unchanged,
4,194,944 bytes, SHA-256
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
The [validation report](../../research/nintendo_named_tables_validation_20261028.json)
records numeric code regions, hashes and aggregate synthetic comparisons;
it contains no original software, names, identifiers or private catalog bytes.

## Record shapes supported by actual consumers

| Table | Observed fields | Original connection |
| --- | --- | --- |
| One, stride `0x6C` | Identifier byte at zero; three raw bytes at `+1`; inline wide name at `+4`; kind byte `+0x6A`; opaque final byte `+0x6B` | Getter `0x8002C610` multiplies the index by `0x6C`; name lookup `0x8002C630` compares the identifier with context byte `+0xA4` and returns matching row plus four |
| Two, stride `0x80` | Four raw key bytes at zero; inline wide name at `+4` | Getter `0x8002C3F0` shifts the index by seven; `0x8002C410` compares four bytes using original helper `0x8002C330` against context bytes `+0xA5..+0xA8`, then returns matching row plus four |

Table two's stride is now known and included in count-times-stride and overlap
validation. It is no longer treated as an arbitrary nonempty unknown table.
The other unparsed tables remain explicitly unresolved.

The native software consumer at `0x8002EDE0` matches a software row's byte `+8`
against table one's identifier byte and returns the first matching row plus
one. Callers at `0x8000707C..0x8000709C` copy exactly three bytes from that
returned address. The decoder preserves those bytes without inventing a
string encoding, product-code meaning or numeric byte order.

The name getter is used at `0x800F6490`; its returned pointer reaches the native
wide formatter at `0x800F64C4`. The original format at `0x803B6C58` contains two
`%ls` conversions. This corroborates the inline wide-name use; the new harness
does not execute that whole UI/BMG/formatting path. Its separate original Unicode
copy comparison preserves Japanese and surrogate-pair name bytes using the same
bounded copy helper already established for software titles.

The complete selected classification function at `0x8002ECB0` uses the first
matching table-one row's byte `+0x6A`. All 256 byte cases are compared with the
original function: values one through ten return themselves; zero and values
eleven through 255 return 255. The decoder retains the raw byte even when the
derived result is 255. It does not globally reject those values or rename the
result as availability, eligibility, permission or a particular category.

## Backend behavior and preservation

`NintendoListInspection` adds default-empty `named_id_rows` and
`named_code_rows` tuples. Existing five-argument construction remains compatible.
Each row preserves its original order and file offset. All record bytes are
retained across identifier fields, decoded name storage, raw kind and opaque
tail; bytes after a name's terminator are kept without assigning padding semantics.
Data-bearing fields are excluded from representations and metadata.

- `find_named_id(byte)` and `find_named_code(four_bytes)` return the first match
  in original order. Duplicate identifiers and names remain present.
- `named_id_for_software(index)` follows the observed software-byte relationship.
  A missing relation returns `None`; it is not converted into an invented label.
- `NamedIdListRow.classification_result()` returns the selected native scalar
  projection while preserving its input byte separately.

With a present ListData object, both original name getters take an observed SDA
fallback pointer when no matching row exists. The pinned original file contains
a zero wide unit at that address. The backend lookup returns `None` to retain
the distinction between absence and actual catalog text; it does not rewrite
the native fallback behavior or claim a generated empty name came from a source.

Four-byte keys stay bytes. No integer interpretation, case normalization,
sorting, deduplication, guessed publisher/genre meanings or default names are
introduced. Missing software/name relationships are counted separately and do
not become a fabricated valid relation or a blanket catalog rejection.

## Explicit local string and structural limits

The inline supported name regions are `+4..+0x6A` in table one (51 wide units)
and `+4..+0x80` in table two (62 wide units). They must contain a terminated,
strict UTF-16BE prefix within that region: at most 50 or 61 units before NUL.
These termination rules are a **stricter local subset**, not checks performed by
the original pointer getters. A table-one name cannot consume kind/tail bytes
as its terminator. Post-NUL storage is retained verbatim.

The negative native comparison leaves a name unterminated within its own field
but supplies zero kind/tail metadata afterward. The native header validator and
pointer getters still run; the backend rejects the name before copying it. This
distinguishes local safety policy from native rejection and establishes no
behavior for the full original UI reading malformed source data.

Existing raw/LZ10/LZ11 bounds, declared-size checks, exact software links and
known table non-overlap policies remain. Tests also pass the new names through
the [retained HTTP handoff](http_lifecycle.md), preserving compressed body versus
unused allocation tail. Complete catalog schema, actual source provenance,
signatures, freshness and native UI remain explicitly unverified.

## Verification

```powershell
.venv/Scripts/python.exe -m unittest tests.test_nintendo_named_tables
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_nintendo*.py'
```

The guarded harness executes the original constructor, selected validator,
row getters, first-match name/software lookup loops, bytewise key comparisons,
selected classification function and Unicode copy helper. No SDK helper or
selected consumer is stubbed. It bounds instructions, code/read/write ranges,
input size/counts and synthetic object/output/stack storage. Explicit host-driven
kind-byte variations are restored before final input/guard comparison; the
original file and other source fields remain unchanged.

Public tests cover raw identifiers, duplicate order, first-match/missing relations,
Japanese/surrogates, all classification bytes, malformed and maximum-length
names, stride/overlap failures, compression, constructor compatibility, privacy
and the existing HTTP/language/record handoff. Native tests skip honestly without
the pinned private executable or optional Capstone/Unicorn.
All 70 Nintendo-specific tests passed in 17.891 seconds, including ten new
targeted tests. An empty-working-directory run passed eight public tests and
explicitly skipped the unavailable-private-input native class.

The complete sixteen-table schema, remaining row meanings/crosslinks, authentic
catalog/media inputs, actual transport/authentication, original list/search/
detail/video rendering and submission flows remain unfinished. This extension
does not make the channel's service or browsing complete.
