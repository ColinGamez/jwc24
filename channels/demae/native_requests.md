# HCHJ v512 native request construction

Read-only static inspection of the supplied ordering frontend. The main DOL is
decompressed privately at `private/demae/frontend-v512`. No original endpoint
was called, title launched, address supplied, or order placed.

## Confirmed tables and area-list variants

The action table begins at raw file offset `0x323CA0`, runtime address
`0x80327BA0`. Records are 72 bytes: an action index at offset 0, a string at
offset 4, and a parameter count at offset 68. The URL builder directly uses the
string and count (`0x8002C2FC`–`0x8002C314`, `0x8002C3F8`–`0x8002C404`).

The parameter table begins at raw offset `0x3243A8`, runtime `0x803282A8`, with
the same stride. Its name is at offset 4; offset 68 controls additional bracketed
values. A zero there means an ordinary scalar name in the inspected builder.

| Action index | Table action | Count | Confirmed parameter mapping |
| --- | --- | --- | --- |
| 0 | `webApi_area_list` | 0 | No action-specific parameters in this row; a caller may supply extra parameters. |
| 1 | `webApi_area_list` | 1 | Parameter ID 0, `areaCode`. Wrapper starts at `0x800F9058`; call at `0x800F90CC`. |
| 2 | `webApi_area_list` | 1 | Parameter ID 5, `zipCode`. Wrapper starts at `0x800F90E0`; call at `0x800F91C4`. |

The area-code wrapper copies its caller's byte string into a temporary buffer
and terminates it. Its copy limit comes from a constant that has not been
resolved in this pass. The postal wrapper copies up to seven non-NUL bytes and
terminates them. These wrappers establish the names and copy behavior, not the
allowed server values, hierarchy, or interpretation of the area codes.

## Confirmed URL construction

The scalar URL builder starts at `0x8002C274`. Its eighth argument controls the
scheme: nonzero copies `https://`, zero copies `http://`
(`0x8002C2AC`–`0x8002C2E4`). The two area-list wrappers pass nonzero.

It appends the embedded host/path `nwapi.demae-can.com/nwapi.php?action=`,
the action string, and `&platform=wii` before processing parameters. The relevant
append calls are at `0x8002C2F8`, `0x8002C314`, and `0x8002C320`.
For each scalar parameter it appends `&`, the selected parameter name, `=`, and
the supplied value. The parameter lookup and appends occur at
`0x8002C354`–`0x8002C374` and `0x8002C3D4`–`0x8002C3E8`.

Thus the two confirmed wrapper shapes are:

```text
https://nwapi.demae-can.com/nwapi.php?action=webApi_area_list&platform=wii&areaCode=<caller byte string>
https://nwapi.demae-can.com/nwapi.php?action=webApi_area_list&platform=wii&zipCode=<up to seven caller bytes>
```

These are static formatting templates, not requests sent during research.
The inspected scalar appends do not perform percent encoding themselves;
upstream value preparation and handling of reserved characters remain unresolved.

The loop uses the action's stored parameter count plus the caller's seventh
argument, allowing extra parameters (`0x8002C3FC`). Both area wrappers pass zero
extra parameters. Nonzero parameter-table flags cause bracketed value handling
in `0x8002C37C`–`0x8002C3D0`; those forms need a separate contract trace.

## Request method evidence and remaining limits

The completed URL is passed to `0x8002CD60` at `0x8002C42C`. That function calls
the request-creation wrapper `0x80247644` with method argument **0**, set at
`0x8002CDEC` before the call at `0x8002CDF4`. The wrapper forwards this through
`0x80246FBC` into request construction at `0x80242434`, which accepts method
indices 0 through 2.

Further tracing confirms **method 0 emits GET**. The constructor stores the
method in request offset `0x1C` at `0x8024297C`. The request-line writer reads
that field at `0x80245EA8`: 0 selects the four bytes `GET ` at `0x80245ED0`,
1 selects `POST ` at `0x80245EE4`, and 2 selects `HEAD ` at `0x80245EF8`.
The GET string is at `0x80471310`, addressed as `r13 - 0x7350`; startup sets
`r13` to `0x80478660` at `0x80006314`. This establishes the wire-method mapping
from the native request-line writer, rather than inferring GET from the query.
Derived method-writer disassembly remains private in
`http-method-writer.private.txt`.

