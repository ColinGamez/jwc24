# HCHJ v512 native response contract: partial trace

Static inspection of the privately extracted ordering executable on 2026-10-13.
This initial static trace has since informed offline fixtures. Startup document
responses were accepted in Dolphin after correcting the XML framing and CDATA;
municipality navigation remains unverified in the native channel.

## XML navigation semantics

`0x800C4538` searches the direct children of the supplied parent node. With a
null parent argument it uses the artificial document node, whose immediate
child must be the actual `response` XML root. It iterates
children, obtains their names, and compares those names. Therefore the area
parser's parent arguments provide stronger hierarchy evidence than adjacent
string literals alone.

`0x800C43E0`, used by status validation, is broader: it checks the current node,
later siblings, and recursively visits children. A tag found by this function
does not establish a specific direct-child hierarchy.

## Status validation

The shared validator requires HTTP status 200 at `0x800EE114`. At
`0x800EE18C` it searches for `apiStatus` using the broader navigation helper.
Within that context it searches for `version` at `0x800EE1B4`; this field is
optional in this code path and, when text is present, is passed to a separate
version handler.

It searches for `code` at `0x800EE1F0`, requires a node and text, then converts
the text to an integer at `0x800EE20C`. Code 0 clears the error fields and returns
success (`0x800EE218`–`0x800EE228`). Missing status, code, or code text follows
an internal error path returning 99. Codes 96 and 97 receive dedicated handling.
The actual XML root must be `response`; an extra wrapper failed native startup.
The custom lexer ignores ordinary PCDATA. Nonempty scalar fields must use CDATA.
Non-ASCII conversion and the version handler's full accepted range remain
unverified.

## Proven area hierarchy

### Initial prefecture selection (corrected 2026-10-15)

The root request does not enter either nested-list consumer below. State0x7C
routes via0x9D to0x85, callback `0x800D8844`. This callback finds direct
`response/areaList` (`0x800D88A0`, `0x800D88F4`), allocates from its child count,
and requires direct `segment` text on every child (`0x800D8A2C`). It uses the
child element name as the selection code (`0x800D8AC0`). Thus the root shape is
`response/areaList/<selection-code>/segment`, without a container/list wrapper.
The previously served nested fixture lacked segment on container0 and was
incompatible with this route. The root producer and HTTP tests now distinguish
this contract from later nested lists. This static correction still requires
live confirmation against the reported334011 failure.

### Prefecture click continuation (corrected October16)

`0x800D8E98` saves the selected root element name at scene+0x610, then calls
`0x800F9058` with literal `0` (`0x800D8F44`) and continuation0x89.
Thus it requests the root response again, not a per-prefecture response.
State0x89's callback `0x800DB1D0` finds response/areaList, then the selected
element (`0x800DB2D0`). It requires that element's segment (`0x800DB324`) and
list (`0x800DB394`); each list child requires areaName (`0x800DB4AC`) and
areaCode (`0x800DB508`). The prior segment-only root omitted this list and
therefore selected a missing-field path. Its loaded constant at r2-0x7270 is95.
This explains the observed request sequence root -> root -> inquiry_done;
the inquiry is an error report, not the missing municipality request.

The root producer now embeds source-backed municipality rows for every
prefecture when postal data is enabled. Municipality IDs use M plus five JIS
digits. `0x800F9058` reads a bound of11 at r2-0x72B0 and copies at most10 bytes;
the old TEST-M-10202 was truncated to TEST-M-102. The offline verifier executes
the actual wrapper and URL-builder instructions with mocked libc and HTTP
submission to prove both the old truncation and preservation of new codes.
It makes no network requests and does not prove native rendering.

Two area display paths were traced:

| Native path | Required direct-child lookup sequence | Other observed fields |
| --- | --- | --- |
| Function beginning `0x800D756C` | Document root → `response` → `areaList` | `kanji1`, `kanji2`, `kanji3` are searched recursively beneath this `areaList`; their returned strings are checked before concatenation |
| Function beginning `0x800D7E90` | Document root → `response` → `areaList` | A recursive `kanji1` search supplies the heading; the parser iterates every direct `areaList` child and requires a direct `list` under each iterated child |

For the first path, the `response` lookup is at `0x800D75D4`, the nested
`areaList` lookup at `0x800D7628`, and the three address-name lookups at
`0x800D767C`, `0x800D7690`, and `0x800D76A4`.

For the second path, the corresponding lookups are at `0x800D7EF8` and
`0x800D7F4C`; `kanji1` is looked up at `0x800D7FA0`. Iteration begins at
`0x800D8144`. The nested `list` lookup passes the current area child as parent
at `0x800D81C4`. Its list children are then iterated at `0x800D8220` and passed
to the shared row parser at `0x800D8260`.

