# Native crash blockers

## HTTP response tree verification (October18)

The preview route verifier now runs every XML response through the original
native parser and compares all element names, text, child counts and sibling
order with the source XML. The real root, Takasaki towns, category and three-shop
responses pass; the highest observed parser stack use is4320 bytes. All three
JPEG routes return the validated original bytes. This checks parsing and local
HTTP transport, not native rendering or successful ordering.

Explicit empty tags brought Minato ward's complete town response to265605 bytes,
slightly above the old256KB offline inspection ceiling. The offline inspector
and parser harness now permit320KB. The full Minato response preserves its tree
under native parsing with3360 stack bytes. This ceiling is not a claim about
native network-buffer capacity. No town rows were removed or shortened.

## Offline native-parser reproduction (October17)

`tools/verify_demae_xml_parser.py` now executes the fingerprinted native parser
at0x800C3BD8 in Unicorn. Allocation, node storage, codec functions and memcpy
are mocked; native token handling, recursion and stack frames are executed.
Forty rows with self-closing empties reproduce stack exhaustion beyond0x4000.
The same parser preserves236 sibling rows with explicit empties using1920
stack bytes for the minimal test. The real Takasaki response completes with
236 rows and3360 maximum stack bytes, below the16KB budget. These regression
checks provide offline reproduction and fix evidence; SDK scheduling and live
Dolphin rendering still require confirmation. The verifier never opens Dolphin.

## Captured parser recursion and serializer fix

A read-only MEM1 snapshot was captured from the warning-paused process after
matching two executable anchors. It remains private. The current thread's saved
PC is0x800C3DF0 within XML parsing. Its saved stack contains repeated0x1E0-byte
frames returning to0x800C42D4, the recursive call at0x800C42D0. Inspecting saved
parent node names found repeated row ancestors where town rows should be
siblings. Stack-like backchain/LR data had reached thread-control fields.

The serializer emitted self-closing empty fields such as <kanji3 />. The native
parser handles closing tags via0x800C3CF4 and normal opening tags through the
recursive path, with no corresponding self-closing-element handling. Root
prefecture/municipality data had no empty fields, explaining why that earlier
screen worked while the town list caused growing recursion.

All native XML serialization now emits explicit opening/closing pairs even
for empty fields. The inspector rejects shorthand self-closing tags and a
regression test checks both spaced and unspaced forms. This also covers empty
payment/status/category fields later in the flow. Live verification of the fix
is pending. No executable, thread stack size or memory-warning suppression was
changed for this fix.

## Takasaki town-list transition, October16

Live v7 displayed Gunma's municipality list, confirming the root response fix.
After Takasaki selection Dolphin reported an invalid write to0x7C0003B5 with
PC0x801A3D9C. The fixture log ends with experimental decimal towns; no category,
shop or image request followed. Image routing is therefore not established as
the cause of this incident.

The instruction is stw r6,0x2E4(r4) in a thread-queue update. It exposes an
invalid queue link, not an identified producer of the corrupted pointer.
Current Takasaki XML has236 rows,50529 bytes, one excluded source row, maximum
name length6 UTF16 units, no percent-sign names, and11-digit terminal area IDs.
Count, encoding and short-label checks pass; these do not prove memory safety.

Required next evidence is the emulated register state, LR/backtrace and relevant
thread/stack memory at the failure or an earlier corruption point. Offline HTTP,
mocked SDK and URL-builder checks do not cover this path. Do not suppress the
warning or describe browsing as ready based on those checks.

## Prepared entry capture

`tools/start_demae.ps1 -DirectoryPreview -TownParserCapture` enables the local
GDB stub on55020 for that process only and starts the existing capture tool
with a breakpoint at0x800D7E90. It captures entry registers, scene r3 for0xE00
bytes, stack r1 for0x1000 bytes, the low-memory thread-pointer region and the
scheduler queue region0x803C5590. Output stays beneath private/demae; memory
contents are not printed. The capture tool removes its breakpoint and resumes
automatically after the snapshot. This is entry evidence, not a proven capture
of the invalid write. The optional mode has been prepared but not run yet.

The normal launcher still disables GDB and no controller, saved address, MMU,
or shared-profile configuration is changed. A busy diagnostic port is rejected.