Other unresolved items include bootstrap-to-area-list call order, the meaning
of an empty area-list request, valid codes and their parent/child rules, response
status requirements, authentication/header behavior, and the extra/bracketed
parameter formats. No replacement response or successful frontend integration
is claimed by these request findings.

## Area-list caller follow-up

A direct-branch scan finds **14 calls** to the area-code wrapper and **one call**
to the postal wrapper. Derived caller disassembly is kept privately in
`area-wrapper-callers.private.txt`; these counts do not cover indirect calls.

Several initialization/retry paths request **`areaCode=0`**, not an empty value.
The passed constant is the literal byte string `"0"` at `0x802DB25E` and other
equivalent constant locations. Confirmed direct root calls are:

| Call address | Confirmed state transition or condition |
| --- | --- |
| `0x800CF850` | Fallback branch after initial state/selection tests; requests `"0"`, stores wait state `0x9D`, continuation `0x85`. |
| `0x800CF898` | Current state `0x7C` triggers the same root request, wait `0x9D`, continuation `0x85`. |
| `0x800D0004` | Entry helper requests `"0"`, sets state `0x9D`, continuation `0x85`. |
| `0x800D0114` | Conditional re-entry path requests `"0"`, sets state `0x9D`, continuation `0x85`. |
| `0x800D86FC` | Mode field at scene `+0x72C` equals 1 and scene pointer `+0x434` is absent; requests `"0"`. |
| `0x800D8F48` | Selected record code differs from scene code; refresh path requests `"0"`. |
| `0x800DB9DC` | Mode field equals 1 and scene pointer `+0x430` is absent; requests `"0"`. |

Selection paths also issue area-code requests with values stored in the scene:
`0x800D7DD0` uses scene `+0x630`; `0x800DAA18` uses `+0x620`;
`0x800DAABC` and `0x800DC270` use `+0x650`; `0x800DBA50` and
`0x800DBAA8` use `+0x620`. At `0x800D877C`, a selected record is addressed
as `base + selected_index * 0x70`; its code string at record `+0x60` is copied
to scene `+0x630` before the request. Similar copying from selected record
`+0x60` to scene `+0x620` occurs before `0x800DBA50`. These establish that UI
selection can request children of a stored code. The exact geographic level
associated with every scene field remains unresolved.

The one direct postal call is at **`0x800CF410`**. Its preceding code takes
data from a global object at `+0x388`, then source offset `+0xC0`, passes it
through `0x800F769C` into two temporary strings, terminates the first at three
bytes, and joins them with `%s%s` before calling the seven-byte postal wrapper.
The caller then waits for request completion (`0x800CF448`), checks the result,
and supplies the returned body to the response parser (`0x800CF494`). This
establishes a postal-derived area-list path. The source field's ownership and
the precise helper transformations still need tracing; no personal values were
read or published in this static pass.

The caller observations strengthen `areaCode=0` as a real native root-list
request and demonstrate postal versus stored-code selection variants. They do
**not** yet prove the global `/startup` → first area-list ordering, that the UI
always takes one variant first, or a complete geographic hierarchy. A successful
fixture inspection is separate from native frontend acceptance.

## Postal-result prerequisites before the root fallback

The root call at `0x800CF850` is part of the same worker beginning at
`0x800CF360` that sends the postal request at `0x800CF410`. In this particular
worker, the established order is:

1. Wait for an earlier request to stop being busy, clear the parser, and send
   the postal-derived area-list request.
2. Wait for its completion at `0x800CF448`, check the result at `0x800CF45C`,
   and parse the returned body at `0x800CF494`.
3. Read the API status through `0x800F8E64`; the successful data branch requires a
   present status value that converts to zero (`0x800CF498`–`0x800CF580`).
