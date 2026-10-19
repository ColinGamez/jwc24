# Native phone QR handoff: resource and hook candidates

Read-only HCHJ v512 inspection, 2026-10-15. The phone handoff backend is separate work; this note does not claim a QR is already displayed in the native channel. No emulator launch, save access, merchant request or native patch was performed in this pass.

## Confirmed independent layout candidate

The private content2 U8 archive contains Dtest/DtestWelcome.arc. Its Welcome/blyt/welcome_layout.brlyt has a picture pane **weP_dummy**, native size512x244, bound to material index20 named weP_dummy. Nearby welcome page6 text panes weT_06_txt_00, weT_06_txt_01 and weT_06_txt_02 are present, along with the existing central OK button. The root canvas is608x480 and panel532x284. These facts come from actual brlyt pane/material sections, not filename inference.

The welcome archive's texture list currently contains shared background/button textures and we_win_01.tpl; no QR texture or dynamic remote-image route was found. A new QR needs an explicit material/texture binding. Replacing a shared 1x1 background texture would also affect other panes and is unsuitable.

Loader `0x800E505C` obtains the archive through `0x8001C86C` (`0x800E5094`) and instantiates welcome_layout through its resource accessor (`0x800E5144`). The associated archive/layout name strings are based at `0x802DB4C0` and `0x802DB4D8`. This is a concrete resource-loading hook candidate. A dedicated native route that creates/selects this view still needs caller/state tracing; do not patch an arbitrary state address on the assumption that the screen is reachable.

A second candidate is Dialog/blyt/W_dialog_layout.brlyt in DtestDialog.arc: its picture pane DwW_win_panel is550x392, with a516-wide text pane and existing buttons. It is used by shared dialogs, so adding a separate handoff layout/resource is preferable to changing every dialog. Ordinary dialogue_layout icon panes are only40 or48 pixels and unsuitable for a scannable QR.

## Recommended implementation sequence

1. Produce a private, dedicated phone-handoff layout cloned from the welcome resource. Give it a QR picture pane approximately224x224 at integer coordinates, readable instructions and a clear return button. Use a unique QR material and texture rather than merchant logos or shared background assets. Preserve native resource names only where existing button/animation code needs them.
2. Generate a TPL QR texture for the server's short phone entry URL and bind it to that new pane. A static texture is the smallest first native presentation artifact: it needs no native HTTP session, no category/shop model, no declared payment capability and no order API. The encoded URL must remain valid for the configured LAN server; do not embed an expiring one-use order token in a distributable resource.
3. Add an explicit native handoff route/button after the layout's creation and return path are traced. Its visible text should explain that official Demae-can ordering happens on the phone and that the later Wii message follows the user's phone confirmation. Showing a QR or opening a store page must not itself create an order-confirmation message.
4. Once static resource presentation works, implement a separate bounded local image adapter if per-store or per-session QR updates are needed. The adapter should fetch only the local handoff image endpoint, decode a reviewed format into a texture and bind it to the dedicated pane. Native JPEG request/decoder code may be reusable, but request ownership, image limits, texture lifetime and pane binding must be traced before injecting calls. The current pass did not establish a complete safe dynamic-image hook.

For QR assets, use an integer module scale, four-module quiet zone, opaque black/white pixels and point sampling. Lossy JPEG can damage modules; packaged lossless TPL is preferable for the first resource artifact. The exact QR size should be chosen from the resulting short URL's module count and tested by decoding the exported artifact before any native launch.

## Merchant image paths are coupled to unsupported capability gates

Existing consumers `0x80038FF0` and `0x8003FEFC` are shop/detail resource pipelines, not neutral image viewers. They require category/shop models and parse native merchant fields. The first checks and processes the same activate and supported cash-on-delivery gates; replacing a logo or item image response with a QR does not bypass those requirements and gives the QR a misleading merchant context. No fabricated merchant/payment/reservation fields should be introduced merely to reach an image pane.

