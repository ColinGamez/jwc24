# Dedicated native phone screen: route trace

Read-only HCHJ v512 inspection on 2026-10-15. No executable patch, save change,
emulator launch, or original-service request was performed in this pass.

## Existing object and lifecycle

The application allocates a `0xF8`-byte welcome object, calls constructor
`0x800E615C` at `0x80024C94`, and stores the pointer in global offset `0x2E0`
at `0x80024C9C`. Registration copies this pointer to global offset `0x2CC`
at `0x80024D50`, between two other scene pointers. The main dispatcher at
`0x80025D18` indexes the table at global offset `0x2C4` plus four times the
scene ID. Consequently the welcome scene is ID **2**. Scene 1 uses the object
constructed by `0x800C84D8`, registered at `0x2C8`.

The constructor places the renderer/controller at object offset `0x60`.
The vtable at `0x80345470` identifies initialization `0x800E6244`, update
`0x800E6458`, and cleanup `0x800E6430`. Cleanup delegates to the inner
resource cleanup at `0x800E54BC`.

## Distinct fields and entry behavior

The inner selector `0x800E5578` stores its argument at inner offset `0x04`.
The outer initializer instead reads object offset `0xBC`, equal to inner
offset `0x5C`. These are distinct fields. A selector value alone must not be
treated as the outer entry configuration.

After loading the resource through `0x800E505C`, the successful stock path
at `0x800E63BC` explicitly invokes the inner selector with value 1 at
`0x800E63E0`, then sets outer state offset `0x08` to 3. Consequently adding a
selector branch for value 6 alone would not make a dedicated screen reachable.
The successful entry path needs an explicitly traced mode-6 selection.

The load-failure path branches on object offset `0xBC`, choosing existing
messages for values 1 through 5 and a default message otherwise, then sets
outer state offset `0x08` to 2. That path is not an appropriate QR-screen entry.
Existing mode-2 error behavior must retain its original purpose.

## Main scene transitions and return requirements

The outer update routine has an internal state dispatcher for values up to
`0x15` at `0x800E662C`–`0x800E664C`. Its common exit returns zero at
`0x800E82C4`; a proposed return cannot rely on changing its function return
value to signal normal scene completion. A nonzero scene update result follows
the main-loop shutdown path at `0x80025DFC`.

Global offset `0x2C0` is the requested scene, `0x2BC` is the active scene, and
`0x2B8` records the previous scene. On a change, the dispatcher invokes the old
scene's cleanup at `0x80025D2C`, updates previous and active scene fields at
`0x80025D44`/`0x80025D48`, and initializes the new scene at `0x80025D94`.

Restoring the previous scene ID therefore does not resume its existing state.
Scene 1's initializer `0x800C8A68` resets its fields at offsets `0x08` and
`0x0C` to 0 and 1 (`0x800C8AB8`/`0x800C8ABC`). Returning to it without a
dedicated return context could restart setup. A QR extension needs a verified
return-context initialization branch or a modal design that preserves the
calling scene; restoring `0x2C0` alone is insufficient.

Existing transition callbacks `0x800C9E00` and `0x800C9E20` request welcome
scene 2. The latter waits for the caller's offset `0x08` to equal 6. The
preceding chooser `0x800C9DA8` calls an address-related helper and selects local
state `0x30` or `0x32`; nearby callbacks `0x800C9E44`/`0x800C9E5C` request
ordering scene 3. This establishes a welcome-versus-ordering fork, but the
exact title button event leading to the chooser still requires tracing.

A dedicated mode 6 is therefore a candidate extension, not a verified route.
Before activating it, establish the existing title/help action that selects
the welcome object, preserve the caller's scene state, and demonstrate an
explicit cancel/OK path through the normal controller. Resource preparation
alone does not establish those behaviors.

Private evidence is retained in `phone-welcome-route.private.txt` and
`phone-outer-update.private.txt` under `private/demae/frontend-v512/`.
Only lifecycle addresses and findings are published here.

## Verified title-button candidate and modal alternative