4. Require `selectedArea` (`0x800CF594`) and its `areaCode`
   (`0x800CF5E4`). Missing either follows the worker's error path; it does not
   automatically retry the root list.
5. If the selected code is exactly 11 bytes, take a separate path at
   `0x800CF6F4`–`0x800CF740`. Its full meaning is unresolved.
6. Otherwise classify the returned area-list structure through `0x800CFBE8`.
   This helper requires `response` and `areaList`, iterates `list` nodes, and
   compares selected row fields. A negative result is an error. Results 1,
   2, and 3 select states `0x8D`, `0x91`, and `0x99`; the remaining result
   requests `areaCode=0` at `0x800CF850` and selects continuation `0x85`.
7. The root request's wait/result/parse sequence is at
   `0x800CF8F0`–`0x800CF93C`; only afterward does it copy the continuation into
   the active state at `0x800CF940`–`0x800CF944`.

The selected-code string and hierarchy fields are not mapped to geographic
levels in this pass. A root-list fixture may satisfy a standalone root parser
while still lacking the `selectedArea` required by this postal-result path.
Those are different response roles and must be tested separately.

This settles a **postal-result → conditional root fallback** sequence, not the
entire title startup. The other direct root path at `0x800CF898` is gated by
state `0x7C`; tracing how every entry sets that state and how `/startup`
connects to this worker remains outstanding. No native success is claimed.

## Exact postal lookup and hierarchy classifier semantics

The status helper `0x800F8E64` first finds a direct document child `response`,
then its direct child `apiStatus`, then the direct `code` child and its value.
These searches use the nonrecursive helper `0x800C4538` and direct-value helper
`0x800C46A8`. A nested arbitrary `apiStatus` is not equivalent for this helper.

The successful postal-data path has different lookup semantics:

- `selectedArea` is searched **recursively from the document tree** at
  `0x800CF594`. Helper `0x800C45EC` starts from parser root pointer `+0x4328`
  when its parent argument is zero, tests each child, and recursively descends
  into it at `0x800C466C`. It is not restricted to a direct child of `response`.
- `areaCode` is then searched **recursively beneath the found selectedArea**
  through `0x800C4784` at `0x800CF5E4`. That helper returns the matched node's
  value pointer. A missing node or null value follows the caller's error path.
- The caller copies at most 32 bytes of the returned code into a temporary
  buffer and measures that copied length. It does not independently enforce
  that the copied bytes are decimal digits. A nonnull empty value pointer would
  produce length zero; whether the XML parser represents an empty element with
  such a pointer or a null pointer remains unresolved. Do not assume `<areaCode/>`
  is an accepted representation.

The classifier at `0x800CFBE8` finds direct document child `response`, then
direct child `areaList`, then its `list` nodes. For each row it looks up the
four direct fields **`kanji1`, `kanji2`, `kanji3`, `kanji4`**, in that order
(field-name pointer table `0x802DB228`). It starts with depth 4 and reduces the
depth at the first missing value or first difference from previously observed
values. At zero it stops. The helper returns the common-prefix depth (0..4),
or a negative failure if required outer containers are absent. Empty text and
whitespace normalization depend on parser behavior and are not resolved here.

The caller maps depth 1 to state `0x8D`, depth 2 to `0x91`, and depth 3 to
`0x99`. Other nonnegative depths take the `areaCode=0` fallback. This explains
how returned rows select a hierarchy UI state, without assigning an unverified
geographic meaning to each kanji level.

For an exactly 11-byte selected code, the caller bypasses this classifier. It
copies the code into a global object's field `+0x74` through `0x800BB48C`,
selects global object slot 2 through `0x800BCE30`, converts the code with a
base-10 numeric helper via `0x800BE868`, stores a two-word result, and copies
two additional source words via `0x800BE7C0`. It selects state **`0x75`**.
No network request is issued inside that branch. What the next dispatcher does
with state `0x75` remains unresolved; the code length alone is not proof that
it is a restaurant ID, delivery order, or final geographic level.

## Native postal status fallback