The proposed independent handoff view avoids using shop_list/shop_one/menu/item success responses as a transport for QR graphics. It can coexist with the read-only provider directory and official phone ordering without claiming native ordering support.

Private evidence: qr-layout-candidates.private.json, qr-welcome-layout-loader.private.txt and qr-image-lead-*.private.txt. Native layouts/program bytes stay private.


## Private native resource artifact built

Reproducible tool tools/build_demae_qr_resource.py now produces private/demae/phone-native/DtestPhoneQR.arc, a224x224 QR preview and metadata. It verifies stock archive fingerprint, appends unique jwc24_phone_qr.tpl, binds only weP_dummy's material20 to the new texture, makes the originally hidden picture visible and puts it left of the instructions. Shared textures, animation files and button names are preserved. The three page6 text fields now contain the requested Japanese phone-ordering header and instructions as UTF-16BE text; the existing OK button is retained.

Builder requires Pillow, qrcode, libWiiPy and zxing-cpp. It decodes its generated QR and compares the result to the private stable-entry URL without printing it; archive/preview/metadata are published together with a source-URL snapshot check. Four synthetic tests verify tiled I8 roundtrip, unique texture/material binding, visible pane placement and Japanese text, QR quiet zone/integer scale and fingerprint/pane guards. An actual archive reload additionally verified17 original files unchanged except welcome_layout. No WAD was patched or installed.

### Route and visibility limitation

A resource clone alone is insufficient. Welcome outer object constructor `0x800E615C` is allocated at global+0x2E0 (`0x80024C94`/`0x80024C9C`); its inner renderer is object+0x60. Vtable `0x80345470` contains initialization `0x800E6244`, update `0x800E6458` and cleanup `0x800E6430`. Inner page selector `0x800E5578` changes group visibility: existing modes1,3,4,5 hide weN_06_txt, which contains the QR. Existing mode2 is used by native error paths (`0x800E7048`, `0x800E708C`, `0x800E7528`) and must not be repurposed as checkout completion. A dedicated page-selection mode and an outer state with explicit return to the caller are still required. The clone has not been shown in native execution.

The inspected loader and page selector bind fonts/animations and toggle groups; no overwrite of the cloned text panes was found in those paths. Other error-specific text handling and the final dedicated route still require verification. The QR resource must remain uninstalled until its route and return behavior are proved.


### Dedicated route requirements now resolved in part

Successful outer initialization unconditionally selects stock mode1 at `0x800E63DC`/`0x800E63E0` and writes outer state3 at `0x800E63E8`. A new inner mode6 alone is therefore insufficient: both successful-entry selection and outer update must explicitly preserve the dedicated mode and bypass stock registration/setup states. The outer+0xBC context field is inner+0x5C; it is distinct from inner+4, which holds the page-selector mode. They must not be confused.

The stock inner renderer offers a concrete close-animation completion signal. In `0x800E5B60`, an accepted button selection (inner+0x54 no longer -1, `0x800E5EFC`) starts ALL_OUT and enters inner state3 (`0x800E5FAC`). When that animation completes, `0x800E60B0`/`0x800E60B4` detect completion; `0x800E60DC` through `0x800E60E4` set inner state -1 and the return value to1, returned at `0x800E6130`. A dedicated outer updater can use this completion signal rather than polling an arbitrary button bit. Concrete renderer disassembly remains private in qr-inner-update.private.txt.

Parallel outer-scene tracing identified the welcome scene as ID2, selected through global requested-scene+0x2C0 and the scene table global+0x2C4. The dispatcher performs cleanup and initialization on transitions. Returning to Title scene1 resets Title fields during its initialization, so restoring the prior Title context requires an explicit dedicated branch; a simple scene-ID return is not yet a proven complete return path. No code cave has been approved, no executable patch has been produced, and the native entry/return implementation remains pending these last routing details.


## Modal alternative: concrete loader and controller constraints

