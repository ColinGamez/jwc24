# Shop help and game-manual recovery, 2026-10-25

The private 2019 collector archive does **not** contain the Wii Shop operations
guide. An independent `7z l -slt -ba -sccUTF-8` inventory agrees with the supplied
listing: 275,505 manual files, 1,733,902,809 declared bytes, and 853 title roots,
all under the `00010001` game namespace. There are no `00010002` or `00070002`
Shop manual roots and no manual `startup.html`. A checksum establishes the
collector archive examined; it does not authenticate Nintendo provenance.

The archive's SHA-1 is `e20c789c86bd602d7af3816d105c3f62ab504374`, its SHA-256 is
`f7f349b8baf06f0f77ba6d413ed87e535378bc746084e24c7d5f59273acacda0`, and its
size is 1,668,780,381 bytes. The detailed, body-free result is
[`research/wii_shop_manual_validation_20261025.json`](../../research/wii_shop_manual_validation_20261025.json).

## Original routes

Static review of captured `oss.js` establishes this help path:

1. `showHelp` checks `isShopManEnabled`, reads the device title ID, and calls
   `showManual`. Compatible mode uses `0007000248414241`, or
   `000700024841424B` for Korea.
2. `showManual(titleId, page)` opens `M_01.jsp` with `titleId` and optional `p`.
3. The only usable captured `M_01.jsp` manual iframe is an English/US **game**
   example. It loads
   `/oss/oss/ext/manual/0001000157414945/FFFD0000/html/index.html`
   with language, country, region, and title parameters. This dispatcher is
   absent from that manual's archived files. It is not evidence for a Japanese
   Shop guide or permission to create a replacement wrapper.

Two `M_01.jsp` captures and one manual-startup capture were extracted into
`private/wii_shop/manual-dispatch-evidence-v1` for inspection only. Raw captured
query strings and page bodies remain private. No script was executed.

**The B_05 footer's captured “More Details” action is a separate flow.** Across
868 captured `country=JP` B_05 pages, it never calls `showManual`. `initPage`
tests `isFreeIntroEnabled == "true"`: true selects `ext/B_30.jsp?titleId=...`,
otherwise it selects `B_06.jsp?titleId=...`, preserving the same game ID. The
captured flag is false on 865 pages and empty on three; none is true. Country
selection alone does not establish Japanese UI language.

The archive has 9,142 nonempty B_06 variants. The 970 nonempty `country=JP`
variants represent 970 titles; 837 intersect the current 844-title catalog.
There are no B_30 captures. Recover B_06 for this action rather than attaching
a game manual to the existing control.

## Bounded game-manual pilot

The inventory contains 212 nonempty `JPN/ja/index.html` files, of which 194
intersect the current catalog. This is coverage of index files, not proof of
complete manuals.

One game, `000100015732434A`, was imported into
`private/wii_shop/manual-japan-pilot-v1`: 52 files and 210,144 bytes, consisting
of seven HTML files, six JavaScript files, two CSS files, and 37 images. The
import verifies the entire archive's fingerprints and each extracted member's
listing order, size, and CRC; private blobs are named by SHA-256 rather than
captured paths. Text decodes without substitution: fourteen text files use
UTF-8 and one script uses CP932.

The pilot manifest SHA-256 is
`e301698e894d2953b00e679aaacfc4eaf1c57b0837a72af876402eab271d82ef`.
The Japanese index SHA-256 is
`5d8da94c18ab2bc59ab197c704710e61b2d097b35b3b57391d314f21a830ba9b`.

This pilot is incomplete. Its index has clickable entries for pages 1–17,
but only pages 1–6 are archived. Six referenced hover images are also absent.
The reference report records all seventeen missing literal paths. The
language-dispatch `html/index.html` used by M_01 is absent as well. Dynamic
navigation and native behavior have not been tested in a browser or Wii.
Do not generate the missing pages, copy hover states from other games, or
describe this as a complete original manual.

## Import and reader API

Run from the repository root, using a new private output directory:

```powershell
.venv/Scripts/python.exe -m tools.import_wii_shop_manual private/wii_shop/frontend-backup-2019/oss-auth.shop.wii.com.7z --listing private/wii_shop/frontend-backup-2019/archive-listing.private.txt --title-id 000100015732434A --output private/wii_shop/manual-japan-another-review
```

Repeat `--title-id` for up to eight explicit Japanese game IDs. The importer
selects that game's `html/<same-title>/JPN/ja/` files and shared `js/` files.
It rejects missing indexes, ambiguous versions, duplicate/linked/encrypted
members, invalid CRCs, members above 2 MiB, and packs above 4,096 files or
32 MiB. It never executes scripts or changes a Shop route. Supported types
are HTML, CSS, JavaScript, PNG, GIF, JPEG; unknown resource types are outside
this bounded importer and remain recovery gaps if a manual requires them.

`jwc24.wii_shop_manual.CapturedManuals(root)` verifies manifest source fields,
every blob's SHA-256 and size, title/locale namespaces, version uniqueness,
and aggregate limits. It exposes:

- `manifest_sha256`, for comparison with a recorded private pack identity.
- `has_asset(path)`, matching exact original paths without query rewriting.
- `asset(path)`, returning `(status, content_type, unmodified_bytes)`.
- `index_url(title_id)`, returning the captured Japanese locale index only
  when that HTML file has been explicitly reviewed and enabled.

All HTML and JavaScript returns 403 by default. A deliberate review may pass
`reviewed_active_sha256=[...]` for individual HTML/JavaScript files. A script's
fingerprint does not authorize other scripts or inline handlers in other HTML
files. Unknown review hashes fail. Passive resources retain their original
bytes; no fallback images or replacement HTML are emitted.

## Integration requirements and remaining work

No server or UI uses this reader. Do not add a manual button, repurpose More
Details, or change the existing help behavior as part of this recovery.

To evaluate game manuals later, first review each enabled HTML/JavaScript
body and recover its missing resources and original dispatcher. The captured
scripts require `wiiShop`, `ECommerceInterface`, `wiiSound`, session history,
native close-manual handling, wallpaper/sound APIs, and an optional EULA URL
from the session. An iframe/session and native-return implementation must
preserve those meanings. Merely serving the Japanese locale index does not
reconstruct M_01 or native manual return behavior.

Recover the Japanese Shop operations guide from a separate verified source;
this archive supplies no guide screenshots to restore Shop menu layouts.
Keep originals, raw listings, manifests and blobs private. The checked-in
files contain JWC24 code, synthetic test fixtures, metadata and evidence of
remaining gaps only.

Validation: `.venv/Scripts/python.exe -m unittest tests.test_wii_shop_manual -v`
passes ten tests, including the optional local pilot check when its private
pack is present. Coverage includes scope/bounds, links and encryption,
ambiguous versions, tampering, namespace/path rejection, unchanged passive
bytes and per-file active-content review. No Dolphin, NAND, credentials, or
live server was used or changed, and no original JavaScript was executed.