The postal worker explicitly recognizes status code **13 or 14** before the
selectedArea gate. At `0x800CF4E4` it subtracts 13 and tests the unsigned result
against 1. Either code stores state `0x7C` at `0x800CF4F4`, jumps to
`0x800CF86C`, and reaches the root `areaCode=0` request at `0x800CF898`.
This is a concrete native fallback path; selectedArea is not required on that
branch. A structurally valid `response/apiStatus/code` containing 13 or 14 is
therefore a useful **offline fallback fixture lead**. It has not been verified
in a running client, and this trace does not establish the original service's
human-readable meaning for either code. The successful-data branch and fallback
branch must be validated as separate response roles.

The private derived evidence for this pass is
`postal-selected-area-contract.private.txt`. No live request or emulator action
was performed.

## Startup/authentication network leads after the first native attempt

The local area-wrapper experiment produced error `331401` and a reported
connection to remote TCP `144.76.17.114:443`. This static pass does **not**
identify the hostname owning that particular connection: the available test
log contains no DNS/request evidence, and an IP alone is insufficient to assign
an originating request. The following are concrete native routes to audit
before interpreting that attempt as an area-parser failure.

### Auth-key request remains separate from the area wrappers

Function `0x80077BB8` checks whether the HTTP manager is busy, then reads the
first word of a global object at slot `+0x270` through getter `0x80011C84`.
When that word is zero, it calls the common request builder at `0x80077C18`
with action index **12**, no parameters, no extra parameters, and scheme flag
**1** set at `0x80077C14`. Action-table row 12 is **`webApi_Authkey`**.
The original formatting contract is therefore:

```text
GET https://nwapi.demae-can.com/nwapi.php?action=webApi_Authkey&platform=wii
```

This is a recovered native request, not an endpoint queried in this pass.
The local fixture patch changes the two area-wrapper scheme instructions but
does not change `0x80077C14`. Consequently, even with the API hostname replaced
by a loopback HTTP fixture host, this auth request still selects HTTPS. This is
a confirmed unhandled request/transport case to resolve; it is not proof that
it generated the reported remote IP connection or error code.

The response/storage follow-up below identifies token handling. Entry order of
all callers and the server's token format/issuance still require tracing.
Supplying an invented successful auth response would not establish an actual
authentication service.

### Other original destinations

The complete main-DOL ASCII URL/domain inventory includes:

| Original destination/argument | Native evidence |
| --- | --- |
| `nwapi.demae-can.com/nwapi.php?action=` | Common query builder `0x8002C274`; includes auth and area actions. |
| `nwapi.demae-can.com/nwapi.php` | Separate POST-builder host string at `0x802D64C1`; not an additional domain. |
| `nwpic.demae-can.com/itemimg/` | Image URL builder `0x8002C474`, append at `0x8002C4F4`. |
| `nwpic.demae-can.com/logoimg2/` | Parallel image-builder string at `0x802D6487`. |
| `/startup?initpage=showTitle&titleId=000100014843484A` | Passed as a launch argument at `0x8002539C` to target title `0001000248414241` (`HABA`). This call does not itself specify a network host. |

The image wrappers have independent scheme arguments; replacing only API
strings does not redirect their `nwpic` host. No additional NAS/auth domain was
found by this main-DOL ASCII scan. This does not rule out dynamically supplied
URLs, encoded resources, another title, SDK transport, or host redirection.

Derived code excerpts remain private in `startup-network-leads.private.txt`.
No emulator was launched and no external service request was made during this
follow-up. A future isolated request/DNS capture is needed to correlate the
reported remote connection with an exact host and caller.

### Auth response and token storage follow-up

The adjacent response function `0x80077C40` first invokes the generic transport/
API-status checker `0x800EE084` with error category `0x47`. A nonzero result
stops this path. That checker rejects transport errors and non-200 HTTP status
before its XML status handling; its status lookup uses the recursive-capable
`0x800C43E0`, unlike the postal helper's direct-child status search described
above. A code converting to zero clears its error state; `version` is optionally
processed. The exact effect of that version on later requests is unresolved.