The actual shared modal loads **dialogue_layout.brlyt**, not W_dialog_layout.brlyt. The latter is packaged in the archive but has no literal DOL name reference; a resource-only W_dialog clone is not established as reachable. The modal controller is allocated with size0x2A4 at `0x80024B2C`, constructed by `0x80018208`, stored global+0x24C, and initialized through `0x80018578` at `0x80024B50`. Its initializer obtains DtestDialog.arc at `0x800185D4`/`0x800185D8` via small-data pointer0x80470670 and uses the layout pointer0x80470674 at `0x80018650`/`0x80018654`. The initializer's second argument is global+0x25C, a separate object pointer, stored in text-pane+0xF8 at `0x800186E4`; it is not an available UI type argument.

Controller fields+0/+4 are current/requested animation state, +8 selects the variant through table0x802D5160. Update `0x80018724` transitions opening1 to steady2 after animation completion (`0x800188BC` through `0x800188C8`). In steady state, the ordinary variant polls three native buttons through `0x80017E5C`; a successful button sets selected index+0x170 and requests closing3 (`0x80018ACC` through `0x80018ADC`). Existing open helpers include `0x800193D0` and `0x80019570`; the latter bounds its public selector to22 entries and maps via0x802D5680 to descriptors at0x80344968, whose fields select native control configuration, variant and text. An arbitrary new variant index would cause unchecked table access in update/draw and must not be added as an unreviewed number.

Resource initialization resolves the native panes and animations once before dialogs open. A conditional archive path selected only when a later dialog type opens therefore cannot change the already bound layout safely. A dedicated second controller instance, or a private clone of the actual loaded archive with an added hidden QR group and an explicit type branch that isolates its visibility, requires additional lifetime/frame dispatch proof. Ordinary dialog resource names, textures and dynamic text must remain intact. No modal QR artifact or executable patch is claimed yet.

Private evidence: qr-modal-sda-loader.private.txt, qr-modal-loader-callers.private.txt, qr-modal-controller.private.txt, qr-modal-api.private.txt and qr-modal-frame-callers.private.txt.


### Private default-hidden modal clone built

Tool tools/build_demae_qr_modal_resource.py now creates private/demae/phone-native/DtestPhoneQRDialog.arc from the fingerprinted stock DtestDialog archive. It extends the actually loaded dialogue_layout with a new **JWC24_QR** pane group, hidden by default, under **dib_N_window_00**. Both dialogue_layout_ALL_IN and ALL_OUT target this native parent, so the QR group shares its animation transform and inherited visibility/alpha rather than remaining an independent root overlay. It appends texture index20 and material index44 and three uniquely named instruction text panes, preserving all44 original material records, original pane/control sections and existing texture indices. The native button labels and dynamic text panes are unchanged.

This archive is a reviewable resource addition only. A future explicit phone UI type must show its group, configure enough panel space and isolate it from ordinary dialog variants. Without that type hook the group remains hidden, and no ordinary dialog becomes a QR screen. It neither places an order nor sends Wii mail.

The builder verifies the stock archive SHA256, reloads the result and checks every original archive resource except the extended layout byte-for-byte, decodes the generated QR back to the private stable URL, and atomically publishes archive/preview/metadata using a source-URL snapshot check. Three modal tests verify the default-hidden group under the correct animated parent, preservation of original sections/material records, unique binding and malformed/repeated-patch guards. Together with the welcome resource tests, seven tests pass. Native type, active-Title input gating and exact return-state restoration still need executable implementation and testing.

The scene-specific helper0x800FAB40 must not be reused blindly: it writes scene+0x178 on dialog opening and scene+0xC=0x3C when the controller becomes idle (0x800FABD4). A dedicated Title modal should own its update branch and restore the captured Title state; low-level0x80018724 update and0x80018B7C draw provide the underlying animation/input behavior without those scene-specific writes.


### Bounded phone opener configuration