Further tracing distinguishes startup scene 1 from the title/menu contained in
ordering scene 3. The `01_B_btn_demae` button is descriptor row 4 in the table
at `0x802DAF38`, whose rows are `0x18` bytes. Its pane names are
`01_P_btn_dema` and `01_B_btn_demae`. The consumer at `0x800F4C94` advances
that table by `0x18` and the corresponding button objects by `0x20`, confirming
the row-index-to-button-index relationship.

The title input routine updates the selected button object at
`0x800D2E24`, passing register `r21` as its button index. A successful hit is
tested at `0x800D2E28`. The following stock path stores that index at scene
offset `0x338`, then changes scene-local state offset `0x08` to 4 at
`0x800D2E74`; later processing advances the local action state.

A dedicated modal can intercept a successful hit **only when `r21 == 4`**,
before these stock selection/state writes. This provides a concrete candidate
hook without replacing setup welcomes, error mode 2, or every ordering action.
The UI must visibly rename this entry to `スマホで注文`. The phone page currently
requires selecting items on the phone; it must not imply that the native cart
has been transferred.

The shared modal controller is a preferable candidate to changing the main
scene: it can preserve ordering scene 3 and its title/menu state. Its bounded
new variant, resource loading, active-input pause, and close-to-idle handoff
still need integration proof before patching. The exact interception point is
therefore established, while a fully functioning phone modal is not yet claimed.

The previously traced `0x800C9DA8` welcome/order fork belongs to the startup
object, not the verified title-button input path. It should not be used as the
phone-order hook.

Private evidence is retained in `phone-title-button.private.json`,
`phone-title-click.private.txt`, and `phone-button-handler.private.txt`.

## Title frame and independent input gating

The title callback containing the button hit is `0x800D2528`, with a `0x100`
stack frame. Its entry arguments are scene pointer in `r3`, frame/context pointer
in `r4`, and cursor/hit pointer in `r5`. After its prologue, `r29` holds the scene,
`r30` the frame pointer, and `r31` the cursor pointer. A candidate active-phone
branch can occur at `0x800D259C`, before the native pause check, after these
locals and register saves are established.

The existing background/layout update and draw routine `0x800D32C8` is called
with the scene and frame pointers at `0x800D2FC8`. A dedicated active-phone
frame can preserve this rendering, update/draw its modal separately, and use the
normal callback epilogue beginning `0x800D30AC`. That epilogue returns 1 to the
ordering-scene callback dispatcher, restores saved floating-point/general registers,
and returns at `0x800D3104`. This is distinct from the welcome scene's main-loop
update return convention.

The low modal draw helper `0x80018B7C` takes controller and frame pointers,
does nothing when the controller is idle, and selects its layout through a bounded
variant table. Its update must be called exactly once per frame by the chosen
integration path; duplicate native/modal updates have not been verified safe.

The parent ordering scene calls `0x800F561C` at `0x800CBDBC`, `0x800CBE54`,
and `0x800CBF68`. Full callee inspection corrects the earlier interpretation of
these calls: they draw the hand pointer, rather than polling title actions.
`0x800169F4` reads IR validity, coordinates, and orientation, builds rendering
matrices, updates pointer panes, and invokes layout draw functions. Its special
overlay branch `0x800EB1F8` likewise only checks visibility flags and draws
layouts. No title button-update or selection callback was found in these paths.
Keep these parent calls intact so the hand cursor remains visible. Pausing the
title callback before its button-update code is the relevant input boundary.

**Do not write global object `0x248`'s field `0xAC` as a phone pause flag.**
The main per-frame routine `0x8001DE44` treats it as a native controller state:
nonzero values invoke the Home Button controller path, and value 2 has distinct
handling. Forging value 1 could activate or mutate that native flow. A phone modal
needs its own active/release context rather than borrowing this field.

Dismissal must complete the modal's close-to-idle transition, hide its QR group,
and release independent input gating without allowing the same confirmation click
to activate the underlying title action. Keeping title/main scene fields unchanged
avoids the previously identified reinitialization problem.

Private evidence includes `phone-pause-owner.private.txt` and the independently
checked full pointer/overlay path in `phone-parent-pointer.private.txt`; no field
writes or native patches were performed during this review.

## Owned-modal reset during ordering-scene cleanup