On the non-error path, the auth response parser requires **`authKey`**:

- Search at `0x80077CBC` uses `0x800C43E0` from the parser root. That helper
  checks the current node, later siblings, and descendants; it is not limited
  to a direct `response/authKey` child.
- The matched node must have a payload object (`0x80077CD0`), a nonnull text
  pointer (`0x80077CE8`), and a nonzero first byte (`0x80077D04`). An empty
  token is explicitly rejected.
- Store call `0x80077D28` invokes `0x80011BC8`. It frees the previous token,
  measures the new byte string, allocates `length + 1` bytes, copies exactly
  `length`, and writes a NUL terminator. The token pointer is stored in the
  first word of the object at global slot `+0x270`; its word at offset 4 is
  set to 1. Allocation failure is handled by the response caller.
- No fixed token length, character alphabet, expiry, signature, or decoded
  token structure is checked by the inspected storage path. This does not
  mean the service accepts arbitrary tokens. An offline inspector needs a
  conservative resource limit rather than claiming a recovered native limit.

The initial auth request's `0x80011C84` getter reads that same first word, so
the concrete request gate is whether a stored token pointer exists. Successful
storage clears the caller's error fields at `0x80077D68`–`0x80077D6C`.
No token bytes or personal values were read or published in this static trace.

## Error 331401: recovered native formatting and SSL path

Static tracing identifies formatter **`0x800EA3C8`**. Its normal mapping is
`331400 - raw_error`; therefore **331401 corresponds to raw error -1**.
It is not evidence that API action 14, postal status 1, or a malformed area row
was received. The formatter also clamps out-of-range values to a separate
fallback code, so the arithmetic alone should not be generalized without its
bounds checks.

One direct UI caller is **`0x80019B3C`**. It enters this formatter only when the
HTTP manager result getter `0x8002C254` returns **14**, then reads the manager's
secondary error through `0x8002C25C`. Those getters read manager offsets `0x1C`
and `0x20`. The general error UI also calls the formatter at `0x800EEADC` from
a stored error field; a live capture must determine which UI call was reached.

The native SSL/NHTTP chain provides a concrete producer of this error family:

1. SSL setup/handshake routine `0x80243400` calls helper **`0x802545E8`** at
   **`0x80243530`**.
2. That helper opens **`/dev/net/ssl`** (string `0x8037AB58`) and submits
   ioctlv operation **3**, the SSL handshake operation. The local Dolphin
   `Core/IOS/Network/SSL.h` independently names operation 3
   `IOCTLV_NET_SSL_DOHANDSHAKE`.
3. The helper can return -1 if opening the SSL device fails. Otherwise it
   returns the handshake result. At `0x80243540` the result is saved to global
   transport-error state, and at `0x8024354C` to per-request error offset 8.
4. A result of **-1** branches from `0x80243554` to `0x80243584`, producing
   the internal connection failure return -1001. The NHTTP connection-error
   path at `0x80245C54`–`0x80245C6C` sets result **14** when that saved SSL
   error is nonzero. A parallel handshake path sets the same result at
   `0x80245DDC`.
5. The channel copies result 14 and its secondary error into its HTTP manager
   at `0x8002CEC0`–`0x8002CED4`. This produces the UI's `331400 - (-1)` case.

These findings identify the native **SSL-error family** and a concrete
handshake/device-error path, rather than NHTTP initialization or WC24
registration. They do not prove whether the observed attempt failed to open
the SSL device, failed during a particular handshake, or encountered a missing
request-state lookup: secondary-error getter `0x80247460` also returns -1 when
its request lookup fails. The exact runtime producer, hostname, and connection
still require a correlated capture. Changing the shared profile or postal XML
without that evidence would not establish a fix.

## Read-only live-state anchors for the failed request

At the SSL-error UI function `0x80019AF0`, the global base is
`0x8039A210`; its slot at `+0x22C` contains the channel HTTP-manager pointer.
Thus the manager pointer is the big-endian word at **`0x8039A43C`**. Useful
manager fields recovered from getters and stores are:

| Offset | Recovered role |
| --- | --- |
| `+0x08` | SDK request handle/wrapper pointer, if still retained |
| `+0x18` | HTTP status result |
| `+0x1C` | NHTTP result, including SSL-error family 14 |
| `+0x20` | Secondary SSL/request error |
| `+0x34` | Last diagnostic request string: URL for the GET path, form/query data for the POST path |

The SDK wrapper created by `0x80246FBC` holds its native request pointer at
`+0x10`, an associated payload pointer at `+0x14`, and secondary SSL error at
`+0x08`. The native request holds its normalized URL-string pointer at
`+0x24` and method index at `+0x1C`. A retained request can therefore be
inspected along **manager `+8` → wrapper `+0x10` → native request `+0x24` →
URL bytes**. Every pointer and read range must be checked against mapped RAM;
cleanup may already have freed the request. A nonnull-looking pointer alone
does not establish a live descriptor.

The POST builder `0x8002C6A8` uses the **same request creator `0x80247644`**
as GET. Its call at `0x8002C850` passes method index 1 and saves the returned
handle at manager `+8`. It subsequently adds form parameters and starts the
connection. Its retained `+0x34` string is the formatted POST diagnostic data,
so that field must not be assumed to be a destination URL or exposed publicly.

An entry breakpoint installed only after a failure may time out because no new
request is created during the capture window. Such a timeout cannot establish
that the patched title uses another creator. These offsets are inspection leads;
no agent performed a new launch or debugger connection during this pass.

### Creator/caller cross-check (2026-10-14)

A main-text direct-branch scan finds only two callers of `0x80247644`:
GET creation at `0x8002CDF4` and POST creation at `0x8002C850`. The wrapper is
the only direct caller of underlying creator `0x80246FBC`. This scan does not
exclude indirect calls or another executable, but identifies no separate native
startup connectivity-test creator in this DOL.

The SSL-error display helper `0x80019AF0` is called at `0x800DE78C` and
`0x800DF910`. Both surrounding functions read and display the HTTP-manager
state; neither creates a request or invokes a new connection test there.
Therefore a creator breakpoint missed after an error is still inconclusive
about when the failed request began. No new emulator action or profile was
created during this read-only cross-check.


### Common transport selector confirmed (2026-10-14)

The GET builder copies argument r8 to r28 at `0x8002C298`, tests it at `0x8002C2AC`, and appends either `https://` (nine bytes including NUL) or `http://` (eight bytes including NUL). It forwards that same value as the SSL argument at `0x8002C424`. The POST builder copies r8 to r19 at `0x8002C6D4` and selects the same prefixes at `0x8002C79C`. POST additionally tests r19 at `0x8002CA34`: a nonzero value configures SSL through `0x80247CA4` with argument 1 and `0x802479B0` with argument `0x10B`; zero skips both calls. Later reuse of r19 begins at `0x8002CB70`, after this transport decision.

Replacing those two four-byte argument-copy instructions with `li r28,0` and `li r19,0` therefore forces both common API builders to HTTP and removes the corresponding TLS configuration. It does not change instruction widths, stack allocation, table records, or field capacities; the original 0x800-byte URL scratch buffer remains. This is suitable only for the explicitly scoped local fixture build. It does not establish that later API actions or image downloads are implemented. Private disassembly: `private/demae/common-scheme-selector.private.txt`.


### Startup document template (2026-10-14)

Action 23 is `webApi_document_template` with one parameter. Wrapper `0x800FA59C` supplies parameter-table ID94 (`version`) and literal `00000`, then calls the common GET builder at `0x800FA600`. The startup worker calls this wrapper at `0x800C9840`, waits for completion, and requires NHTTP result0 and HTTP200 before parsing at `0x800C9924`.

The worker finds a direct document `response` node (`0x800C9938`), then direct `apiStatus` beneath it (`0x800C9968`); it obtains `code` recursively beneath apiStatus (`0x800C9980`) and converts it to an integer. Code0 reaches the template path. Codes96/97 take special states0x28/0x2A, and other codes take explicit error branches. This is a dedicated parser, not simply an HTTP success gate.

