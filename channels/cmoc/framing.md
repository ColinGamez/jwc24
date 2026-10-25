# Japanese CMOC response framing

October 26, 2026. This is an independent offline parser and a bounded native
interoperability check, not a working Check Mii Out service.

## Verified native scope

The private Japanese HAPJ v512 main DOL has SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
The test harness reads this original file without changing it. No original
instructions, resources, submitted Miis, keys or credentials are committed.

`tools/verify_cmoc_framing.py` executes these original routines without stubs:

| Address | Checked boundary |
| --- | --- |
| `0x800695D0` | Body pointer, signed length and initial 32-byte cursor |
| `0x80069634` | Header presence at the 32-byte threshold |
| `0x8006966C` | Peek a bounded record without advancing |
| `0x80069728` | Return the record and advance by its exact declared size |
| `0x80068344` | Nonzero 16-bit size at offset 2, or 32-bit size at offset 12 |
| `0x8006A57C` | Compare header tag and words at offsets 4 and 8 |

Synthetic cases cover every body length through 32 bytes, ordinary records,
mixed size encodings, records larger than 65535 bytes, truncation, insufficient
sizes and independent mutation of every header byte. The checksum/signature,
header bytes 2/3, service status, encryption and record meanings are **not**
validated by these routines. Header correlation is not authentication.

## Deliberate independent-parser safeguards

The native iterator checks eight remaining bytes before calling the extended
size accessor, which can read record offset 12. The harness traps that read
when fewer than sixteen bytes remain; it does not read fixture padding and
mistake the result for valid input. A malformed extended size of eight can
also make native iteration alias another prefix inside the extended header.

The independent `jwc24.cmoc.inspect_response` therefore requires at least
sixteen remaining bytes and an extended declared size of at least sixteen.
It rejects partial trailing data instead of silently stopping. Its 16 MiB and
4096-record limits are local inspection policies, not recovered native limits.
Complete extended **payload schemas** remain unknown even though their size
framing is now supported. Opaque correlation values are excluded from object
representations and the metadata CLI.

## Verification and remaining startup work

```powershell
.venv/Scripts/python.exe -m unittest tests.test_cmoc tests.test_cmoc_framing tests.test_cmoc_native_framing
.venv/Scripts/python.exe tools/inspect_cmoc_response.py <private-local-response>
```

Native tests skip when the private executable or optional Unicorn dependency
is absent; the independent parser tests still run. Native execution is capped
per call and by record count, accepts only the pinned DOL, restricts code/read/
write ranges, and checks input, object and stack guards. The harness reports
only booleans, counts and offsets.

The `/first/<value>` FD record meanings, response encryption/signatures,
`X-RESULT` success semantics, request identity checks and native startup remain
unfinished. List/search, posting, contests, voting and WC24 tasks also need
their own contracts and original UI checks. No startup-success response or
live server route has been invented from this framing evidence.