The shared allocation helper `0x800F8274` finds `response`, then reads
`areaCount` as a direct child within that context and converts it to an integer.
The examined display path rejects zero as well as negative results; a positive
count is required for allocation. Another helper,
`0x800F8474`, skips children named `container0` and requires `segment` on the
other children it handles. These observations do not yet establish every
allowed container name, row field, or count-to-row consistency rule.

## Shared rows and section headers

The row parser called at `0x800D8260` is `0x800F8594`, with variant argument
2. It initializes a field-name table from pointers at `0x803461D0`; those
pointers resolve to `kanji1` through `kanji4`. For variant 2, the primary field
is `kanji2`, the secondary field `kanji3`, and the tertiary field `kanji4`.
These are direct children of each list row. The primary node is required;
the secondary node is checked when primary text exists, and the tertiary node
is checked when secondary text exists. Missing text can select a native fallback
label, so an empty element and a missing element have different behavior.

After label construction, the following fields are required on the row:

| Field | Evidence | Native handling |
| --- | --- | --- |
| `areaCode` | Text lookup at `0x800F8D50` | Opaque byte string copied up to 15 bytes plus NUL at `0x800CCBB8`–`0x800CCC40`; no integer conversion here |
| `isNextArea` | Text lookup at `0x800F8D78` | Integer conversion at `0x800CCC74`; true only if the converted value equals 1 |
| `display` | Text lookup at `0x800F8DA0` | Integer conversion at `0x800CCC98`; true only if the converted value equals 1 |

The parser rejects a null result from each of these three text lookups. The
boolean conversions do not enforce a 0/1 input range in this code path. An offline
inspector should distinguish a strict producer policy from native acceptance.

The displayed row label passes through bounded UTF-16 conversion and concatenation,
then `0x800CCA90` copies at most 31 UTF-16 units plus a terminator. The exact
conversion-error and suffix branches remain unsuitable for a blanket
"every source name must be 31 characters" rule; this is the final label capacity.

The section-header helper `0x800F8474` checks the iterated area's element name.
A child named `container0` produces no section heading. Other handled children
require `segment` text, converted with an eight-unit output setting at
`0x800F8528`. The initializer `0x800CDCA4` independently copies up to eight
UTF-16 units plus a terminator. The value 6 passed to that initializer is a style
argument, not a six-character limit.

The caller still looks up and iterates `list` beneath `container0`; skipping its
heading does not skip its rows. Consequently a supported inspection shape is
`response/areaList/<container>/list/<row>`, with the names of ordinary containers
and row elements not constrained by these iteration loops. Each ordinary container
needs `segment`; `container0` is exempt from that heading requirement.

The heading lookup uses `0x800C4784`, which calls the recursive child search
`0x800C45EC`. This is different from the direct text getter `0x800C46A8` used
for row fields and section headings. The recursive name search explains why
`kanji1` need not be a direct `areaList` child: placing it there would make it
participate in the container loop and consequently require its own `segment`
and `list`. An inspector must not exempt direct `kanji1` elements from that loop.

Private follow-up disassembly is retained in `area-row-full.private.txt` and
`area-row-fields.private.txt`, without publishing the original executable.

## Count and allocation consistency

`areaCount` counts allocated row records, not section headings or only visible
rows. At `0x800F8334` the parsed count is stored for the selected variant;
`0x800CC998` multiplies it by `0x70` to allocate that many row slots. For
variant 2, the count is at state offset `0x468` and the allocated pointer at
`0x438`.

The container loop maintains separate counters for rows, headings, and layout
positions. Every direct child of each container's `list` consumes one row slot:
`0x800D82A8` advances the destination by `0x70`, and `0x800D82AC` increments
the global parsed-row counter. This occurs irrespective of the row's `display`
value. An odd layout position can receive alignment padding at
`0x800D8230`–`0x800D8238`, but that padding does not increment the row counter.
Heading allocation separately counts direct `areaList` children, subtracting
each child named `container0`, and allocates heading records of `0x24` bytes.

The native row-capacity check at `0x800D82BC` runs before entering a container's
row loop. It does **not** run before every row within that loop. A single
container containing more rows than the declared remaining capacity can
therefore overrun the row allocation. The native code also does not perform a
final equality check between allocated and parsed rows.

