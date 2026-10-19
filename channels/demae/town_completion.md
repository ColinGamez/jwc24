# Terminal area selection: bounded native evidence

## Town producer follow-up, October16

Municipality selection callback0x800DB960 passes scene+0x620 through
0x800F9058 and continues to0x8D (variant2 town-list consumer). The shortened
M plus five JIS-digit route survives this wrapper's10-byte bound.

The variant2 duplicate-label branch at0x800F8A54 reads zipCode and subsequently
reads seven bytes for its postcode suffix. Town XML now includes each row's
source Japan Post postcode, preserving separate identities for repeated labels
with different postcodes. The inspector rejects provided postcodes that are
not seven digits, and regression coverage exercises repeated town names and
malformed postcodes. The current database contains one municipality/name group
with multiple postcodes; this is a real source edge case. Native display and
terminal confirmation remain unverified.

Read-only stock HCHJ v512 trace, 2026-10-14. No emulator launch, save changes or upstream requests. State values below belong to the particular area scene, not a universal state enum.

## Selection gate

Handler `0x800D8684` reads the selected 0x70-byte row from scene+0x438 using selected index+0x338. The row flags are read at row+0x1C (`0x800D872C`). If isNextArea is true, it copies row areaCode(+0x60) into scene+0x630 and requests another area list (`0x800D877C`).

For isNextArea false, display is decisive (`0x800D87A4`):

- display false: state+0xC becomes0x7C (`0x800D87B4`), and all six cached area variants are cleared. No terminal API is requested in this branch.
- display true: areaCode is copied into the global+0x260 object through `0x800BB48C` (`0x800D87E8`), then state+0xC becomes0x82 and return-state+0x14 becomes0x8D (`0x800D8814`?`0x800D8820`). The continuation is detailed below; this selection handler itself sends no terminal request.

Consequently a fixture with only isNextArea=0 does not establish successful town completion. The corresponding display flag and later scene prerequisites matter.

## Confirmed area_shopinfo request

Wrapper `0x800F8FC0` requests action6 (`webApi_area_shopinfo`) through the common GET builder at `0x800F903C`. It supplies parameter-table IDs0 and1, confirmed names **areaCode** and **reservationType**. areaCode is formatted from the incoming string; reservationType is formatted using literal `%d` at `0x802DBD03`. A direct caller `0x800D36D0` obtains areaCode from global+0x260 through `0x800BB5DC` and reservationType from `0x800C5678`, reduced to its low byte. This proves the wire parameter mapping, not that this caller immediately follows state0x82.

The selected-code setter `0x800BB48C` allocates strlen+1 and copies the original bytes to object+0x74; getter `0x800BB5DC` returns that pointer. No numeric conversion or eleven-byte special case occurs in these two functions. However, confirmation and state84 do pass that code into a base10 numeric conversion, as established below. Experimental T-prefixed area identifiers cannot be treated as native-selectable. Earlier postal code handling has a separate eleven-byte numeric branch and must not be generalized to this route.

## Partial area_shopinfo consumer

The apparent response worker `0x800D3700`, following the request caller, waits for HTTP idle (`0x800D3720`), requires NHTTP success and HTTP200 through `0x800F8F38` (`0x800D3738`), parses XML (`0x800D376C`) and delegates status checks to `0x800D3F50` (`0x800D377C`). Status helper `0x800D3F50` calls `0x800F8E64` at `0x800D3F70`: it requires direct document response, direct apiStatus beneath it, and direct code text beneath apiStatus. Integer code0 returns success (`0x800D40DC`); missing code/text or nonzero status takes explicit error handling. Required scalar values must therefore use nonempty CDATA.

It also requires existing local model objects (`0x800D3798`, `0x800D37B8`), so response XML alone cannot replace those prerequisites. It takes the artificial document node's first child (`0x800D37E0`/`0x800D37F4`) and requires a nonempty child list. It iterates children from index2 to strictly less than childcount-1 (`0x800D3890`/`0x800D3894`/`0x800D39AC`), making response child ordering material. Beneath each handled child, recursive **ShopList** lookup occurs at `0x800D38B8`, and each ShopList row requires nonnull recursive **shopCode** text (`0x800D3928`). The returned code is compared to an existing selected-shop code (`0x800D3980`), producing different scene states0x48 and0x46. This is a bounded eligibility/membership path, not a full list renderer or a completed restaurant contract.

All scalar XML values require nonempty CDATA under the native lexer. The remaining body shape and ordering must be established before serving this response.

## Unresolved

- Branches beyond the confirmed conditional state44 route, including state24 and State.dcd persistence error handling.
- Whether action5 (`webApi_area_one`, one table-declared parameter) is used on this route. No concrete action5 caller was established in this bounded pass; do not infer parameter or response semantics solely from its name.
- Remaining area_shopinfo local-model prerequisites and intended ordering of its response children.
- Compatibility of experimental synthetic area IDs with every later native consumer.

Private evidence: town-selection.private.txt, town-800bb48c.private.txt, town-800d3540.private.txt and area-shopinfo-consumer.private.txt under private/demae/.


