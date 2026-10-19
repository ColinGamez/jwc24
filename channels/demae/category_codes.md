# Native category identifiers and genre labels

Read-only HCHJ v512 static trace, 2026-10-15. No requests, emulator launch or save access. This mapping comes from native tables and consumers; it does not assign provider restaurant genres automatically.

## Fixed code table

The native three-byte-stride table at `0x802D6730` contains the two-character codes01 through11, followed by00, each terminated by NUL. A second table at `0x802D74C0` repeats this sequence. The UTF-16BE label table at `0x802D6610` has twenty-byte slots containing the following eleven labels in corresponding index order:

| Code | Native label |
| --- | --- |
| 01 | ピザ |
| 02 | 弁当 |
| 03 | すし |
| 04 | 和食 |
| 05 | 中華 |
| 06 | 洋食 |
| 07 | ファーストフード |
| 08 | カレー |
| 09 | 仕出し・パーティ |
| 10 | デザート・ドリンク |
| 11 | その他 |

Code00 is present in the code table, but its special role has not been established; no ordinary genre label is assigned to it here.

## Consumer evidence

`0x80037B10` reads the selected category index from scene+0x198 (`0x80037B34`), multiplies it by3 (`0x80037B3C` through `0x80037B40`), selects the code table at `0x802D6730`, then finds the category model by exact string (`0x80037B48` calling `0x800BECC8`). That model lookup walks the linked category records and compares stored code strings with strcmp (`0x800BECF8` through `0x800BED00`); it does not convert the code to a number. Thus01 differs from1, and an arbitrary provider code will not resolve through this fixed UI index lookup.

The UI label path reads a genre index at scene+0x360, multiplies by20 and selects the label table (`0x80032D34` through `0x80032D40`), then uses it for text conversion/display (`0x80032E50` onward). A second label lookup appears at `0x8003474C` through `0x80034758`. These hardcoded labels and fixed code slots establish the native genre vocabulary; complete icon-resource association is not yet traced.

Another selection path stores the selected record's byte index into scene+0x198 (`0x800B6AD8`), obtains a code from the duplicate `0x802D74C0` table using index*3 (`0x800B6AF8` through `0x800B6B00`), and inserts that exact code into a category model (`0x800B6B14`). This corroborates index-driven fixed identifiers rather than arbitrary dynamic display labels.

The XML category consumer `0x8002DE58` accepts nonempty CategoryCode strings and inserts them through `0x800BEAA8`; that parser alone has no fixed-code allowlist. Acceptance by the parser therefore does not imply that the corresponding native genre button/model lookup can use the record. A replacement backend can preserve the confirmed01..11 codes for their native genres, but provider-to-genre classification needs a separately reviewed mapping. No such mapping is created by this note.

## Remaining limits

The role of00, index bounds at every caller, icon/texture mapping and any category-code suffix/subgenre conventions remain unresolved. Do not claim that every accepted XML code produces a usable genre UI entry. Use nonempty UTF-8 CDATA and the confirmed category group/status ordering described in shop_contract.md.

Private evidence: category-ui-800becc8.private.txt, category-ui-8002e824.private.txt, genre-map-80032f94.private.txt and genre-map-80037bb0.private.txt. The label table was decoded directly from the private input; native program bytes are not redistributed.