For a safe producer or offline inspector, require a positive `areaCount` equal
to the total number of direct children of every container's `list`, including
rows with `display` set to 0 and rows beneath `container0`. This exact-equality
rule is an inspection/production policy derived from the allocation and loops,
not a claim that native code enforces it. Container count, heading count, and
layout-padding count must not be substituted for this row count.

The allocation and loop trace is preserved privately as
`area-count-allocation.private.txt`.

## Entry and fallback state `0x7C`

A bounded caller trace distinguishes several state fields that happen to use
the value `0x7C`; they must not be treated as one universal state enum.

The address-related worker at `0x800CF360` reads a buffer from global object
offset `0x388`, then offset `0xC0` within that object. It prepares request text
at `0x800CF3D4`–`0x800CF404` and submits it through `0x800F90E0`. After the
response is parsed, API status codes 13 or 14 cause the worker's result field
at offset `0x1C` to receive `0x7C` (`0x800CF4F0`–`0x800CF4F4`). This is a
fallback signal from address lookup, not evidence that a real postal address
must be submitted to obtain the first area list.

The area-row selection handler at `0x800D8684` supplies another entry: when
the selected row's `isNextArea` and `display` bits are both false, it writes
`0x7C` to the area's state field at offset `0x0C` (`0x800D87AC`–`0x800D87B4`).
It then clears six cached area variants through `0x800F75AC` and
`0x800F7604`. This provides a native route back to area selection without
requiring a postal downloader in that handler.

An unrelated outer state-machine write at `0x800ABB34` stores `0x7C` at
offset `0x10`; its preceding UI-result check differs from the area handler.
No isolated-profile startup has yet verified whether the area-root route is
reachable with no personal-data save. Such a test must preserve the real save,
use an isolated profile, and observe the native request rather than fabricate
an address or change the executable's state in memory.

Private caller evidence is retained in `state7c-entry.private.txt` and
`state7c-xrefs.private.json`.

## Not yet established

- Which area-list action variant is called first during startup.
- Exact action parameters and request method for each display path.
- The XML document wrapper and accepted `version` values.
- Other row variants, numeric-converter edge behavior, and
  valid empty results. The variant-2 fields above are traced, but no universal
  area-response schema is claimed.
- Whether the observed variants correspond to prefecture, city, town, or another
  selection level; their UI roles must be traced rather than inferred from names.

The offline inspector now checks the recovered response/areaList structure,
recursive heading-name lookup, a positive mandatory direct `response/areaCount`
for the list variant, and every direct container's `list` plus `segment`
requirement (with the `container0` heading exemption). Ambiguous heading matches
are rejected as an inspector policy; this is stricter than the native first-match
search. Variant-2 row-field presence and conditional name-node requirements
are now checked from the evidence above. Numeric flags use the inspector's
strict nonnegative integer policy; native integer conversion is more permissive.
These checks do not yet justify serving an invented XML success response to the
native channel.

## Offline inspection

`tools/inspect_demae_response.py FILE --variant address` checks HTTP status,
the recursive status lookup, direct `response/areaList` hierarchy, and the
three address-name fields. `--variant list` checks the heading and container
hierarchy and requires a positive direct `response/areaCount`; it also checks
variant-2 row fields. For the address variant, `areaCount` is checked
when present; its necessity in that variant remains unresolved.

The inspector requires UTF-8, rejects DTD/entity declarations, duplicate
required fields, invalid integers, oversized input and excessively deep trees.
Its limits and stricter ambiguity checks are tooling choices, not recovered
native limits. Output contains counts and scope only, without address text.
A passing report is not evidence of native acceptance or authenticity.

`--variant postal-fallback` checks the separately traced direct
`response/apiStatus/code` hierarchy and accepts only status 13 or 14. This is
an intentional fallback response role, not a successful address lookup. The
private fixture builder emits status 13 without fabricated `selectedArea` data.

`tools/build_demae_area_fixture.py` creates a private 47-prefecture XML fixture
and validates it before atomic publication. Its wrapper is explicitly
`offlineFixture`, and its area codes start with `TEST-`; these are synthetic
test identifiers, not recovered native codes. It is not registered with the
server or served to Dolphin. The declared count equals fixture rows as a
safe producer rule based on the traced allocation and container-loop guard.
Source area codes over 15 UTF-8 bytes are reported as truncation risks; the
native code-page behavior has not been established. No source label is truncated
by the inspector, which does not emulate the native display conversion.

Private evidence includes `area-parser-disassembly.private.txt`,
`area-record-helpers.private.txt`, and the protocol reference inventory in
`private/demae/frontend-v512/`. This note publishes instruction addresses and
findings only, without copied executable bytes or personal addresses.
