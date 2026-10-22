# HCCJ sample-save follow-up

October 22, 2026. The collection-wide catalog lead was verified against the
actual `apps.tar.xz` archive, not just its path listing. The exact member is
under the pre-repair test application's `sample/savedatas/HCCJ/nocopy/pd.dat`.
It was read directly from the archive into ignored private evidence, without
extracting the full archive or installing a save into any NAND.

## Observations

- Sample length: **16,384 bytes**.
- Sample SHA-256: `1049f01d169db224c20ed58d4bfbc95d0488c7aa9981a6ed319b6fdf849de680`.
- The raw sample does not start with the `PDFF` marker described below.
- No personal fields, address strings or phone numbers were decoded or reported.

The archive's HCCJ directory identifies a sample-save lead; it does not
establish the build/version that created the sample, safe live installation,
valid checksum, authenticity or compatibility with the current channel.

## Native helper trace

The separately inspected Japanese HCCJ v2 executable has SHA-256
`640982489f7cc7924da52602130dcf3f100054dd8f907a467759356f1659fbfc`.
Its save-path string is referenced at `0x800E0C6C` and `0x800E39F8`.

In the bounded trace, `0x800E10BC` supplies a `0x4000`-byte buffer length to
helper `0x80087A94` at `0x800E10C0`. The caller checks for return value one at
`0x800E10F0`, then compares the first four output bytes with `PDFF` at
`0x800E110C`/`0x800E1110`. This is the **post-helper buffer**, not proof that
the raw on-disk file must start with that marker. The buffer argument is not
by itself proof that all valid save files must have exactly that length.

The transformation is now independently checked as AES-CBC, as described
below. Save-specific key derivation, integrity checks and record layout
remain to trace. The original sample has not been decoded. These
findings must not be applied to processed postal records, which have their
own U32BE/UTF-16BE framing in `jwc24/demae.py`.

## Reproducible checks

`tools/inspect_demae_address_save.py` reports only bounded metadata and optional
fingerprinted native instruction anchors:

```powershell
python tools/inspect_demae_address_save.py private/demae/address-save-evidence/sample-pd.dat --native-dol private/demae/v2/main.decompressed.dol
python -m unittest tests.test_demae_address_save
```

Size and magic matches are explicitly observations, not validation. The tool
does not print save bytes, decode fields, verify checksums, write saves or
establish native acceptance. Five tests cover metadata-only output, misleading
size/magic matches, bounded inputs, wrong executable fingerprints, the native
anchors and CLI success/failure output. Private binaries are optional local
test inputs, never public fixtures.

## Executable cipher verification

`tools/verify_demae_save_crypto.py` executes the native context initializer
at `0x800879D0`, encryption loop at `0x800879DC` and decryption loop at
`0x80087A94` in Unicorn PPC. The original key schedule, block cipher and CBC
chaining run unchanged. Only memcpy and SDK debug reporting are mocked;
the original startup's SDA register values are supplied to the harness.

Synthetic 128-, 192- and 256-bit keys and a synthetic IV are compared against
PyCryptodome AES-CBC in both directions over multiple blocks. A separate
256-bit-key check covers the full observed 16 KiB buffer. The native routine
also rejects a 17-byte length without modifying the output buffer.

The save caller supplies a 32-byte key length, establishing the 256-bit-key
branch at that call site; the additional key sizes test the underlying cipher
library, not alternative save formats. No Nintendo/device key, IV, plaintext
record or decoded sample is included in the tool or tests.

```powershell
python -m unittest tests.test_demae_address_save tests.test_demae_save_crypto
```

This verifies algorithm behavior with chosen inputs. It does not establish
the correct key/IV for the archive sample, authentication, save-record framing,
checksum behavior or native save acceptance. It must not be used to install
a size/magic-matching file into the user's live NAND.

Private provenance and disassembly are under
`private/demae/address-save-evidence/`. The next step is to trace save-specific
key derivation and the integrity path before implementing an independent
decoder; no service route or live profile was changed.
