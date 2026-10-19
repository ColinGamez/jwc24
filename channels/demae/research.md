# Demae initial stock-content inspection

Read-only inspection of the supplied stock WAD on 2026-10-13. Nothing was
installed, patched, launched, or sent to an ordering service.

## Identity and scope

The file named `Stock WADs/demae channel.wad` identifies itself as title
`000100084843434A` (`HCCJ`), version 2, region Japan, using IOS31. Its TMD
contains 11 contents and selects boot index 10, content ID `0000000A`.
The boot content is a 312,576-byte DOL whose header entry is `0x00003400`;
its startup code is mapped at the corresponding cached address `0x80003400`.

The local NUS Downloader database labels the matching title family
`00010008484343XX`, versions 0, 1, and 2, as “Japan Food Service/Demae
Channel.” The supplied title therefore matches that local catalogue identity;
the inspection does not establish that the WAD is wrong or incomplete.

Its visible packaged native application handles personal data. Evidence includes the
content-0 build label `setpersonaldata.0906231905`, packaged `pd_resource.arc`
and `address_book.bmg`, and resource source-path labels containing `pdtool`.
The native UI resources cover address entry, address lists, confirmation,
cautions, and password entry. The Japanese messages describe registering and
editing the Wii's address information. This component handles address settings;
the separate ordering title is identified below.

Subsequent primary developer metadata resolved the separate ordering title as
HCHJ, `000100014843484A`, version 512; see
[frontend identity](frontend_identity.md). The user then supplied an archive
source, from which that exact title/version was downloaded into private storage.
All ten HCHJ contents verified against their TMD. The supplied HCCJ file and
the newly obtained HCHJ ordering frontend are separate artifacts. HCHJ contains
native restaurant/menu/order layouts and Demae-can API/image-server references;
its response contracts are a separate investigation from HCCJ postal lookup.

## Executable and local dependencies

Content index 1, ID `0000000F`, is LZ11-compressed. It decompresses to a
2,198,624-byte DOL with entry point `0x8000403C`. Both the boot DOL and this
application DOL were inspected; the exact transfer between them still needs
code tracing. The boot executable identifies itself as a NAND boot program and
contains content-file open/read/seek/close diagnostics, consistent with loading
another content executable. This is not evidence of an external browser launch.

Bundled resources include the native software keyboard, keyboard sound bank,
ATOK dictionaries, Wii fonts, Home Button resources, layouts, animations, and
textures. These are local resources, not missing server routes.

The application contains local save-path strings for:

- `/title/00010008/4843434a/data/nocopy/pd.dat`
- `/title/00010008/4843434a/data/nocopy/pdtmp.dat`
- Equivalent `HCCE` and `HCCP` companion-title paths.
- `/shared2/sys/SYSCONF` and the System Menu's `setting.txt`.

The save format and safe-write contract have not yet been decoded. Existing
personal-data files must not be replaced with invented records.

## Network and WiiConnect24 evidence

The only complete application URL found by an ASCII scan of the decompressed
main executable is:

`http://cfh.wapp.wii.com/zipcode/001/post%03d.dat`

This establishes a postal-code lookup dependency, but does not establish the
binary response format, request-number range, or whether it is needed before
manual address entry. No restaurant catalogue or order-submission endpoint was
found by this scan. A further scan of the boot and decompressed application
executables for UTF-16LE/BE HTTP URLs, at both byte alignments, found no additional
URLs. Absence from these scans is not proof that none exists in
other encodings or dynamically constructed data.

The executable also contains WiiConnect24 SDK strings for the scheduler,
mailbox configuration, download list, `wc24dl.vff`, `download.bin`,
`content.bin`, and `wc24pubk.mod`. These strings alone establish linked SDK
support. The subsequent code trace below identifies the postal download-entry
registration path; concrete task IDs, intervals, and the full transport payload
contract remain unverified.

## Postal lookup contract: static follow-up

The postal request creator is at `0x8002E34C`. Its default bucket step is 10;
each bucket covers 100,000 numeric postal codes, producing names such as
`post000.dat`, `post010.dat`, through `post990.dat`. The application extracts
at most seven decimal digits from up to 255 input UTF-16 units, accepting both
ASCII and full-width digits. Hyphens and other non-digit characters are skipped.

The request flows through a WiiConnect24 download-entry registration and
download-now chain in `0x8002CC04`, rather than a recovered direct HTTP client.
The default postal input-size setting is 262,144 bytes. Its initialization
requires at least 589,824 bytes of supplied work memory and reserves a 65,536-byte
intermediate allocation. These are native defaults, not yet a complete transport
or task scheduling specification.

The final processed-data parser at `0x8002EBCC` consumes repeated records with
no count or header read by this parser:

| Field | Encoding | Native output capacity |
| --- | --- | --- |
| Postal code | Big-endian unsigned 32-bit integer | One integer |
| Address string 1 | NUL-terminated UTF-16BE | 31 units plus terminator |
| Address string 2 | NUL-terminated UTF-16BE | 31 units plus terminator |
| Address string 3 | NUL-terminated UTF-16BE | 63 units plus terminator |

The parser scans the supplied byte length as 16-bit units. An exact postal-code
match returns 0. A fallback matching the requested number rounded down to the
nearest 100 returns 1; no match returns 2. Oversized strings are scanned through
their terminators while only the output capacity is copied. The precise address
field names still require tracing their UI consumers.