A dedicated phone opener can retain native variant0 rather than extending unchecked variant tables. Configuration0x101 passed to0x8001ADC0 combines the native background/window visibility bit0 with central-OK activation0x100; it omits ordinary message visibility bit1. The same normal single-OK style0x103 appears in descriptors7,18 and others; its extra bit1 controls the message pane, not the button. The setter activates button0 at0x8001AE10 through0x8001AE30 and selects the central OK icon via0x8001AE38 through0x8001AE5C. Its state/selection initialization must mirror existing open helpers: current0, requested1, variant0, counter0, selected-index -1 and animation timer0.

Native panel bindings are controller+0x218=dic_W_panel00 and +0x21C=dic_W_panel00_s, proven by the pane table0x802D54F8 and resolver0x8001C3F4. Native sizing routine0x8001B4A0 writes their pane height+0x50 and button pane translations at+0x30. The stock maximum row11 uses height330 from0x802D4FA0 and button y=-182 from0x802D5060. A phone-only adjustment to those same fields can accommodate the224px QR and own instructions while leaving ordinary sizing tables unchanged. Central/yes/no button pane pointers are controller+0x17C/+0x1A0/+0x1C4 as read by0x8001B5B4,0x8001B5E4 and0x8001B61C. Remaining exact Title callback pause/return hooks and input argument ownership must be verified before encoding the opener/frame dispatch into a private DOL patch.

Controller close-animation completion writes requested state0 at0x80018A34 (ordinary variant). The subsequent update copies requested0 into current0 at0x80018768; this is the suitable idle completion gate to hide the phone group and release the dedicated Title input pause. Completion is not an order confirmation and must not send mail.


### Review-only opener code component

A standalone PowerPC opener was implemented privately in phone-native/phone-modal-opener.review.s, compiled with devkitPPC Gekko assembler and linked as a356-byte review binary at the reserved-address candidate0x80001800. This is not a DOL patch or installed code. It preserves LR and r29-r31, refuses non-idle or already owned modal state, recursively resolves JWC24_QR before changing any request state, then initializes the existing variant0, calls0x8001ADC0 with0x101, applies phone-only330/-182 geometry and shows the group. A dedicated writable context holds the active flag, owning scene and QR pane. Missing group/layout/modal returns failure before opening a blank dialog. Direct-call decoding independently confirms the config call target0x8001ADC0.

Private source, ELF, binary, disassembly, metadata and reproducible build script are in phone-native. This component still requires a verified Title pause/frame/dismiss hook and proof that the proposed low-memory region survives SDK startup and does not conflict with Gecko. It must not be installed based solely on successful assembly.


### Compiled four-hook integration candidate

The review-only private assembly now includes four guarded interposition points: Title frame0x800D259C, successful button hit0x800D2E28, post-widget overlay draw0x800D30AC and scene3 cleanup0x800CB774. The frame hook uses established native locals r29=scene,r30=frame,r31=cursor. Active phone mode bypasses Title input/action writes and rejoins0x800D2FC0, preserving Title and common widget drawing; the overlay draws last. Both frame and draw retain native HOME pause behavior without changing global+0x248/+0xAC. A successful button index4 hit is consumed even when the QR resource cannot be found; it never falls through into the real ordering action. Other hits relocate the native comparison and follow stock branches.

Cleanup ownership checks the stored scene pointer, requests modal state0 and invokes the statically proven no-frame idle update path with null frame/cursor, then hides the QR and clears context. It preserves volatile GPR3-12, CR, CTR, LR and stack before reissuing the original scene+0xDD4 load. A valid-owner requested-scene mismatch uses the same idle reset before releasing context; a different-owner stale context is cleared without resetting another owner's modal. Normal scene cleanup covers main-scene changes, including HOME exits.

The supposed parent generic input calls were reclassified by full callee inspection:0x800F561C delegates pointer rendering to0x800169F4, and its special branch0x800EB1F8 also performs only virtual draw calls. These calls remain intact so the hand pointer remains visible. Actual Title button updates are suppressed by the active frame hook; the modal button handler reads the existing WPAD state and supplied cursor directly.

