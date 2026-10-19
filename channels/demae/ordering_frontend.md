# Demae ordering frontend: initial inspection

Read-only inspection on 2026-10-13 of the user-provided archive's
`HCHJ-v512.wad`, retained privately under `private/demae/source/`.
No installation, emulator launch, restaurant request, or order was performed.

## Identity and packaged application

The verified WAD identifies title `000100014843484A` (`HCHJ`), version 512,
requiring IOS55. Its ten contents select boot index 9. Content index 1
decompresses to a 3,708,032-byte executable. This is distinct from the HCCJ
personal-data title inspected in [research.md](research.md).

The frontend has native restaurant and ordering UI resources: `DtestOrder`,
`DtestTitle`, `DtestCommon`, `DtestDialog`, and `DtestWelcome` archives contain
NW4R layouts, animations, and textures. No Flash movie or ordering HTML page was
found in the recursively inspected application resource archive. The code uses
native NHTTP requests and JPEG conversion diagnostics. Complete-URL scans miss
the service roots because the executable stores the scheme and host/path
separately.

## Recovered service roots and request construction

The native executable contains these service host/path strings:

- `nwapi.demae-can.com/nwapi.php?action=` for GET API construction.
- `nwapi.demae-can.com/nwapi.php` for POST API construction.
- `nwpic.demae-can.com/itemimg/` and `nwpic.demae-can.com/logoimg2/` for JPEGs.

Separate `https://` and `http://` strings are present. The GET builder appends
`&platform=wii`; the POST builder contains form-style `%s=%s&` formatting and a
`platform` field. The default scheme selection and per-action method still need
caller tracing before replacing these endpoints.

## Native action inventory

The executable's action table has 72-byte rows containing a numeric ID, a
64-byte action-name field, and a declared parameter count. This inventory does
not establish the first startup request or the required response for every action.

| ID | Action | Parameter count |
| --- | --- | --- |
| 0 / 1 / 2 | `webApi_area_list` | 0 / 1 / 1 |
| 3 / 4 | `webApi_category_list` | 1 / 2 |
| 5 | `webApi_area_one` | 1 |
| 6 | `webApi_area_shopinfo` | 2 |
| 7 | `webApi_shop_list` | 4 |
| 8 | `webApi_shop_one` | 2 |
| 9 | `webApi_menu_list` | 1 |
| 10 | `webApi_item_list` | 2 |
| 11 | `webApi_item_one` | 3 |
| 12 | `webApi_Authkey` | 0 |
| 13 | `webApi_basket_add` | 6 |
| 14 | `webApi_basket_modify` | 7 |
| 15 | `webApi_basket_delete` | 4 |
| 16 | `webApi_basket_list` | 7 |
| 17 | `webApi_basket_reset` | 1 |
| 18 | `webApi_validate_condition` | 12 |
| 19 | `webApi_validate_user` | 9 |
| 20 | `webApi_order_tempdone` | 34 |
| 21 | `webApi_order_realdone` | 4 |
| 22 | `webApi_inquiry_done` | 6 |
| 23 | `webApi_document_template` | 1 |
| 24 | `webApi_order_done` | 34 |

The parser's string vocabulary includes `apiStatus`, `version`, `code`,
`response`, `areaList`, `container0`, `segment`, `areaCode`, `zipCode`,
`isNextArea`, and `display`. Restaurant/menu vocabularies include `CategoryList`,
`ShopList`, `menuListCode`, `paymentList`, `isOpen`, and `isSoldout`. These names
are evidence for native structured responses, not a complete schema. A generic
success response cannot establish compatibility.

## Personal-data integration

The frontend directly contains HCCJ's `nocopy/pd.dat` and `pdtmp.dat` paths,
including Japanese, American, and European variants. This establishes shared
personal-data storage integration. The full title-launch/handoff behavior still
needs tracing; address-book data must not be invented or overwritten.

## Launch-reference clarification

Static inspection located `/startup?initpage=showTitle&titleId=000100014843484A`
at runtime address `0x802d62c0`. The reference at `0x80025378` constructs
`r3=0x00010002`, `r4=0x48414241`, `r5=6`, and `r6` pointing to that string,
then calls `0x801a70dc`. The assembled title ID is `0001000248414241` (HABA),
consistent with an Internet Channel launch handoff. This is an inference from
the call arguments; the callee and branch conditions still require tracing.
The string does not establish the ordering frontend's first API request.

`tools/inspect_demae_references.py` validates DOL section bounds and reports
candidate immediate-address references with local disassembly context. Its
results are leads: it does not model register clobbers, indirect references,
or small-data-relative addressing. Private output is required.

## Next verification

Startup document/auth framing is now traced and implemented in the local
harness. Continue terminal-selection and restaurant-response tracing, then
verify using the existing shared JWC24 Dolphin profile. Do not create isolated
profiles. Basket and actual ordering actions remain unimplemented.

The independent HCCJ postal decoder work is covered by the project's 188-test
result reported during this pass. Those tests do not verify this newly extracted
HCHJ frontend's native startup or ordering flow.

Private evidence includes the ten verified content records, the decompressed
executable, recursive resource inventory, and string inventories under
`private/demae/frontend-v512/`. Executable bytes, artwork, title keys, and personal
data are not published in this document.
