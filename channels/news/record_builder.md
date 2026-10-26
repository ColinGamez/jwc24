# Explicit native News record generation

October 26, 2026. `jwc24/news_records.py` now builds actual decompressed native
buffers from structured records. This fills the gap between a future authorized
provider adapter and the existing [signed publication path](publication.md).
It does not select/acquire a provider, supply articles or create editorial facts.

## Format and evidence

The layout comes from the separately attributed [format investigation](format.md):
the Japanese HAGJ v7 validator corroborates the header and five record tables;
the headline/ticker table is separately corroborated by the public WiiLink
generator. The independent builder writes all six tables, aligned data,
UTF-16BE text with explicit terminators, byte lengths and CRC32 over bytes 12+.
The independent structural inspector must accept the completed output.

Original-code tests execute the complete existing validator/CRC on 24 supplied
copies of a generated all-table snapshot and a snapshot with explicitly absent
source/location/image references. Both return zero, with no pruned topic links
and intact guards. Time/calendar services are mocked as in the earlier harness;
image decoding, signature trust, IOS downloads and native rendering do not run.
Repeating a snapshot for a test is not evidence of actual hourly coverage.

No source names, copyright, categories, coordinates, dates, article IDs, ticker
text or pictures have defaults. Opaque fields are also required explicitly;
their widths are known, but their complete meanings remain unverified. They
must come from a documented format/source decision, not a guessed value to
make the encoder pass. Input evidence/rights references are caller assertions,
not proof of Nintendo provenance or permission to redistribute an article.

## Structured input contract

`encode_news_records(document)` accepts an ordinary Python dictionary. The
command-line builder reads the same structure from bounded UTF-8 JSON, rejecting
duplicate fields, nonstandard numbers, missing fields and unknown fields.
The exact top-level fields are:

| Field | Required value |
| --- | --- |
| `schema_version` | Integer 1 |
| `evidence_ref`, `rights_ref` | Explicit nonempty bounded references; retained privately by the build command |
| `header` | Object described below |
| `topics`, `articles`, `sources`, `locations`, `images`, `headlines` | Explicit arrays, each at most 4096 entries |

Header fields are `version`, `updated_timestamp`, `close_timestamp`,
`secondary_timestamp`, `country_code`, `language_code`, `supported_languages`,
`flags_45_46`, `byte_47`, `opaque_21_23`, `opaque_92_95` and `server_message`.
Timestamps are the supplied native minute words, not Unix seconds. The encoder
does not take the current clock or retime anything. Opaque byte ranges use exact
hexadecimal text; the two explicit boolean-width flags remain separate. The
supported-language array retains supplied order and gets its wire terminator/
padding; no additional language is inserted. `server_message` must be explicit
text or null, with no generated maintenance/error copy.

| Record | Exact fields |
| --- | --- |
| Topic | `name`, `article_links`; each link is `[snapshot_timestamp, article_identifier]` |
| Article | `identifier`, `source_index`, `location_index`, `picture_timestamp`, `picture_index`, `published_timestamp`, `updated_timestamp`, `title`, `body` |
| Source | `logo_flag`, `position`, `reserved_u16`, `picture`, `name`, `copyright` |
| Location | `name`, `latitude_word`, `longitude_word`, `country_code`, `region_code`, `location_code`, `zoom_byte`, `opaque_padding` |
| Image | `credit`, `caption`, `picture` |
| Headline | A supplied text string |

The safe producer subset requires an explicit latest-topic entry at index zero.
Only that entry may have a null name. It does not create or translate category
names. Article title/body are nonempty; missing body is rejected, not replaced
with a headline, URL, AI summary or boilerplate. Leading/trailing whitespace,
line breaks, Japanese text and surrogate pairs are preserved. Embedded NUL and
malformed UTF-16 reject. Bodies reaching 20000 encoded bytes reject instead of
being silently pruned. These are declared producer policies, not a claim that
the original validator applies all the same text checks.

Optional article indices use explicit null for the native `0xFFFFFFFF` sentinel.
No picture uses timestamp zero and null index. Cross-snapshot references remain
explicit and must resolve in the later 24-buffer graph validation. No automatic
article-ID assignment or duplicate-reference repair is performed.

Picture objects require exactly `encoding: "native-image-bytes"` plus
`data_base64`. These are supplied already-encoded image bytes, not a URL or an
instruction to synthesize/download/convert an image. The encoder does not
establish that the original image decoder accepts them. Source logo flag zero
requires supplied picture bytes; other supplied flags require null picture.
Signed latitude/longitude words are preserved as native integers; the builder
does not infer a geographic location or convert arbitrary degrees. The three
opaque location padding bytes must also be supplied explicitly.

## Private build and publication handoff

```powershell
.venv/Scripts/python.exe tools/build_news_records.py `
  --input private/news/authorized-records.json `
  --output-dir private/news/builds/explicit-new-snapshot
```

The new output directory contains `news.raw` and a private manifest with input/
output hashes and the caller's evidence/rights references. Validation finishes
before staging. The complete directory appears with one same-volume rename;
an existing build is not replaced. Failed staging leaves no activated or partial
build. Reports omit article text, credits, coordinates, source/rights references
and paths. The command neither signs nor serves its output.

Supply each genuine snapshot deliberately to the existing publication config;
its input path can name this build's `news.raw`. The signer then checks the
complete 24-file graph, locale, signature key and current windows before serving.
No command automatically fills missing hours or duplicates one file 24 times.

Tests exercise structured records through encode, compression/signing with
generated keys, immutable publication, reload and a real loopback HTTP download,
then independently decode exact original text and dates. Synthetic articles and
opaque synthetic image bytes remain confined to tests and are never installed
or published as production content.

An authorized actual provider schema/sample, correct native genre and geography
mapping, licensed image encoding/attribution, time-slot scheduling, installed
client trust, VFF capacity, and original UI remain completion gates.
