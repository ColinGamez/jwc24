# Body Check offline header component review

October 26, 2026. The existing `jwc24/body_check.py` inspector, metadata CLI and
six synthetic tests form a coherent, self-contained offline component suitable
for a scoped baseline commit. Their parser semantics were preserved during
this review. This is not a revived Wii Fit Body Check service or a dataset/health
record generator.

## Contract confirmed

The original Japanese HFNJ v256 decoded main DOL is 4,110,944 bytes, SHA-256
`ca6677094a9293219b4122038b916cb64f6361b5b4106a670ade438292d4969c`.
The private original was read without changing it. No personal save, game
profile, device credentials or actual-Wii backup was read or modified.

The successful-read code at `0x802BBCB8..0x802BBCE8` copies the first downloaded
four bytes into a native word, then calls `0x80146CD4` over the following twelve
bytes. The underlying file read is capped at `0x8000` bytes. The inspector's
BE32-at-zero versus CRC-32(bytes 4 through 15) interpretation therefore matches
the selected original read/check anchors. It does not checksum the remaining
payload. The independent sixteen-byte minimum is a safe truncation policy;
native minimum-length rejection remains unproven.

All six existing tests passed locally and in an isolated public-only copy of
the component without private material. The parser/CLI need only the Python
standard library. They do not import a server, provider adapter, native engine,
encryption keys or proprietary fixture. There is no substantive checksum,
bounded-read or wrong-native-field-meaning issue in this stated subset.

## Scoped CLI privacy correction

The earlier CLI printed exception text for filesystem errors, which could echo
a sensitive supplied pathname. It now returns the same failure status with a
fixed error string and no input-derived exception/path content. Corrupt or
unreadable inputs remain failures; the parser's accepted bytes and metadata
scope are unchanged. Successful output still contains only lengths and scope,
without covered header bytes, opaque payloads or health records.

## Reproducible original CRC comparison

`tools/verify_body_check_header_crc.py` executes only the original CRC leaf
routine against 67 deterministic synthetic twelve-byte regions: zero bytes,
all `0xFF`, incremental bytes and 64 seeded random regions. Every result matches
Python's independent `zlib.crc32` result. No CRC values or supplied bytes are
included in the report.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_body_check tests.test_body_check_crc_native
.venv/Scripts/python.exe tools/verify_body_check_header_crc.py `
  private/body_check/v256/0001-0000000e.dol
```

The original code and its read-only nibble table execute unchanged. The harness
pins the complete DOL fingerprint, limits code to the CRC routine, permits reads
only from the synthetic twelve bytes and original CRC table, rejects every
native memory write, caps instructions per call and checks input guards.
Its 256-case limit is local tooling policy, not a channel dataset limit.

The native checks require the private decoded original and optional
`reverse-engineering` dependencies; they skip when unavailable. Public parser
and CLI privacy tests still run. Eleven focused tests passed locally: six
preserved inspector tests and five new native/privacy cases.

The report is [the bounded CRC validation record](../../research/body_check_crc_validation_20261026.json).
It verifies the CRC primitive used by the header comparison. The complete
dataset loader, WC24 envelope/trust, record layouts, current service data,
Wii Fit/Plus save-backed startup, mail/questions, balance-board input and
measurements remain unfinished. A matching twelve-byte header checksum cannot
establish the integrity or meaning of health records or diagnose a user.
