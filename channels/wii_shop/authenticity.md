# Original Shop fidelity requirements

Updated October 25, 2026, following the owner's explicit requirement: original
assets and experience, no placeholders or invented replacements. This applies
across JWC24, with the Shop findings below documenting the current experiment.

JWC24's service implementation is new code. The target client experience is
the original Japanese channel: its layout, artwork, copy, sounds, animations,
control meanings and flows. Backend compatibility work must not be presented
as recovered original Nintendo server code. Authorized current provider data
can replace discontinued feeds without inventing facts about that data.

## Current preview does not meet the requirement

The loopback preview establishes browser connectivity and exercises a catalog.
It is not an authentic-complete Shop restoration. These concrete deviations
remain in `jwc24/wii_shop_artwork.py` and its adapter:

| Area | Current deviation | Required work |
| --- | --- | --- |
| Page source | Home, VC menu, lists, 834 detail views, 836 controller pages, 835 descriptions and the generic no-results view use reviewed captures; WiiWare menu, ten detail fallbacks and other experimental states still use a modified interactive archive | Integrate remaining captured states and corroborate their behavior |
| Text | Home labels are corroborated by Nintendo's screenshot and native properties; other pages still have adapted translations/descriptions and decoding substitutions | Recover remaining original Japanese copy and correct source encoding |
| Controls | Captured VC menu meanings are preserved, with unsupported ranking/gateway targets leading to the existing explanation; WiiWare's adapted category controls still use list/demo filters | Preserve remaining original meanings and implement their corresponding data and flow |
| Account/title fields | Captured names/publishers now cover 835 IDs and historical points cover 774; balance, other fields and uncovered entries remain unknown | Recover remaining facts, distinguish original-game and Wii release dates, and implement native account state |
| Images | Captured page references now distinguish 776 catalog icons and 835 detail images; 68 icon slots and nine detail slots still use a transparent spacer | Recover missing role-specific references/images and verify native rendering; do not count blank images as completion |
| Details | Captured information panels now preserve original facts/artwork without the custom notice; transaction/account branches are excluded, while ten earlier views remain | Implement original commerce behavior and recover remaining original pages/resources |
| Scripts | Unchanged installed Shop/sound/common scripts and a reviewed captured keyboard script now run; storefront bindings/navigation are still adapted | Review the other recovered storefront scripts and verify remaining native behavior |
| Navigation | Catalog scrolling/paging, 776 title-line sets and the original More Details target/back behavior are restored; unmatched typography and some common labels remain adapted | Recover remaining original page states, navigation and text handling |

Deleting those substitutions alone would not restore missing functions or
original material. Keep the experiment distinguishable from the finished
experience while recovering originals. Do not use another emulator launch as
proof that these fidelity gaps are solved.

The home heading and Wii Menu button now use the native `shop.title` and
`shop.menuBtn` properties. Hover/restore uses the installed `common.js` helpers;
native object construction uses unchanged `shop.js` and `sound.js`. Their pinned
hashes establish exact equality to the installed v21 scripts. This resolves those
specific substitutions, not the other text, menu, data or layout gaps above.
The [historical storefront capture](frontend_capture.md) adds thirteen captured
shared scripts and Japan-region detail requests matching 836 preview IDs.
Its keyboard script and observed search mode/row limit are now integrated;
the complete original Japanese page/keyboard flow remains unfinished.
The home now uses the captured markup and matching CSS/images. Its visible
Japanese menu labels follow Nintendo's official screenshot, correcting
`設定・特典` to `設定・その他`. These strings are corroborated by that screenshot;
the screenshot is not a version-specific v21 localization dump. Other page
labels, native account state and unsupported menu functions remain unresolved.
The [historical title-data integration](title_metadata.md) now supplies accepted
names, publishers and point amounts without claiming current offers. One
request/internal-ID mismatch is excluded, and original-game release dates are
not substituted into Wii release-date fields.
The [captured catalog update](captured_catalog.md) now restores populated-list
markup and its original navigation key handler. It preserves original catalog
title lines for 776 IDs, while 68 use a captured card prototype. The captured
caption is English; this does not resolve the original Japanese localization.
The [detail/controller integration](captured_titles.md) now enables 834 original
information panels and 836 controller pages, with verified local return paths.
Ten detail routes retain the earlier view, including one with a missing CERO
descriptor; no other rating system's icon is substituted. Empty-result/category
templates, complete Japanese copy, commerce and current native visual checks
remain on the [completion list](completion.md).
The [description recovery](descriptions.md) now supplies 835 original B06 pages
and 1,670 screenshots through their verified B05 footer target. The [no-results
review](../../research/wii_shop_navigation_recovery_20261025.md) replaces one
modified state with captured markup; it does not establish Japanese search-again.
The [CAS codec](soap_contract.md) remains offline, and the [partial manual](manual_recovery.md)
does not replace the absent Shop guide or a More Details control.
The [captured VC menu](captured_navigation.md) now replaces its modified template.
Its English captions remain captured English; ranking/release data and the missing
category gateway are not replaced by unrelated filters. The system picker stays
offline because two original pictograms are absent. Detail pages now select the
reviewed original Japanese normal/hover controller images from the same captured
asset family; this asset selection does not prove an original Japanese page capture.

