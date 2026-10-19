# Native HCHJ restaurant contracts: bounded static pass

Read-only inspection of the private v512 executable, 2026-10-14. No emulator was launched, upstream service contacted, or order performed. These are consumer requirements, not proof that a server fixture works end to end.

## Shared XML rules

Names are case-sensitive. Native values require **nonempty CDATA**; ordinary element text is discarded by the custom lexer. The shared status validator requires HTTP200 and apiStatus/code integer0. Root response is the simplest compatible document form. Search helper `0x800C43E0` checks the current context, later siblings and descendants; unlike direct-child helper `0x800C4538`, it does not establish strict containment. Keep unambiguous fields in the indicated context. Non-ASCII conversion and complete accepted input encoding remain unverified.

## Category list

Action4 (`webApi_category_list`, two declared parameters) is requested at `0x8002DDD4`; its result consumer starts `0x8002DE58`. It runs the shared validator with category0x3E (`0x8002DEA0`) and recursively finds response (`0x8002DF60`). It iterates **response child count minus one** (`0x8002DF84`/`0x8002DF88`), so child ordering matters: the final response child is excluded from this loop. The excluded child's identity is not checked here; it must not be assumed that arbitrary ordering is safe.

For each handled response child, it requires a LargeCategoryName node and payload (`0x8002DFB4`/`0x8002DFD4`). Only value matching stock CP932 bytes for 食事 is processed (`0x8002E010`). That group requires CategoryList (`0x8002E028`). Each category entry requires CategoryCode node and payload (`0x8002E07C`/`0x8002E09C`); missing node/payload aborts. Null or empty value skips the entry. Nonempty codes are inserted into the category model at `0x8002E100`. No category display-name field is consumed in this examined path.

A separate consumer `0x8002E51C` recursively finds response, selects response children whose **names start with the nine-byte prefix container** (`0x8002E680` through `0x8002E690`), finds CategoryCode beneath each, and resolves an existing category by that code (`0x8002E6EC`). It then reads ShopList (`0x8002E708`) and each shopCode (`0x8002E740`), constructing skeletal shop entries (`0x8002E79C`). Missing/empty values or unresolved category are skipped in this path. Its exact association with action3 versus other request variants is unresolved.

## Shop list

Action7 (`webApi_shop_list`, four declared parameters) is requested at `0x8003813C`; the detailed consumer is `0x800381C0`. Shared status validation uses category0x3F (`0x80038208`). It finds response (`0x800382B4`) and again iterates response child count minus one (`0x800382E4` through `0x800382F0`). A group must contain LargeCategoryName matching 食事 (`0x80038388`) and CategoryList (`0x800383A4`). Categories require CategoryCode (`0x80038428`); nonempty code must resolve an existing category (`0x800384C8`) or the category is skipped. ShopList is required (`0x800384E4`).

Within each shop entry, these scalar nodes, payloads and nonempty values are required; their absence aborts the consumer:

| Field | Lookup | Use |
| --- | --- | --- |
| shopCode | `0x8003854C` | String identifier |
| homeCode | `0x80038628` | String identifier |
| name | `0x80038704` | Converted display text |
| catchphrase | `0x80038828` | Converted display text |
| yoyaku | `0x80038A4C` | Stored string; interpretation not established |

minPrice (`0x80038964`) and waitTime (`0x80038C18`) are optional; when nonempty their values pass through integer conversion `0x80102CD0` and formatting. No native numeric range guard was established. activate (`0x80038B34`) is optional at lookup, but the resulting value must be exactly **on**, **stop**, or **near** (`0x80038B9C` through `0x80038BD8`) or the shop is discarded.

paymentList is required (`0x80038D00`). Its direct children are inspected for nonempty values matching stock CP932 **代金引換** (`0x80038D90`); no matching payment discards the shop (`0x80038DB4`). This is a display eligibility gate, not proof that payment or ordering is implemented. For eligible shops, shopStatus (`0x80038DC8`) and status beneath it (`0x80038E00`) are required. Optional isOpen beneath status (`0x80038E48`) sets true only for value **1** (`0x80038E8C`); otherwise false. Final insertion is `0x80038EC8`.

## Shop detail