The stock postal defaults select this processing sequence:

1. WiiConnect24 delivers the registered task's downloaded file.
2. The native callback decrypts it with AES-256-CBC, requiring at least 16 bytes
   and a size divisible by 16.
3. The decrypted buffer must begin with ASCII `zpcd`. Its validator requires at
   least five bytes and uses byte 4 as the number of bytes to strip from the
   front. The remaining header bytes and padding semantics are not decoded.
4. The remaining data is Nintendo LZ10 or LZ11. The bounded decoder validates
   the compressed input, then the processed output is saved and read by the
   postal-record parser above.

The default selection is established by the request flag initialized to 1 at
`0x8002D980`, carried into the request object, and the postal processing mode
initialized to 1 at `0x8002E148`. The default download-entry creator selects
entry type 3 and flags value 2, supplies another setter with `0xC0`, and sets
frequency to 1. The semantic names and full scheduler behavior of these fields
still require SDK mapping; they must not be interpreted as ordinary HTTP headers.

The application copies its fixed 32-byte key and 16-byte IV from local constants
into the request context. The AES setup and CBC decrypt path were traced through
`0x800879D0` and `0x80087BE8`; no key or IV bytes are included in this note.
An additional fixed 256-byte block is supplied to the download setup, but its
role has not yet been established. The precise outer framing, authenticity
checks, padding, and original-data provenance remain requirements before serving
a wire-compatible postal response. No original postal files or user address
information have been fetched or published.

## Postal production follow-up (2026-10-14)

The three processed strings are copied into personal-data UI buffers at offsets
`0x224`, `0x264`, and `0x2A4` by `0x80020814`, `0x80020820`, and
`0x8002082C`. The last string also initializes editable address scratch space.
Those buffers bind to `tItem1`, `tItem2`, and `tItem3` in the UI. This confirms
the field order and destination capacities, but the precise prefecture/city/town
label mapping still needs a semantic UI trace before importing Japan Post CSV
columns automatically.

The local Dolphin source establishes the outer download layer: `NWC24DL.cpp`
defines signed downloads as flags bit 2 clear and outer encryption as bit 3 set.
HCCJ's default flags value 2 therefore requests a signed WC24 envelope without
outer encryption. `NetKDRequest.cpp` strips its 320-byte envelope before writing
the delivered application payload. That application payload then follows the
AES-CBC/`zpcd`/LZ pipeline above. Serving the AES body alone is not the stock
task's HTTP wire contract.

The inspected Dolphin implementation does not verify the RSA signature in that
signed branch. This does not establish real-Wii acceptance or authorize producing
an authenticity-shaped placeholder. Original signing material has not been
recovered, and no personal NAND keys or files were changed.

`jwc24/demae_postal_encode.py` now provides a bounded **processed-record** encoder
and stock bucket calculation. It contains no keys and creates no WC24 envelope.
It rejects duplicate postal codes, mixed buckets, embedded NULs, malformed UTF-16,
strings exceeding 31/31/63 UTF-16 units, and processed buckets above 262,144 bytes.
Four focused tests cover round-trip framing, bucket boundaries, ambiguous source
records, Unicode capacities, and oversized buckets.

A Japan Post integration must resolve codes with multiple address rows explicitly;
the native parser chooses the first exact match, so arbitrarily choosing a CSV
row would silently discard address alternatives. No CSV data has been fetched
or converted during this follow-up, and no server route claims native acceptance.

## Smallest next implementation

The independent processed-record reader is now implemented in `jwc24/demae.py`.
It checks every postal-code word and terminated UTF-16BE string before reading,
and rejects malformed text or truncated records. Its configurable inspection
limits are conservative tooling policies, not recovered native capacities.
`tools/inspect_demae_postal.py` reports only file length and record count; it
does not print postal codes or addresses.

The same module implements the recovered application-level decode sequence,
with a caller-supplied 32-byte key and 16-byte IV. It validates ciphertext
alignment, the `zpcd` offset, compression type, and the declared decompressed
size before allocating output. It uses the native default 262,144-byte size
ceiling. This function takes the task file after WC24 delivery; it does not
implement the outer delivery envelope or authenticate signatures. Header
offset checks are deliberately stricter than the native magic-only validator.
No PKCS#7-padding rule is assumed, and no original keys are bundled.

Six tests exercise synthetic CBC/zpcd/LZ10 and LZ11 fixtures, oversized declared
output, malformed headers, every truncated record, Unicode code units, and
metadata-only CLI output. These are independent software checks, not evidence
that the original channel accepted a generated postal download. No postal route
has been added to the live server.

Trace the identified HCHJ frontend's initial API calls and parameter/response
contracts; its [ordering investigation](ordering_frontend.md) records the native
action table. For HCCJ, establish genuine postal-data provenance and the remaining
header/authenticity requirements, then verify local address-entry/save behavior
in a backed-up isolated profile. Only then add a matching lookup route. A generic
JSON API or success-shaped placeholder would not satisfy the native client.

## Private evidence

The extraction helper verified all 11 decrypted contents against the WAD's
content records. Copyrighted payloads remain in `private/demae/v2/`, alongside
the extraction manifest, decompressed DOL, string inventory, U8 resource
inventory, and private address-book message decoding. This public note contains
metadata and findings only; no title keys or copied executable resources.
