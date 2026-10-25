# Check Mii Out Channel: Japanese v512 inventory

This is an offline inventory of the user-provided stock WAD. No title was
installed, launched, patched, or connected to a remote service during this pass.
No Mii was submitted. Extracted executable, resources, and cryptographic material
remain under the ignored `private/cmoc/v512` directory.

## Verified input

- Source: `Stock WADs/CheckMiiOutChannel-v512-JAP.wad`.
- SHA-256: `d5f7be4e65407d6c46051b2c426427f4c0dd9f3dcb21d66e475f2cc703056a2a`.
- Title ID: `000100014841504A` (`HAPJ`); title version 512; required IOS 35.
- Eight decrypted contents match their TMD SHA-1 values. Boot index is 7.
- Content index 1 (`0000000C`) is the main, uncompressed DOL; index 7
  (`00000007`) is another DOL. Indices 2 through 6 are U8 resource archives.
- The embedded banner build label is `miiContestChF_JP.0801231400`.

The main DOL text is mapped from file offset `0x25E0` to `0x800078A0`.
The endpoint strings below are in the data section starting at file offset
`0x2E8380`, runtime address `0x802EC2C0`.

## Native endpoints

The native URL builder at `0x800743CC` onward selects paths by two-byte request
tags. `0x80074904` combines the selected base host and path. The read service base
is `http://miicontest.wapp.wii.com`; the CGI service bases are
`http://miicontestp.wapp.wii.com/cgi-bin` and
`https://miicontestp.wapp.wii.com/cgi-bin`.

| Native path string | Role established from the string/builder |
| --- | --- |
| `/first/%u` | First/startup data, request tag `FD`; selection at `0x80074520` |
| `/addition/%s%u` | Additional data, request tag `AD` |
| `/%u/con_info` | Contest information |
| `/contest/%u/con_detail%u` | Contest detail |
| `/contest/%u/thumbnail`, `/contest/%u/thumbnail2` | Contest thumbnail assets |
| `/contest/%u/photo`, `/contest/%u/msgboard` | Contest photo/message board |
| `/%u/number_info` | Number information |
| `/%u/pop_list`, `/%u/spot_list`, `/%u/popcrafts_list` | Discovery lists |
| `/%u/new_list%02u`, `/%u/bargain_list%02u`, `/%u/select_list%03u` | Paged lists |
| `/info.cgi?craftsno=%s%u` | Creator lookup |
| `/search.cgi?entryno=%s%u` | Entry lookup |
| `/ownsearch.cgi?craftsno=%s%u` | Creator's entries |
| `/namesearch.cgi?cngroup=%u&entryno=%u` | Name/group lookup |
| `/mister.cgi`, `/check.cgi`, `/post.cgi`, `/vote.cgi` | Native CGI operations; body contracts still need tracing |
| `/contest/%u/entry_list%u`, `/contest/%u/best_list`, `/contest/%u/special_list` | Contest entry/ranking lists |
| `/conpost.cgi`, `/convote2.cgi`, `/conresult.cgi` | Contest CGI operations; body contracts still need tracing |

These are observed string formats, not a specification of accepted values,
HTTP methods, response bodies, or a claim that submission is implemented.

## Response contract evidence

This channel uses structured binary data. An arbitrary successful HTTP response
or invented JSON/XML response will not establish a working startup flow.

- Header names include `X-RESULT`, `X-MC-HOST`, `Last-Modified`,
  `If-Modified-Since`, and `X-APPVER`.
- At `0x80072D58`, the native response handler reads `X-RESULT` as a number;
  values at least 100 enter the service error path (`0x800731C4`). The exact
  absent-header default and success codes have not yet been recovered.
- At `0x80072D84`, a present `X-MC-HOST` value is processed as a host override.
  This is separate from a standard HTTP redirect.
- The body wrapper at `0x800695D0` initializes its cursor to `0x20`.
  `0x80069634` returns the header only when at least 32 bytes are present.
- `0x8006A57C` compares the response header against the expected request:
  big-endian 16-bit field at offset 0 and 32-bit fields at offsets 4 and 8.
  A mismatch is rejected at `0x80072E5C` onward. Fields at offsets 2 and 3
  also feed independent checks, through `0x8007306C` and `0x80072FD4`.
- The block iterator at `0x8006966C` requires enough bytes for the next
  eight-byte block prefix, then requires the declared block size to fit within
  the total body. The size accessor `0x80068344` reads the big-endian 16-bit
  value at block offset 2; if zero, it reads a 32-bit value at offset 12.
  The subsequent [native framing check](framing.md) establishes the extended
  size accessor and deliberately stricter independent-parser bounds.

These offsets establish useful parser checks but do not yet describe a complete
first-response record schema or authentication envelope.

## WiiConnect24 and resources

The separate task URL format is
`http://miicontest.wapp.wii.com/%d/con_task%d.bin`, at file offset `0x2F4B54`.
The formatter at `0x80066AC0` passes two values truncated to eight bits. Their
semantic identities remain to be traced. Its task settings constructor stores
360, 192, 1440, 100, 1, and 1 in successive configuration fields; mapping those
fields to SDK setters is still required before interpreting scheduling units.

The resource archive includes separate `Basic/Net` version/signing/encryption
inputs and `Basic/Nwc24` encryption/public-signature inputs. Their presence is
evidence that the online binary protocol and WC24 envelope need investigation;
it does not establish that server signing keys are available. No key bytes are
published here.

Other resources include contest/posting layouts, localized message banks,
`NGFaceDB.bin`, RFL assets, and an LZ77-compressed `wwwlib-rvl.lz7` library.
The latter was decompressed privately for future analysis. Local save and WC24
strings include `save.dat`, `/storage.bin`, `S:/onrecv.kwb`, and the standard
WC24 download database paths.

## Next useful implementation

The offline, read-only inspector is implemented in `jwc24/cmoc.py` and
`tools/inspect_cmoc_response.py`. Run:

```powershell
.venv/Scripts/python.exe tools/inspect_cmoc_response.py <local-response-file>
```

The CLI reports only framing metadata, excluding record payloads and opaque
header identifiers. The original five inspector tests are now supplemented by
four independent tests and seven native interoperability tests. They do not
establish that the channel accepts a response; see [the bounded native scope](framing.md).

Further static tracing confirms `0x800697C0` advances the cursor by exactly the
declared record size, so the ordinary size includes the eight-byte prefix.
The native iterator requires at least eight remaining bytes, declared size at
least eight, and cursor plus declared size not beyond the body. It establishes
only the eight-byte prefix before the extended-size accessor reads offset 12;
the complete extended payload schema is not verified. The inspector now supports
extended size framing while requiring a full sixteen-byte prefix and an extended
size of at least sixteen. It rejects incomplete extended prefixes rather than
emulate the unchecked native read. Its 16 MiB/4096-record limits and rejection of
trailing partial records are conservative inspection policies, not recovered
native capacity limits. Authentication and field meanings remain unverified.

Next, trace the `FD` first-response record consumers and the authentication/encryption
path before producing a local `/first/<value>` response. A parser test fixture
must be clearly synthetic and must not be described as accepted by the channel.
After the schema is established, add the smallest native startup/read route and
verify it against a captured native request. Submission/voting and WC24 task
generation should wait for their actual contracts to be recovered.