Success requires direct `container0`, `container1`, and `container2` children of response (`0x800C9A20`, `0x800C9A34`, `0x800C9A48`); direct response `version` text (`0x800C9A80`); and direct `contents` text under each container (`0x800C9A94`, `0x800C9AA8`, `0x800C9ABC`). All four text pointers must be nonnull. Missing required nodes or pointers produces internal error0x5F. The numeric version is stored at global-base+0x354. Contents setters `0x80025A10`, `0x80025A84`, `0x80025AF8` free prior buffers and allocate strlen+1 before copying the strings to global-base pointer/length pairs +0x358/+0x35C, +0x360/+0x364, +0x368/+0x36C. No fixed length cap or allocation-null check is visible in these setters; small bounded offline fixtures are appropriate.

The contents' document language and later rendering semantics are unresolved. The parser does not explicitly reject a nonnull empty string, but native XML empty-element representation has not been established; empty XML elements must not be assumed acceptable. The whole startup sequence is also not fully recovered. Private evidence: `private/demae/document-template-consumer.private.txt`.


### Document root correction and error 338395

The document-template parser requires `response` as the XML root element. Its null-parent direct lookup does **not** mean a child beneath an arbitrary parsed root element: initialization `0x800C3B38` creates an artificial 0x14-byte document node at parser+0x4328, with an initially empty immediate-child array. Parsing with null parent uses that document node (`0x800C3C0C`). Direct lookup `0x800C4538` loads the same document node at `0x800C4564`, then iterates immediate children through child count+8 and array+0xC (`0x800C4AF4`, `0x800C4AFC`). Consequently `<offlineFixture><response>...</response></offlineFixture>` hides response from the required document-level lookup. `<response>...</response>` exposes it. This corrects the earlier synthetic fixture assumption.

The exact error number follows from this failure: missing direct response at `0x800C9948` stores internal error0x5F (95). The report path loads the base338300 from `0x802D9D94` at `0x800C9CA8`, adds that internal error at `0x800C9CB4`, and reports338395 through `0x800EA468`. Thus the wrapper explains338395 without invoking unverified document-content syntax. Contents rendering remains unresolved; the observed failure can occur before any contents are stored.


### Native XML values require CDATA

Static lexer tracing explains why a root-correct ordinary XML body can still produce338395. In parser state0, `0x800C3CB4` checks for `<`; every other byte takes the advance-only path at `0x800C42F0`. Ordinary element text is therefore discarded. The value-writing path is CDATA: after `<!`, `[` at `0x800C3E48` selects state11, starts content seven bytes later, and scans for the literal `]]>` at `0x802D7738` (`0x800C3EEC`). It copies that content and calls value setter `0x800C491C` at `0x800C3FC8` or `0x800C40C8`. The setter stores a value only when strlen is nonzero (`0x800C4970`?`0x800C4978`); empty CDATA is insufficient for required values. Thus required scalars must use nonempty CDATA, for example `<code><![CDATA[0]]></code>` and `<version><![CDATA[1]]></version>`, with each required contents field likewise using nonempty CDATA.

XML declaration quote style is not the cause in this lexer: `<?` enters state3 (`0x800C3CD4`), `?` advances to state4 (`0x800C3E08`), and `>` returns to state0 (`0x800C3E1C`). These branches skip declaration contents without inspecting quote style or encoding name.

Non-ASCII CDATA additionally traverses conversions `0x8002434C` and `0x800243C4`; either conversion failure aborts parsing (`0x800C4054`, `0x800C4078`). Accepted encoding has not yet been established. A short ASCII CDATA fixture is the smallest useful native diagnostic before introducing Japanese text. Private lexer evidence: `private/demae/xml-lexer.private.txt`.


The non-ASCII conversion uncertainty above was resolved on 2026-10-15: native CDATA expects UTF-8 input and converts it to internal Shift_JIS. Exact converter initialization and call direction are documented in shop_contract.md. This supersedes the earlier encoding limitation; unsupported/unrepresentable characters can still fail native conversion.