## Runtime dispatch and confirmed continuation

The scene constructs its callback table at runtime, explaining why literal function-pointer scans did not recover it. Dispatcher `0x800CBC08` reads scene+0xC, shifts the state by two bits, adds the scene base, loads the callback at +0xB44 (`0x800CBC18`) and invokes it (`0x800CBC34`). Constructor `0x800CB35C`/`0x800CB3A0` builds `0x800DAE94`, writes it through stack+0x60, and stores it at scene+0xD4C (`0x800CB458`). This is exactly +0xB44 + state0x82 *4.

State0x82 (`0x800DAE94`) opens dialog type0x30 (`0x800DAEC0`), uses return-state0x8D to select cached variant2 (`0x800DAEC4`?`0x800DAED4`), supplies its cached heading and selected row label, and advances to state0x83 (`0x800DAF74`). It sends no API request.

State0x83 is callback `0x800DAF94`, installed at scene+0xD50. When the completed dialog's selected result equals1 (`0x800DB030`), it obtains personal-data slot2, reads stored areaCode and calls `0x800BE868` (`0x800DB058`). This converts the code through `0x80102D94`, which explicitly passes base10 to `0x8010280C` (`0x80102DCC`), and stores the returned two-word numeric value. It also copies two personal-data words from global+0x388 object's +0x4A8/+0x4AC through `0x800BE7C0`, then advances to state0x84 (`0x800DB074`). Other dialog selections restore the scene's saved return-state. No API occurs here.

State0x84 (`0x800DB0E0`, installed at scene+0xD54) repeats the code conversion (`0x800DB124`) and personal-data word transfer, clears five local bytes, then calls State.dcd persistence routine `0x800BC1C0` (`0x800DB160`). Result0 advances to state0x80; results14,5,18 select state0x62 with return-state0x84; other nonzero results select state0x6F. Exact underlying status meanings remain partly unresolved; the operation is a NAND state-file save, detailed below. The decimal converter makes the experimental T-prefixed town IDs unsuitable for native completion; no native-compatible decimal ID mapping is established.

On the result0 route, state0x80 callback `0x800DAD44` opens dialog type0x2F then state0x81. State0x81 (`0x800DAD8C`) waits for dialog completion and selects state0x44 if global+0x34C is nonnegative, otherwise state0x24 (`0x800DAE14`?`0x800DAE38`). Constructor `0x800CB0DC`/`0x800CB1DC` constructs handler `0x800D360C` and stores it at scene+0xC54 (`0x800CB278`), exactly +0xB44 + state0x44 *4. That handler requests area_shopinfo at `0x800D36D0`, as traced above. This is a **conditional** next API route requiring confirmation, decimal-code conversion, State.dcd persistence, another dialog and the global+0x34C condition. It is not an immediate request caused by a terminal area row.

Private continuation evidence: area-handler-install.private.txt, state82-800dae94.private.txt, state82-800cbc00.private.txt, state83-800cb3a0.private.txt and state83-800daf94.private.txt.


## State.dcd persistence and numeric constraints

The state84 call `0x800BC1C0(slot=2)` is a **state-file persistence operation**, not an area-code format validator. Filename table `0x80344808` slot2 points to `State.dcd` at `0x802D7520`. Initial filesystem checks run through `0x8002B3BC`/`0x8002B3C0`; directory preparation is `0x8002B628` (`0x800BC308`). The routine opens State.dcd with mode2 through `0x8002B1E8` (`0x800BC430`), invokes the slot2 object's virtual writer at vtable+0x18 (`0x800BC554`), closes via `0x8002B270` (`0x800BC7A0`), and refreshes file listing through `0x8002B624` (`0x800BC828`). The normal return0 is `0x800BC934` after these operations succeed. No save was read or changed during this static trace.

Raw status table `0x802D75A0` maps0 to0, -14 to14, -5 to5 and additional filesystem status values to numbered errors. Positive results map18; values below -4096 map16; unrecognized values map17. These explain state84's error-state branches. Exact SDK error names, permissions and directory capacity thresholds were not established in this pass.

Area code is a signed64 numeric value: converter `0x80102D94` uses base10 and saturates overflow to signed64 extrema. Setter `0x800BE868` stores highword at payload+8 and lowword at payload+0xC. The two personal-data words copied through `0x800BE7C0` occupy separate payload+0/+4 fields; they do not encode additional area-code bits in this observed representation. Formatter `0x800BE7E0` uses literal `%011lld` at `0x802D7730`: minimum width11, zero padding, signed64 decimal. Consequently a short decimal identifier is normalized when emitted from that stored value, and leading-zero distinctions are lost in the numeric representation.

The nearby State.dcd reader `0x800BE67C` additionally checks a 0x20-byte header, version1, payload size no greater than0x20, complete reads and a checksum. It compares stored area against constant highword0x17/lowword0x4877E7FF = **99,999,999,999** (`0x800BE740`?`0x800BE770`) and returns -15 when the signed comparison exceeds that cap. This establishes a read-side ceiling consistent with eleven decimal digits. It does not prove a lower bound, geographic packing, JIS relationship, or that the write path applies the identical bound. A custom mapping must preserve numeric round trips and this read-side ceiling; replacing original code semantics remains unproven.