Ordering scene 3's vtable at `0x803452E0` identifies initializer `0x800CB7A8`
and cleanup `0x800CB760`. Cleanup first saves its scene pointer in `r31` at
`0x800CB770`; the next instruction at `0x800CB774` loads the scene's owned
allocation pointer from offset `0xDD4`. This is a concrete candidate reset hook
after the native prologue and before its existing free operation.

Any added reset must first verify that the phone context is active and belongs
to this same scene pointer. It must not close an unrelated native modal.
For an owned phone modal, requesting controller state 0 at offset `0x04` and
calling `0x80018724(controller, NULL, NULL)` has a statically verified idle path:
the routine copies requested state 0 into current state at `0x80018768`, skips
opening/closing-specific work, and returns through `0x80018824`–`0x80018830`
without dereferencing frame or cursor arguments. The modal draw helper then
returns immediately because current state is 0.

After hiding the owned QR pane and clearing the independent phone context, a
hook must restore native registers/condition state and execute the original
`lwz r0,0xDD4(r3)` before continuing at `0x800CB778`. Normal scene cleanup then
retains its allocation and return behavior. This closes the stale-context case
where the same ordering-scene allocation is initialized again after HOME/menu
exit or another main-scene transition. It is an implementation contract, not a
claim that such a hook has already run successfully in Dolphin.


### Added Title text font binding

The Title archive's `01_m_layout.brlyt` declares font index 0 as
`wbf1.brfna`. The added `JWC24_PHONE_TXT` pane uses the same font index as
stock `01_T_win_post00`, but this does not by itself reproduce the application's
later font replacement.

Native group initialization at `0x800F4894` uses the descriptor table at
`0x802DA638`. The `txt_T` descriptor begins at `0x802DA660`. It resolves layout
groups at `0x800F48E8`, then walks each selected group's pane list at
`0x800F495C` through `0x800F49C0`. For every text pane it obtains the current
font sizes from pane offsets `+0xE8` and `+0xEC`, calls
`0x80285E54(textPane, font)` at `0x800F49A4`, and restores those sizes at
`0x800F49B0` and `0x800F49B4`.

The font setter stores its supplied font pointer into text-pane `+0xE4` at
`0x80285EF0`. This is font replacement, distinct from the text tag processor
at `+0xF8`. The stock `txt_T` group contains seven text pane names and does
not contain the newly added name. To receive this same binding, the new pane
must be included in `txt_T`: its `grp1` section stores a big-endian U16 pane
count at section offset 24 and 16-byte NUL-padded pane names from offset 28.
Appending this name also requires updating section size and layout total size.
This proves the binding omission; runtime rendering still requires testing.

The TextBox resource constructor also attempts initial font lookup at
`0x802831D8` through `0x80283210`, and a resource-font fallback at
`0x80283218` through `0x802832D0`. These are separate from the application's
explicit group-based replacement. Private evidence is in
`phone-title-group-loader.private.txt` and `phone-font-bind.private.txt`.


### Dialog QR text font binding

The shared Dialog has the same explicit font replacement requirement.
Its descriptor table at `0x802D5670` consists of two `(layoutIndex, groupName)`
entries: layout 0 / `txt_T` and layout 1 / `txt_T`. Dialog initialization
`0x80018578` calls `0x8001C3F4` at `0x800186C4`; group lookup at
`0x8001C508` stores the resolved groups into controller `+0x290` and `+0x294`.

The helper `0x80018BB0(controller, font)` iterates both stored group lists
at `0x80018BE4` through `0x80018C58`. It calls the same real font setter
`0x80285E54` at `0x80018C2C`, preserving each pane's `+0xE8` and `+0xEC`
font sizes. Application initialization obtains the font from global `+0x244`
through `0x8001D528` and `0x8001D160`, then calls this helper for the shared
Dialog controller at `0x80024C14`.

Thus added QR text panes must be added to the corresponding Dialog `txt_T`
group, preserving the five original memberships, to participate in this
native font replacement. The tag processor assignment at `0x800186E4`
is a separate store to the stock message pane's `+0xF8` and does not replace
this requirement. Private disassembly: `phone-dialog-font.private.txt`.