Action8 (`webApi_shop_one`, two declared parameters) is requested at `0x8003DB98`. Consumer `0x8003DC14` validates status with category0x40 (`0x8003DC58`) and resolves the already selected shop model (`0x8003DD68`); an isolated detail response does not create that prerequisite shop.

Recursive whole-document lookups require nonempty categoryCode (`0x8003DE68`), menuListCode (`0x8003E23C`), activate (`0x8003E308`), timeorder (`0x8003E4E0`), and tel (`0x8003E5CC`). The associated missing-value gates abort this parser. address, information, attention, amenity, waitTime, yoyakuMinDate and yoyakuMaxDate have optional lookup branches. timeorder is compared to **y**; positive reservation-date integers are handled. Exact date units and acceptable telephone formatting remain unresolved.

paymentList (`0x8003E808`) must yield at least one supported 代金引換 entry; the supported-entry flag is checked at `0x8003E988` and failure aborts. shopStatus (`0x8003E9FC`) introduces deeper hours/all/message, today/values, delivery/values and selList/values processing. Complete schedule, selection, recommendation-item and later status semantics have **not** been recovered, so this partial detail contract is insufficient to manufacture a successful full response.

## Limits and backend implications

Category insertion `0x800BEAA8` and shop insertion `0x800BF0F4` allocate linked records (0x14 and0x9C bytes) and validate insertion index against current count. No fixed maximum count is visible in these helpers; this does not imply unlimited safe responses. Identifier setter `0x800C0260` allocates strlen+1 and checks allocation failure; no fixed identifier byte cap is established. Display-text conversion uses dynamically allocated buffers. Producers should impose small explicit limits rather than rely on absent native bounds.

Confirmed work suitable for the next offline implementation: strict CDATA/status validation; exact case-sensitive names; nonempty required fields; accepted activate values; model-code consistency; explicit rejection of incomplete shop-detail/schedule contracts. Do not invent menus, payment support or ordering success from these requirements.

Private evidence: shop-list-parser.private.txt, shop-one-parser.private.txt, category-second-parser.private.txt, shop-8002dd60.private.txt and shop-limits-*.private.txt beneath private/demae/.


## Category wire encoding resolved (2026-10-15)

Non-ASCII CDATA is UTF-8 on the wire and becomes Shift_JIS internally. Converter initialization `0x800FA1E8` sets the decoder's name to literal UTF-8 at `0x802DBDB0` (`0x800FA210`) and the encoder's name to Shift_JIS at `0x802DBDB6` (`0x800FA240`). CDATA conversion at `0x800C4050` calls `0x8002434C`, then `0x800FA2CC`, then decoder `0x801F7AE0` using the converter object's first context. The second conversion at `0x800C4074` calls `0x800243C4` and `0x800FA3C4`; encoder `0x801F7D70` receives object+0x10 at `0x800FA4C4`. This establishes direction rather than guessing from adjacent encoding strings. Conversion errors abort native XML parsing.

The category parser's exact LargeCategoryName comparison at `0x8002E010` resolves base `0x802D65AC` +0x1F = `0x802D65CB`, whose four-byte Shift_JIS text decodes as **食事**. Its UTF-8 wire representation is the same Japanese text in nonempty CDATA. The shop-list comparison at base `0x802D6754` +0x22 = `0x802D6776` is the same label. These are case-sensitive tag names and exact text equality, not translated labels.

For a conservative offline category producer, put apiStatus **last** among direct response children. The category consumer unconditionally iterates only childcount-minus-one (`0x8002DF84`/`0x8002DF88`), so placing a handled category group last silently excludes it. Native code does not explicitly verify that the excluded child is apiStatus; this placement is a producer constraint that preserves all handled groups. The status validator itself can locate apiStatus recursively.

An offline category builder can now confidently emit response root, UTF-8 CDATA, LargeCategoryName 食事, CategoryList and nonempty CategoryCode values with final apiStatus/code0. Group and category-entry tag names are iterated rather than explicitly name-matched in this examined parser. Their labels may be synthetic offline names; native end-to-end acceptance, display resources and downstream actions still require separate verification.

Private evidence: encoding-800fa2a0.private.txt, encoding-800243c4.private.txt and xml-lexer.private.txt.


## Category selection to shop-list request (2026-10-15)

