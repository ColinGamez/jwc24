# Captured Virtual Console navigation

October 25, 2026. The preview can use the recovered English `B_01.jsp` Virtual
Console menu while retaining its original markup, four labels, hover images,
title-input geometry and keyboard constants. The captured footer says **Back**
and originally returns to `W_03.jsp`. This recovers a historical menu view;
Japanese localization and complete original navigation remain unfinished.

The source-pinned reader is `jwc24/wii_shop_captured_navigation.py`. It checks
the collector source/archive metadata, exact member-selector fingerprint,
canonical source host/path, page size/hash, original stylesheets and twenty
display dependencies, including hover images and images referenced by CSS.
Original bytes remain private. A collector fingerprint identifies the fetched
capture; it does not establish a Nintendo signature.

| Original label | Captured destination meaning | Current integration limit |
| --- | --- | --- |
| Popular Titles | `B_04`, `popular=true`, `vc=true`, page 1 | Original ranking data is unrecovered; unsupported target remains `/about` |
| Newest Additions | `B_04`, `order=new`, `vc=true`, page 1 | Verified new-release ordering is unrecovered; unsupported target remains `/about` |
| Search by Category | `B_23`, `vc=true` | Gateway is missing; target remains `/about` |
| Search by Game Title | `B_04`, `title` input, `vc=true`, page 1 | Adapted to the replacement catalog query with the captured input/keyboard binding |

The keyboard uses `cKT_PredictNoLF`, five rows and a forty-character limit.
The recovered category control does **not** target the system picker directly.
Its earlier all-title/demo substitutions are removed; the working catalog is
still reachable through `/catalog?category=Virtual+Console`. Unsupported targets
do not claim recovered data or successful completion. No Japanese label,
ranking, release date or missing category menu is invented.

The reader exposes `vc_root`, `vc_layout_html`, `vc_stylesheets`, `vc_styles`,
`vc_controls`, `vc_search`, `vc_back_page`, `vc_dependencies` and
`manifest_sha256`. `vc_root` has script tags/comments removed; callers must
still sanitize original inline event attributes before applying reviewed native
hover/keyboard bindings. Captured account/commerce scripts are not enabled.

## System picker remains offline

`review_systems()` reads the pinned original `B_03.jsp`. It retains all ten
source-backed code/English-label bindings and its original `B_23.jsp` Back
destination. The small 318-byte scrolling subset is separately fingerprinted.
These bindings establish picker codes and labels, not complete Japanese
platform-title membership or the missing gateway's full contents.

The page references 28 display/hover/CSS resources. Two original pictograms are
missing from the shared capture and the reviewed full archive listing:

- `Plat_WII_E.gif`
- `Plat_WIIWARE_E.gif`

Strict reading rejects the incomplete picker. Explicit
`review_systems(allow_incomplete=True)` is available for offline evidence and
reports `ready_for_display=False`; it preserves both rows and original
references. No runtime system-picker route, substituted artwork, removed row,
or Japanese picker is supplied by this work.

The [metadata report](../../research/wii_shop_captured_navigation_20261025.json)
records page/member/manifest hashes, exact original control meanings, dependency
counts and missing resources. Five synthetic reader tests cover source/member/
hash rejection, original bindings, keyboard constants, hover/CSS dependencies
and incomplete-picker behavior:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_captured_navigation
```

Native Japanese input, audio/hover behavior and visual comparison remain
unverified. The missing publisher (`B_17`), category gateway (`B_23`) and WiiWare
(`B_27`) screens are not reconstructed here.
