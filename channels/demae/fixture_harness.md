# Offline root-area harness

## Current launch setup

The October 14 native test fixed the local TLS/HTTP mismatch with
`HCHJ-local-api.wad`; `tools/start_demae.ps1` now uses that artifact.
The patcher's `--all-api-http` option sets the common GET selector at
`0x8002C298` and POST selector at `0x8002C6D4` to zero, covering callers beyond
the initially patched wrappers. API host fields still point only to loopback;
image hosts are unchanged. The new WAD re-extracted with all ten content hashes
verified, with the other nine contents unchanged. SHA-256:
`de1b89de5a67fddff6841ad616fff596b1dd1de20db7db5fc48ac41203c3290a`.

The fixture server observed `webApi_document_template` and rejected it with
HTTP 400; native error changed to 333400. The prior shared-profile 331401
observations below describe the older area/auth-wrapper-only patch. Document
template startup compatibility remains incomplete.

User direction supersedes the separate-profile experiment: use the existing
`%APPDATA%/Dolphin Emulator` profile with `Dolphin-JWC24-Mail.exe`.
`tools/start_demae.ps1` launches this shared profile, checks fixture listener
ownership, and refuses to stop an existing Dolphin instance. Shared channel
and mail listeners on ports 80 and 8081 remain running.

The shared-profile native test also produced 331401. A live RAM capture
confirmed the HTTP patch words at `0x80077C14` and `0x800F90C0` were loaded;
installed application bytes matched the auth-patched content. Request-creation
breakpoint captures timed out, and subsequent pointer inspection did not
recover the URL. No endpoint or exact SSL error producer was established by
those captures. The error is unresolved. Debugger sessions were stopped and
the ordinary shared-profile launcher restored afterward.

Restarting the fixture listener initially stopped its parent rather than the
child that owned port 18085. That was corrected by inspecting actual listener
ownership; a direct localhost HTTP check verified the active auth fixture.
That direct check is not evidence of a native channel request.

Run `.venv/Scripts/python.exe tools/demae_fixture_server.py` to bind only
`127.0.0.1:18085`. The supported root query is
`/nwapi.php?action=webApi_area_list&platform=wii&areaCode=0`.
It returns the validated 47-prefecture synthetic fixture, with a scope header
and no-store caching. A second query with `zipCode=0000000` replacing
`areaCode=0` returns the traced postal-fallback status 13 fixture. Other queries,
repeated fields, real postal lookups and
ordering actions are rejected. Bounded form POSTs now admit only the same exact
read-only areaCode lookup as GET, for known root/prefecture/municipality codes.
Unknown codes, duplicate fields, extra fields and order actions remain rejected.
Request URLs and body values are not logged. This was added after a native
Gunma selection produced a rejected POST; its exact native form still needs
verification against the adapter.

Correction from live capture, October16: the rejected action after Gunma is
`webApi_inquiry_done`, not area_list. Native error-report code at0x800EA644
submits action22 with a message containing labeled error code/location/side/URL.
Consequently the POST rejection may obscure an earlier native failure; the
area-POST adapter is not a confirmed fix. The server now extracts only the
labeled six-digit diagnostic code from UTF-8 or CP932 form text and discards
the remaining report. No report is forwarded and ordering stays disabled.
The subsequent live report contained336195 itself. Diagnostic submissions now
receive a local status0 acknowledgement after being discarded, to avoid an
unsupported-report failure feeding the error path again. This acknowledges
only the diagnostic receipt; it does not establish working area navigation.

The later native continuation trace established the actual producer omission:
prefecture selection requests areaCode0 again, then reads the selected element's
segment and list of areaName/areaCode rows. The old root had segment only.
When postal data is configured, the root now contains all1892 municipalities
across47 prefectures (35 for Gunma), using189680 UTF-8 bytes in the current
database. Municipality route IDs are M plus five JIS digits to survive the
native10-byte wrapper; old TEST-M IDs truncate. Native wrapper execution and
root hierarchy regression coverage pass; live rendering is still pending.