## Nintendo collection follow-up

The existing collection does contain the commerce library and the separate
`shop-browser-source/bw/build/tests/wiishop` customization/test overlay under
`workbench/wii/channel-hunt/packed-resources/`. The latter includes browser C++
integration, `ec.js`, example pages and `demo_oss.html`. These are valuable
original development references. The demo has diagnostic controls and test
server links; it is not the shipping Japanese storefront and must not be used
as its replacement UI.

The overlay installs a separate Shop base package before applying its files.
The recorded dependency is `wstrunk1316_repack.zip`. The collection's existing
archive-reference search has no filename hit for that package. A fresh physical
filename search in the Nintendo tree and `D:/Nintendo-Archive` also found only
`wstrunk1300_notes.conf`, with no `W_03`/`B_27` page files or named Shop/OSS
archive. That notes file is an explicitly synthetic scanner fixture beneath
`vcs-history/control/seed/`, not a recovered Nintendo reference or version.
The October 22 metadata index has no `/oss/serv` hit. These searches do
not exclude renamed files, unindexed archive members or other encodings; they
do not establish that the retail storefront is recovered. No recovered build,
diagnostic page or internal server link was executed or contacted.

## Evidence, not appearance

The [resource comparison](../../research/wii_shop_artwork_provenance_20261025.json)
compares every resource in the 71-file private web pack against the installed
Shop v21 resource archive, after checking all installed title contents against
their TMD. Exactly **2 resources match byte for byte**:

- `/oss/oss/common/images/spacer.gif`
- `/oss/oss/common/images/banner/under_banner_shadow.gif`

This comparison establishes byte equality to the local installation. The TMD's
Nintendo signature has not been verified. The other **69 resources are
unmatched**, which does not prove they are inauthentic: server-side assets need
not be bundled in the channel. Their provenance needs independent evidence.
The transparent spacer is an original resource, but using it in place of missing
title artwork is still a placeholder.

The cached archive's `W_03.html` has a modified doctype and a `clicker.html`
link. `B_04.html` uses `URLSearchParams`, template literals and a separate game
dataset. These are concrete signs that the cached pages are not an untouched
retail-era server snapshot. Source URLs and SHA-256 checks protect the local
cache against alteration; they do not establish historical authenticity.

The earlier 821-image cache used source-reported title-ID associations and one
file ID for both roles. The [historical image update](image_roles.md) now checks
catalog-panel links and accepted detail `Photo` references, preserving separate
role-specific bytes. This establishes agreement with the collector captures,
not Nintendo signatures or complete native rendering. The original category
flow also remains unfinished; the new [backend filters](category_contract.md)
are not a recovered picker UI.

## Reproduce the read-only comparison

```powershell
python -m tools.audit_wii_shop_artwork '<original installed Dolphin Wii directory>' private/wii_shop/artwork-v2
python -m unittest tests.test_wii_shop_artwork_audit tests.test_wii_shop_client_audit
```

The comparison reads installed Shop contents and the private web cache. It does
not read device keys, tickets or account saves; it emits metadata only and
changes neither source. Use the original installed profile, not the patched
preview profile. Original bytes remain private and outside Git.