The frozen compiled candidate is968 bytes, SHA256 a7e927ce535024f631e78e7052db3e8d22357344d7c724a485f3e7a3221f9c47. Its metadata validates the exact fingerprinted local-api DOL and four original instructions. Fourteen offline scenarios execute the actual compiled instructions with controlled fake SDK calls, checking successful/missing-resource clicks, normal other hits, active/HOME/inactive frames, draw ordering routes, close-to-idle, scene cancellation and cleanup register preservation. This does not prove native SDK rendering or successful scan/return; no installation or launch was performed by this agent. Root owns final guarded composition and emulator validation.


### Boot diagnostic boundaries and loader alignment

The custom Dolphin DolReader explicitly rejects nonempty text/data sections whose address or size is not32-byte aligned (DolReader.cpp initialization). The968-byte candidate must therefore be represented by a992-byte padded DOL section. Padding does not change the968-byte input payload fingerprint; its extra24 zero bytes are loader alignment, not instructions. Root owns the corrected composition primitive.

The first native diagnostic did not reach the patched main executable: the stock TMD boot index is9, and IOS bootstrap loaded00000009.app. That unchanged Nintendo NAND boot program then explicitly launched the System Menu before auth or any maincontent1 access. Its entry at physical0x3400 transfers to0x81330000; main0x813307D0 runs SDK initialization before the boot-state worker0x81330D80. The log has title/directory queries, setting/state/NANDBOOTINFO access and System Menu launch, but no main-content-open/TMD query. Therefore no QR/font/hook display failure was demonstrated by that attempt. The exact SDK launch-context condition remains unresolved; no boot-index or startup-check bypass is justified by this evidence.

The runtime text-field concern was also resolved: TextBox+0xF8 is the optional custom TagProcessor (base constructor has ut_TagProcessorBase.cpp evidence), and rendering explicitly skips it when null at0x80286468/0x8028646C. TextBox font is+0xE4 (assertion at0x8037E890 names mpFont), while+0xD8 holds its text buffer. The appended plain instruction panes preserve the original fontindex0 and need no custom-tag pointer copy. Native font rendering still belongs to display validation, but no new font-pointer patch is warranted.

Private boot evidence: boot9-entry.private.txt, boot9-main.private.txt, boot9-state.private.txt, boot9-refs.private.json and boot9-menu-caller.private.txt. Raw diagnostic logs and native program bytes remain private.


### Revised placement after actual startup failure

The normal Wii Menu start reached maincontent1, but native startup reported an invalid write in the generic copy routine before auth or QR display. A read-only process probe found patched main-text anchors while the proposed low-memory payload at0x80001800 did not match the staged code and its padding was nonzero; scene globals were still uninitialized. This makes that placement unsuitable for the experiment. The exact bootloader overwrite/copy failure remains unproven; it is not attributed to QR rendering.

Root identified a fingerprinted zero run in existing text0 from0x800058BC through0x80005D88. The same968-byte assembly was relinked at **0x800058C0**, entirely inside verified zero bytes, instead of adding a low-memory DOL section. This candidate preserves original section ranges/sizes and uses root's guarded in-place composer. The earlier0x80001800 and0x80004200 candidates are superseded and must not be used.

Private version4 binary/metadata/build script use phone-modal-integration-v4.review names. Payload SHA256 is9fa63dc5fce7cc0c8ac7893e0f133db400db1177603be63ac4f03c7e2b63af41. Runtime hook addresses are frame0x800058C0, click0x800059B0, draw0x800059D8 and cleanup0x80005A24; context0x80005C7C. All fourteen compiled-code scenarios pass again at the new placement. Native boot/display verification remains root-owned and pending; this static test is not a screen-success claim.


## Corrected main home action route (2026-10-15)

The previous state `0x40` hook was on the reorder pane, not the main home order button. Its callback `0x800D2528` initializes `r21=-1` (`0x800D25C4`) and only assigns index 9 (`0x800D2648`); the former index-4 gate was unreachable. This explains why the real home action still entered the native telephone gate.