This listener does not replace the active channel server, patch Dolphin,
forward requests to a provider, or establish native acceptance. Its fixture
uses an unverified wrapper and explicit `TEST-` identifiers. The HTTP test
verifies payload inspection, loopback binding and rejection of unsupported
requests; it shuts down its ephemeral listener afterward.

The inspector enforces exact equality between `areaCount` and all direct rows
in each container's list, including `display=0` rows. Static tracing found that
the native capacity guard runs between containers rather than inside the row
loop, making this producer rule necessary before considering native testing.

The request-line writer confirms method index 0 is GET. A successful postal
response requires `selectedArea/areaCode`, but postal status 13 or 14 branches
to the root request before that lookup. The fallback fixture uses direct
`response/apiStatus/code=13`; its inspector checks that specific nesting and
status, without asserting the meaning of those error codes. The root fixture
also places its status beneath `response`. The wrapper and endpoint transport
still require native verification. See `native_requests.md` for addresses and
remaining startup gaps. HTTP integration tests exercise both offline responses.

The harness also accepts `action=webApi_Authkey&platform=wii`, returning status
0 and an explicitly synthetic `OFFLINE-TEST-TOKEN`. The auth-role inspector
checks the traced recursive status/token lookups and nonempty token without
printing it. Native response acceptance remains unverified. The private DOL
patcher supports `--include-auth`, changing the additional HTTPS selector at
`0x80077C14` to HTTP. `HCHJ-loopback-auth.dol` contains this extension; the
earlier test WAD still contains only the area-wrapper patch and must be rebuilt
before testing the auth extension.

A debugger attempt at the request-creation wrapper timed out and interrupted
at `0x801A30D8`; it did not capture the requested URL. The observed remote IP
cannot yet be assigned to a hostname, and the auth scheme mismatch has not
been proved to be the cause of 331401.

## Private test executable

`tools/patch_demae_fixture_endpoint.py` accepts only the fingerprinted HCHJ v512
main DOL and produces a new private output. It changes the two API host/path
fields to `127.0.0.1:18085`, preserving field sizes, and changes the area-code
and postal wrapper instructions at `0x800F90C0` and `0x800F91B8` from
`li r8,1` to `li r8,0` to select HTTP. Source bytes are never overwritten.
It does not install or launch a title; other endpoints and callers are untraced.
Other API callers sharing the host fields may still select HTTPS and are
unsupported by this harness. Image hosts are unchanged.

The local test artifact `private/demae/fixtures/HCHJ-loopback.wad` was rebuilt
from the immutable source with only application content index 1 replaced.
LZ11 decoding reproduces the patched DOL exactly. Re-extraction verified all
ten contents against their updated TMD hashes, and comparison confirmed the
other nine contents are byte-identical to the originals. The test WAD has not
been installed or launched. Its SHA-256 is
`21abb2b425b219e676917f68ea68d96cdfd0ca9bfd68ad9a405126086749e384`.

Native testing needs a separate Dolphin profile and a synthetic postal test
path. This artifact is not a complete endpoint replacement or restored channel.

## First native launch

On October 13, 2026, the test WAD booted with the existing
`Dolphin-JWC24-Mail.exe`, using `private/demae/test-profile`. The profile copied
system settings and controller configuration, without channel saves. Its first
screen requested a system update because the address helper was unavailable.
Installing the verified stock HCCJ helper into this isolated NAND got past that
screen. The next missing dependency was Wii SSL files, copied locally from the
working profile without exposing their contents.

The subsequent boot reached native internet error **331401**. No successful
area-list display was observed. The current harness and endpoint patch cover
only two area request wrappers; other startup request schemes/actions remain
unsupported and need capture. The experiment used the same emulator build as
the working Forecast, TV no Tomo and Wii no Ma setup; profile dependencies and
incomplete protocol support are separate from the emulator executable.