Private evidence: local-validation-800bc1c0.private.txt, local-validation-800be7c0.private.txt, local-validation-80102d94.private.txt and personaldata-*.private.txt.


## Stored-code reuse and replacement-ID feasibility

A bounded direct-call scan found one raw numeric-area getter `0x800BE7D0` caller (`0x800CF1C0`) and one normalized formatter `0x800BE7E0` caller (`0x800CF228`). This startup path first requires the slot2 state object to have loaded successfully (`0x800CF1A4`) and the saved signed64 area code to be **greater than zero** (`0x800CF1C4`?`0x800CF1E0`). It then compares the separate saved two-word field, obtained via `0x800BE7B0`, with current global+0x388 object's +0x4A8/+0x4AC (`0x800CF200`?`0x800CF21C`). Equality is required for this cached-area route; those words' full semantic identity remains unestablished.

On success it formats the stored code (`0x800CF228`), copies the normalized text into global+0x260 (`0x800CF234`), and selects state0x44 or0x24 according to global+0x34C (`0x800CF238`?`0x800CF254`). No geographic arithmetic, decimal-prefix extraction or JIS interpretation appears in these examined numeric/formatter callers. Direct setter calls found were the postal selected-area branch (`0x800CF720`), confirmation (`0x800DB058`) and state84 (`0x800DB124`), all passing text to the same base10 conversion. This does not rule out indirect calls or other uses of the corresponding string field.

**Inference for a replacement backend:** custom positive decimal IDs in range1 through99,999,999,999, with one stable eleven-digit zero-padded representation, are structurally consistent with the recovered storage and cached-startup checks. This is not proof of native compatibility or a geographic mapping. Allzero is unsuitable for this cached-area path; leading-zero-distinct IDs collide numerically. The saved two-word equality gate, persistence operations, later API response shapes and route prerequisites remain applicable. No new ID mapping was served or saved in this pass.

Private evidence: stored-area-callers.private.txt.


## State0x24 handoff and category-list job

Area-scene state0x24 is callback `0x800F9AD8`, constructed at `0x800CAEDC`/`0x800CAFD4` and stored at scene+0xBD4 (`0x800CB068`), matching +0xB44 +0x24*4. It clears the XML parser, sets scene+0x1D4 resource text and selects state0x20 with continuation0x25 (`0x800F9B10`/`0x800F9B14`). State0x20 (`0x800F97BC`) starts worker `0x800F9838`, which releases cached area variants and UI resources. State0x25 (`0x800F9B2C`) waits until scene lifecycle+8 equals6, then writes global+0x2C0=4 (`0x800F9B30`?`0x800F9B44`). No category request is emitted directly by state0x24 or0x25.

Global scene table slot4 at +0x2D4 is initialized with object constructed by `0x800A9078` (`0x80024D08`/`0x80024D58`). Its vtable `0x80344798` contains update callback `0x800AA75C`. That callback dispatches **its own** job field+0x10 through table `0x8034329C`; job0x14 maps to `0x800AA9FC`, which calls category request wrapper `0x8002DAD0` at `0x800AAA24`. This proves a category-list request path in the destination scene; it does not establish that activation immediately selects job0x14, since initialization/UI gates are not fully traced.

The wrapper sends action4 `webApi_category_list`: parameter ID0 **areaCode** comes from stored string getter `0x800BB5DC` (`0x8002DC64`/`0x8002DCE8`); ID1 **reservationType** is string1 when scene+0x1A0 is nonzero, otherwise0 (`0x8002DD7C`?`0x8002DDA4`). GET submission is `0x8002DDD4`. Destination job0x15 waits for HTTP idle and parses the response (`0x800AAA68`?`0x800AAAA8`). Job0x16 selects worker job10 (`0x800AAAF4`); worker `0x800AA5B4` dispatches that job to category consumer `0x8002DE58` (`0x800AA68C`). This links the request to the previously examined category contract.

The smallest **consumer-level** category requirements are shared HTTP/status success, response, a handled group with nonempty LargeCategoryName equal to native 食事, CategoryList, and nonempty CategoryCode values in category entries. Values require CDATA. The category consumer iterates response childcount minus one; preserve reviewed ordering rather than assuming unordered XML is accepted. It creates category records, not complete shop detail/menu/order support. Exact group/row tag names remain unproven; the UTF-8-to-Shift_JIS conversion is now established in shop_contract.md. See shop_contract.md for precise lookup addresses and failure/skip behavior. No speculative category fixture was served in this pass.

Private evidence: scene-callback-map.private.json (derived register/stack tracking, confirmed relevant entries against disassembly), state24-800f9ad8.private.txt, state24-next-800f97bc.private.txt and restaurant-bootstrap-*.private.txt.
