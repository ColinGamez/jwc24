# Wii Fit Body Check Channel: initial native inventory

## Scope and status

The local Japanese stock WAD is title `0001000148464E4A` (`HFNJ`), version
256, using IOS55. This is the **Wii Fit Body Check Channel**, whose resources
identify it as Wii Fit からだチェックチャンネル. It combines Wii Fit save access,
body-check records, questions, mail and a downloaded service dataset. It should
not be treated as an HTTP-only video channel.

The first pass on 2026-10-13 verified and privately extracted all ten WAD
contents. Content index 1 is an LZ11-compressed executable; its decoded DOL is
4,110,944 bytes. Index 2 is the main U8 resource archive. Neither the source
WAD nor any installed title or save was modified, and the channel was not
launched in this pass. Extracted executables, resources and service key material
must remain private.

## Confirmed local dependencies

The executable contains explicit Japanese game-save paths:

| Game | Title | Save files referenced by this build |
| --- | --- | --- |
| Wii Fit | `0001000452464E4A` / RFNJ | `RPHealth.dat`, `RPWiiFit.dat`, `banner.bin` |
| Wii Fit Plus | `000100045246504A` / RFPJ | `FitPlus0.dat`, `FitPlus1.dat`, `banner.bin` |

Its own resource strings include `RPFitDat.dat` and `/storage.bin`. The Japanese
message resources explicitly distinguish missing game saves, absent personal
profiles, corrupt game saves and switching to detected Wii Fit Plus records.
The balance-board library also checks the registration/link key recorded in
the Wii Fit save. These are real prerequisites to investigate before blaming
the server for an initial menu failure.

The Wii no Ma isolated NAND checked during this pass contains neither the RFNJ
nor RFPJ save directory. That is evidence about that test profile only; other
Dolphin NANDs have not been fully inventoried. Do not create dummy health data
or overwrite an existing game save to bypass this prerequisite.

## Confirmed network surface

The decoded executable contains one concrete channel-specific download URL:

`http://nwcs.wapp.wii.com/hfn/WiiFitDataAll.enc`

It also references `WiiFitData.dat`, `signkey.key` and `enckey.key`. This implies
a structured encrypted/signed dataset rather than a plain XML response; the
cryptographic format and parser have not yet been reconstructed. Generic
`http://`/`https://` and WC24 strings elsewhere are library strings, not
additional proven service routes. Japanese resources describe receiving DS
pedometer data and including it with question/mail submissions, and distinguish
temporary WC24 service failure from save failures.

There is currently no HFNJ-specific handler or test coverage in this project's
server. Returning arbitrary bytes or a success placeholder at the download
route would not establish compatibility.

## Native tracing anchors

For this exact unmodified v256 executable:

- Dataset URL: DOL file offset `0x3993D8`, runtime address `0x8039D2F8`.
- Nearby string table names the downloaded data and signing/encryption key
  resources. Code at `0x8031BEA0` references that table and resolves key resources
  at its `+0x3E` and `+0x4A` offsets. This is a useful tracing entry, not yet a
  confirmed complete download/decryption routine.
- Local game-save path table begins around file offset `0x393E20`.
- Balance-board save diagnostics are around file offsets `0x3A68B8`–`0x3A6B9C`.

## Next concrete work

1. Prepare a separate Japanese HFNJ test NAND while retaining the existing
   controller configuration and preserving real game saves.
2. Inventory available legitimate RFNJ/RFPJ saves and profiles. Record the
   native first screen on a clean NAND separately from a save-backed NAND.
3. Trace dataset registration/read/decryption and reconstruct its size, header,
   integrity and record constraints before implementing the download route.
4. Verify WC24 consent and mail/question submission flows separately from
   offline records and balance-board input. Confirm balance-board emulation or
   a real registered board before interpreting measurement failures.

No native bootstrap, downloaded-data acceptance, mail submission or body
measurement has been demonstrated yet.

## Download framing trace

Further static tracing recovered the following constraints without creating a
dataset or any personal health records:

- Private nested-resource inspection found a 256-byte `signkey.key` resource and
  a 16-byte `enckey.key` resource. Only names and lengths are recorded here.
- The native registration routine at `0x801BCDF4` writes the signing resource
  at key-store offset `0x000`, reserves/clears `0x100` bytes at `0x100`, and writes
  the encryption resource at `0x200`. This matches the WC24 public-key module
  layout in the local Dolphin source.
- The local Dolphin `WC24File.h` describes a `0x140`-byte outer wrapper: magic
  at `0x00`, version at `0x04`, crypt type at `0x0C`, IV at `0x30` (16 bytes),
  and RSA signature at `0x40` (256 bytes). Its `NetKDRequest.cpp` strips that
  wrapper for signed tasks and decrypts the remainder with AES-OFB for encrypted
  tasks. This source path does **not** verify the RSA signature. Emulator
  acceptance would therefore not prove compatibility with real Wii signature
  validation. Actual task flags and wrapper field values remain to be captured.
- The application read call at `0x802BBBF8` requests `WiiFitData.dat` into an
  internal buffer at `+4`, with a maximum length of `0x8000` bytes. The underlying
  reader at `0x8031A3A0` rejects lengths beyond that bound before copying.
- On successful read, `0x802BBCB8` copies the first downloaded four bytes to a
  word and compares it with CRC-32 over the following **12 bytes**, not the whole
  dataset. The checksum routine at `0x80146CD4` uses reflected polynomial
  `0xEDB88320`, initial value `0xFFFFFFFF`, and final inversion. Thus the
  application has a 16-byte header consisting of a big-endian checksum followed
  by 12 covered bytes. A mismatch clears the buffer and records diagnostic
  `-999`.

The metadata fields, minimum accepted length, subsequent record tables,
compression (if any), and signed-wrapper authentication details are still open.
No arbitrary record layout or synthetic download has been implemented. Native
save-backed testing is deferred until a legitimate Japanese Wii Fit or Wii Fit
Plus personal profile is available from the user's own game session.

## Offline header inspector

`jwc24/body_check.py` and `tools/inspect_body_check_dataset.py` now inspect an
already decrypted local dataset without printing header values or health data:

```powershell
.venv/Scripts/python.exe tools/inspect_body_check_dataset.py private/path/WiiFitData.dat
```

The inspector requires 16–32,768 bytes and verifies only BE32@0 against
CRC-32(bytes 4–15). The sixteen-byte minimum is an explicit safe truncation
policy; native minimum-length rejection has not been proven. The CRC covers
only twelve header bytes. Successful inspection establishes neither payload
integrity, record semantics, RSA authenticity nor native acceptance. Changes
after byte 15 deliberately produce the same header-integrity result.

The CLI reads at most 32,769 bytes to detect oversize input without unbounded
allocation. Six tests cover both size boundaries, all truncated header lengths,
corruption in every checksum/covered-header byte, opaque payload mutations,
metadata-only output and bounded CLI reading. Fixtures contain synthetic
framing only; no health records or downloadable service dataset were created.
