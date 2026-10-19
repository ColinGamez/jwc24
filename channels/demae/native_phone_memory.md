# Phone modal payload memory review

## Current owned-section candidate

The low-memory candidate below was rejected after a native launch: the main
executable loaded, but the payload bytes in `0x80001800` did not survive startup.
The failing run also hit an invalid write at `0x80004040`. The exact writer of
the low-memory region has not been established, so this is not attributed solely
to the startup copy table or the QR resource.

The relocated v4 payload uses `0x800058C0` in the original text section 0.
The fingerprinted executable has an all-zero span through `0x80005D80`, with
no direct branches or aligned address constants referencing the payload span.
The 968-byte payload fits in this span. Its composer retains the original DOL
header, section inventory and file size; only the empty span and four guarded
instructions change. The native startup copy and cache-flush range already
includes this section. Fourteen compiled-code scenarios pass at the new address.
Native rendering and navigation still require verification.

## Rejected low-memory candidate

The candidate payload range is `0x80001800..0x80003000`, also used by Dolphin's
Gecko installer. Any experimental launch using this range must disable cheats
for that launch. It must not run concurrently with a Gecko payload.

The v512 DOL's text/data sections and header BSS do not overlap this range.
Startup at `0x80006124` calls the copy/zero initializer at `0x80006320`.
Its copy table at `0x80006420` has ten destinations, all at or above
`0x80004000`. The zero table at `0x800064A4` targets `0x8038A200`,
`0x804716E0` and `0x80474580`.

SDK initialization at `0x80199F40` calls exception initialization at
`0x8019A4C4`. The latter copies a `0x98`-byte stub to the fifteen destinations
in the table at `0x80356648`; the highest is `0x80001700`, ending at
`0x80001798`. Its handler table begins at `0x80003000`. Neither copy overlaps
the candidate payload. The ordinary arena defaults and fallback begin above
the candidate range.

These checks cover the traced boot copies, zeroing and exception installer.
They do not establish every runtime writer or debug-loader behavior. A staged
payload still requires the complete guarded hook review and Dolphin verification;
the reserved-section builder's overlap check alone is insufficient proof.

Private disassembly evidence is in `private/demae/phone-native/sdk-init.private.txt`
and the original DOL. Heuristic immediate-address scans are retained as leads,
not used as evidence that indirect writes cannot occur.