Selected category index is stored at scene+0x198 (`0x800B6C80`) before selecting destination job0x514. Dispatch table `0x8034329C` maps jobs0x514..0x518 to request, wait/parse, worker-start, worker-result/UI initialization and later row-resource stages. Job0x514 calls request wrapper `0x80037B68` at `0x800B6CC8`. This wrapper emits action7 at `0x8003813C` with these exact parameter-table IDs:

| ID | Name | Source |
| --- | --- | --- |
| 0 | areaCode | Stored area string (`0x80037D00`, `0x80037D84`) |
| 2 | categoryCode | Fixed selected-index code/model; special scene+0x1A4 mode selects first category or fallback01 (`0x80037DA4` onward) |
| 3 | isReservation | String1 when scene+0x1A0 nonzero, otherwise0 (`0x80038028` onward) |
| 4 | selectType | String0 when scene+0x1A4 nonzero, otherwise1 (`0x800380E0` onward) |

Job0x515 waits for idle, checks transport and parses the body (`0x800B6D08` through `0x800B6D40`). Job0x516 starts worker job0x28 (`0x800B6D88` through `0x800B6D94`); worker `0x800AA5B4` routes that job to shop consumer `0x800381C0` at `0x800AA6B0`. Job0x517 requires a successful worker result, finds the existing category using the same fixed code table (`0x800B6E0C`), obtains its shop count (`0x800B6E10`) and initializes row UI through `0x8003992C` (`0x800B6E1C`). Later row/resource/image processing is not fully established, so this is not a proof of rendered restaurant rows.

There is no requirement for skeletal pre-existing shop records in the detailed consumer's normal insertion path: category records must exist, but each eligible shop is constructed and inserted at `0x80038EC8`. CategoryCode must resolve the selected existing native category; inconsistent category codes skip the entire group.

### Honest directory data limitation

Native eligibility does not support a neutral directory-only row from merely provider name/address. It requires nonempty shopCode, homeCode, name, catchphrase and yoyaku; accepted activate is on/stop/near; and paymentList must include the exact supported cash-on-delivery label (see above), or the row is discarded. shopStatus/status is subsequently required. These gates encode native restaurant-service capabilities, not just display layout. Directory provider data that does not establish those capabilities cannot be promoted into them by invented values. Optional price/time fields can be absent, but that does not remove the eligibility gates.

A truthful read-only integration therefore still needs either verified provider fields satisfying the native contract or a separately reviewed client/backend display design that explicitly removes order-capability assumptions. No such modification or fake success/payment/reservation mapping was implemented in this pass.

Private evidence: shop-request-parameters.private.txt and category-selection-shop-jobs.private.txt.


## Native Shift_JIS repertoire includes CP932 extensions

The native codec name is not equivalent to Python's strict shift_jis repertoire. Alias registry `0x802F4928` maps normalized shiftjis and mscp932 to the same encoding ID12. Descriptor table `0x802F46B8` names ID12 Shift_JIS. Encoder dispatch `0x801F86DC`, via `0x8036ECA0[12]`, selects `0x801F8820` and encoder `0x801F611C`. Its per-character mapper `0x801F6CEC` uses an indexed Unicode-to-byte table at `0x802ED240`, with index table `0x802F2938`, and explicit ASCII/halfwidth/private-use branches.

Exact representative table mappings establish extensions: U+2460 (circled digit one) emits8740, U+2160 (Roman numeral one) emits8754; both are rejected by Python strict shift_jis but supported by cp932. Native U+301C and U+FF5E both emit8160. These are actual native encoder paths and table entries, not assumptions from an alias name.

A read-only table audit of the current 9,400 cached restaurant names and catchphrases found no unsupported native codepoints. Python strict shift_jis rejected19 name rows and816 catchphrase rows; cp932 rejected none. All2,214 distinct characters across those two fields also produce identical native-table and Python cp932 bytes. Therefore strict-only exclusions or NFKC rewriting are unnecessary for this audited cache repertoire. This does not claim whole-codec equivalence for every possible future character; preserve original text and retain explicit validation for unsupported source characters. No native table is redistributed and no restaurant response was served by this audit.

Private evidence: native-sjis-encoder.private.txt, native-sjis-table-helper.private.txt, native-sjis-probes.private.json, native-sjis-cache-repertoire.private.json and native-cp932-cache-comparison.private.json.
