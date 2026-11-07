# Original News body and source-credit text consumers

November 7, 2026. This adds an original-code check of the native article body
and source copyright pointers, their separate text-object handoffs, and a bounded
UTF-16 character-setup region. It advances the handoff investigation for actual
licensed source candidates without changing the original UI or publishing an
article. It does not establish working hyperlinks, HTML/rich-article support,
complete layout/rendering or provider attribution compliance.

## Original evidence

The immutable Japanese HAGJ v7 executable is pinned by SHA-256
`8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852`.
Original bytes and disassembly remain private. The existing complete
[article constructor](headline_model.md) at `0x8000FA38` resolves the selected
wire article and retains these fields:

| Model offset | Native wire reference |
| --- | --- |
| `+0x20` | Article title offset at article row `+0x20` |
| `+0x24` | Article body offset at article row `+0x28` |
| `+0x28` | Source name offset at source row `+0x10`, when present |
| `+0x2C` | Source copyright offset at source row `+0x18`, when present |

The independent harness compares both exact wire-derived pointers and exact
caller-supplied synthetic text. Equal duplicate text elsewhere is insufficient
to establish the source-name pointer's provenance. An explicitly absent source
keeps source-name and copyright model pointers null; no substitute is generated.

The original article layout suffix `0x800331CC..0x80033278` passes title, body
and copyright to three calls of text formatter `0x80027F94`. The actual loads
occur at `0x800331F4`, `0x80033210` and `0x8003326C`. The three text-object
pointers come from separate globals. Thus the source copyright has its own
original native text path; it is not necessary to repurpose a menu control or
replace the article screen merely to supply that field. Appropriate placement,
visibility, capacity and legal sufficiency still require native UI evidence.

The formatter prefix stores its text pointer at text-object `+0x14`, calls the
original UTF-16 length helper at `0x801881BC`, and records code-unit count plus
terminator. The original loop `0x800280D0..0x80028204` visits each 16-bit unit,
calls the original grouping/line-break helper `0x800278A0`, and fills rows with
stride `0x70`. A line feed follows a distinct branch and bypasses the ordinary
glyph-width lookup. U+00A0 is converted to U+0020 in the glyph row. The source
buffer itself remains unchanged. The final zero-unit row is also checked.

## Executed scope and explicit scaffolding

`tools/verify_news_article_text.py` performs three separate bounded executions:

1. The complete original article-model constructor and its original string
   helpers. Only allocation is replaced with a bounded guarded synthetic heap.
2. The actual three-call layout suffix, beginning with explicitly supplied
   synthetic model/register/float context. Formatter calls are observed at their
   boundary, not executed in this stage. The larger layout method, its earlier
   branches and epilogue are outside this check.
3. The original formatter prefix beginning at `0x80028000`, all UTF-16 unit
   iterations and grouping helper, through the final zero-row setup stopping
   at `0x80028250`. Earlier prologue/context setup, later width aggregation,
   wrapping/layout, image handling and final renderer are outside this check.

Text objects, their pointers, glyph storage, font object/vtable and position
inputs are synthetic. Font width/height methods return explicit caller-supplied
integers. Grouping mode zero, zero color/spacing and the three text-object
globals are explicit bounded synthetic BSS context. Original lookup tables and
constants come from the pinned source; no original instructions or string/
grouping operations are patched. The emulator's floating-point execution bit
is enabled for the observed ordinary float instructions. No unsupported paired
save/restore prologue instructions are skipped or claimed executed: execution
starts inside the declared formatter prefix and stops before its epilogue.

The harness checks allowed control flow, bounded reads/writes, instruction caps,
guards around all synthetic regions/allocations, exact glyph code units and
unchanged raw input. An intentionally undersized glyph buffer traps the actual
original write; it is not an accepted payload. An out-of-range body offset is
rejected before dereferencing its expected text. These consumer checks do not
run the separate full buffer validator or signature path.

Local harness limits are one synthetic article, a 64 KiB raw buffer, 4,096
UTF-16 units per expected string and bounded synthetic font metrics. They are
tooling limits, not original channel capacity claims. A supplementary scalar
such as an emoji is two UTF-16 units in these checks, not proof of a correct
native glyph. The existing producer's separate 20,000-byte article-body limit
and full graph/publication checks remain in force.

## What this says about source attribution and full articles

Synthetic literal HTTPS URLs and `<a ...>` markup reach the character rows as
ordinary units in the observed region. This is evidence of plain-text handling
here; it does not make URLs clickable, prove no other original link mechanism
exists, or license sending an HTML article directly to this formatter. No link
activation path was recovered in this bounded pass.

For [Global Voices source candidates](globalvoices_source.md), the genuine
article body, original author, Japanese translator, source identity, license,
links, modification dates and third-party components remain separate source
records. This harness supplies no combined attribution prose and does not
rewrite or flatten an actual article. The following handoff decisions remain:

- Preserve genuine paragraphs, headings, quotations, captions and attribution
  without silently deleting substantive structures. Plain UTF-16 paragraphs
  with line feeds have an original path; typography, wrapping and media need
  the actual font/layout/rendering and component-rights decisions.
- The real source name can use the original source-name path. Source copyright
  has a separate original text path. Putting author/translator/license details
  there alone does not prove the publisher's requested attribution placement.
- Article/source/license URLs represented as visible text are not automatically
  usable links. Actual original link capability and suitable attribution must
  be established before declaring that provider ready. No original control is
  reassigned to open a replacement screen.
- Any added attribution or rendering-change disclosure must be explicit source
  adaptation, not falsely represented as the author's original prose. No
  automatic preface, summary, truncation or invented editorial metadata exists.

Native source-credit layout/capacity, fonts, complete body wrapping/rendering,
image support, source/license-link behavior, component rights, provider coverage,
native IDs/genres/geography, genuine hourly scheduling, signatures, IOS/VFF and
original UI testing remain completion gates.

## Verification

```powershell
.venv/Scripts/python.exe -m unittest tests.test_news_article_text -v
```

The native class skips without the pinned private executable or optional
Capstone/Unicorn packages. Public tests contain synthetic strings only. Reports
return counts and scope booleans, never story text, credits, URLs, original code,
credentials or local paths. No emulator profile, installation, owner backup,
network route or production article was changed.
