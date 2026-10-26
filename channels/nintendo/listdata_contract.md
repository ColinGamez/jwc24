# Downloaded ListData records: partial native contract

October 26, 2026. This advances the [list-reference planner](list_references.md)
to selected actual records in the separately downloaded list buffer. It supplies
a bounded backend reader for original-order software titles and linked rows.
It does not supply a genuine catalog sample, replacement news/catalog content,
downloadable games, playable video, or a native browsing completion claim.

## Evidence and load connection

The original HATJ v1792 main DOL remains the private, fingerprinted input:
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
Its constructor diagnostic identifies `prmdata::ListData` and its maximum size.
Tracing the already recovered follow-on download caller gives this sequence:

1. At `0x80026950..0x80026984`, the returned bytes are either passed through the
   original LZ size/decompression helpers or copied into the configured output.
2. `0x80026990` calls `0x80032DC0` to install that buffer into a ListData object.
3. `0x80026998` calls `0x80032EC0` to check the installed object. A nonzero
   result enters an error path. Those anchors establish the actual subsequent
   consumer; they are not an unrelated filename or adjacent generic helper.

The new harness starts at the constructor with supplied raw synthetic bytes.
It executes the original constructor, selected validator and record accessors.
Real allocation, asynchronous completion, storage, decompression in this full
caller, transport/authentication and the surrounding application remain outside
this new harness. Earlier isolated native LZ tests remain separate evidence.

Targeted searches for the newly identified `ListData`, `prmdata` and `entj`
names in the selected private Nintendo index found no genuine channel payload
or matching service schema. The three `ListData` path hits belonged to unrelated
projects. This is a limitation of those searches and the selected index, not
proof that every archive in the collection lacks a sample. No secret, key,
personal-save or actual-Wii-backup material was accessed.

## Header and descriptors

The selected native gate is `0x800329A0`, called by `0x80032EC0`. It checks a
zero BE16 prefix, a format byte of at least six, a declared size in
`0x5E8..0x1FC7CC`, and sixteen descriptor offsets. Descriptors begin at byte
`0x25`, each containing BE32 count followed by BE32 offset, eight bytes apart.
The constructor installs a base/descriptor pair for each table.

The independent supported format is exactly byte value six. It additionally
requires actual and declared lengths to match and performs count-times-stride
and non-overlap checks using Python's non-wrapping arithmetic. The narrow native
gate does not establish those stronger guarantees. An out-of-buffer native
record read is trapped by the harness rather than reported as valid.

| Table index | Verified stride | Evidence and current decoder scope |
| --- | --- | --- |
| 0 | `0x22` | Native accessor `0x8002C050`; byte span checked, record semantics undecoded |
| 1 | `0x6C` | Native accessor `0x8002C610`; byte span checked, record semantics undecoded |
| 3 | `0xEC` | Native accessor `0x8002EFB0`; selected software/title fields decoded |
| 5 | `0x116` | Native validator's iteration at `0x80032F04..0x80032F5C`; selected links/fields decoded |
| 15 | `0xCE` | Native lookup at `0x80033160`; byte span checked, record semantics undecoded |

Other nonempty tables are retained as explicit undecoded table counts. Their
complete record lengths and contents are not validated or inferred from the
next table's location. Metadata keeps `unknown_table_record_bounds_checked`
and `complete_catalog_schema_checked` false.

No CRC meaning is assigned to the word at header offset eight. Changing it in
a synthetic fixture still passes this selected native consumer. This neither
establishes that the complete service lacks integrity/authentication nor makes
the word a proven CRC. The new component performs no CRC/signature check.

## Software titles and links

For table-three rows, the relative word at row offset `0x0C` is added to the
buffer base by native accessor `0x8002EC90`. Actual UI code at
`0x800AFA84..0x800AFA98` takes four bytes after that returned address as the
source for the native wide-character copy helper, with a 500-unit destination.
This corroborates a four-byte opaque prefix followed by a terminated UTF-16
title. The prefix's meaning is not invented.

The independent reader validates that reference and decodes strict UTF-16BE,
including surrogate pairs. A zero reference remains a missing title. It rejects
malformed text, references into known table storage and strings beyond the
local 499-code-unit-plus-NUL policy. Those stricter checks must not be described
as the narrow native gate rejecting the same data. The actual UI has additional
rendering behavior that is not exercised here.

Table-five word zero is a relative software-row reference. Native accessor
`0x8002F600` resolves it against the list base; a caller at
`0x800621A8..0x800621AC` immediately uses the result as software information.
The reader requires a nonzero reference to name an exact table-three row;
zero remains absent. Order is preserved, including links that name a different
row index than their own.

Other exposed table-five fields retain byte-offset names: BE16 at `0x04`,
BE32 at `0x06`, and bytes at `0x0A`, `0x0B`, `0x1A`, `0x1B` and `0x1C`.
The original validator bounds byte `0x0A` to ten and bytes `0x1B`/`0x1C` to
zero or one. Native scalar getters corroborate selected decoded values.
These are not guessed prices, availability flags, publication timestamps,
ratings or permissions to download/play content.

## Use and verification limits

```powershell
.venv/Scripts/python.exe tools/inspect_nintendo_listdata.py <private-list-file>
.venv/Scripts/python.exe -m unittest tests.test_nintendo_listdata
```

The read-only inspector accepts bounded raw/LZ10/LZ11 bytes and prints counts
and scope, without titles, opaque identifiers or copied data. The dataclasses
retain decoded titles for a future backend consumer while excluding them from
`repr` and metadata. Nothing is served to the channel.

Fifteen tests cover record order, cross-row links, Japanese/surrogate titles,
missing fields, count/offset/overlap failures, UTF-16 limits, unknown tables,
compression bounds and metadata-only bounded CLI reads. The guarded original
execution compares software pointers, actual native title copies, software
links and scalar getters; it also exercises native enum/boolean rejection and
separates local policy failures from native acceptance. No SDK helper is
stubbed in these executed constructor/validator/accessor/copy paths.

The harness pins the DOL, limits code/read/write ranges and instructions, and
checks object, input, output, published synthetic pointer and stack guards.
Its local test cap is 64 KiB and 64 decoded rows, separately from the native
maximum and the independent decoder's byte bounds. Native tests skip without
the private original or Unicorn. A successful synthetic comparison is not
evidence of a genuine catalog, completed download, trusted signature or native UI.

## Remaining restoration work

Recover the other descriptor strides/record meanings, title-prefix and identifier
contracts, software-detail and media relationships, filtering/ranking behavior,
integrity/authentication and freshness. Find and independently validate a genuine
sample with provenance. Connect the real load path and original list/search/detail
UI only once those requirements are met. Review/bookmark submissions and video
codec/playback remain separate unfinished work.