Main home state `0x38` uses callback `0x800DC738`. It updates descriptor rows 0 through 4 using `0x800CCD7C` at `0x800DC7A4`, with the current row in `r27`. A successful hit is tested at `0x800DC7A8` and stored to scene selection `+0x338` at `0x800DC7E0`. Row 4 is the descriptor's `01_B_btn_demae`; rows 0?3 retain Wii Menu, address change, order history and help. Once the stock selection animation finishes, state `0x39` callback `0x800DC8CC` handles row 4 via `0x800DC9B8`, resets the selected-shop global `+0x34C` to -1, and enters state `0x71`. That bootstrap can enter state `0x0E`, where `0x800D6E94` validates the stored telephone string. Thus the dedicated QR action must consume only the row-4 home hit before these stock state writes. No telephone or address validator is modified.

The private v5 reviewed component uses four hooks: `0x800DC768` for owned modal frame update, `0x800DC7A8` for the row-4 hit, `0x800DC8B4` for modal drawing after the native home background, and the existing scene cleanup hook `0x800CB774`. Callback registers are scene `r24`, frame `r25`, cursor `r26`, singleton `r31`. While the QR modal is owned and active, it skips home input and draws the existing home layout via `0x800DC8A4`; HOME remains native and its `+0xAC` field is never written. The draw hook restores `r11=SP+0x30` before the native saved-register restoration. Modal dismissal consumes the whole frame, avoiding a closing click reaching the home button. Missing QR resources also consume this dedicated hit rather than entering actual ordering.

The v5 payload is 972 bytes at the existing guarded text padding `0x800058C0`. All four original instruction words were checked against the local API-patched source DOL. Eighteen compiled-instruction scenarios passed with mocked SDK calls, including all four other home rows, missing resources, HOME pause, dismissal, scene ownership mismatch and cleanup register preservation. This is static/component verification; the corrected home route has not yet been tested in Dolphin.


### Live refusal and v6 narrow reopening fix

A read-only live probe after the home action found the v5 payload and hooks loaded exactly, main scenes 3/3, private phone context cleared, and modal current 0/requested 3. This hits the opener's pending-request guard before resource lookup. Bounded traversal of the native dialog pane tree confirmed `JWC24_QR` exists and is hidden, with its picture and three text children present; all three text children had assigned native fonts. No user address or telephone bytes were read.

Requested 3 is the native close transition (`0x800187B0`), while requested 4 means no pending transition. Stock new-dialog helper `0x8001ACA8` unconditionally writes requested 1 at `0x8001ACE8` and current 0 at `0x8001ACF0`; helper `0x80019570` does the same at `0x800195C0`/`0x800195C4`. Neither preserves a previous queued close. The v6 opener follows this reset behavior conservatively: it accepts queued close 3 only when current is already 0, alongside existing idle requests 0/4. It still refuses active current 3, other active states, and pending opening requests 1/2. Resource lookup still precedes all new request-state writes.

The v6 component is 980 bytes at the same guarded padding and retains the four corrected home hooks. Twenty-three compiled-instruction scenarios pass, including the observed current-0/requested-3 case and unchanged refusal of current-3 and pending-opening cases. No native installation or launch was performed by this component pass.

### Native visual follow-up

The v6 build subsequently opened the QR dialog in the shared Dolphin profile, with Japanese text and the native OK button. Live pane inspection exposed inherited picture scale 0.55 and right-center origins on the added picture and text. The I8 texture also rendered with insufficient black contrast under the inherited icon material.

The staged v7 WAD retains the same v6 executable and replaces the modal resource with an opaque RGB565 texture, unit picture scale, centered origins and zero inherited text spacing. The launcher pins SHA-256 `bd9db4a57aa51de74360c4335682f07f2fab5c316b78d5daafd1aef80a5edba1`. All 263 automated tests passed, including independent texture tile decoding and geometry checks. The v7 native render, rendered QR scan and close/reopen cycle remain unverified; UI input activity interrupted the build switch. No order was placed or real-user Wii notice sent.
