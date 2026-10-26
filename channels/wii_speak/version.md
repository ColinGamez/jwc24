# HCFJ v512 version-file consumer

Recovered October 26, 2026 from the private Japanese retail application
identified in the [channel audit](README.md). This is a version-file inspection
component, **not a restored Wii Speak service**. No actual version-file response
was found or fetched, and no constructor value is used as a service default.

## Original application evidence

Application SHA-256:
`7da329f17754d3199b6254f26c3e059913671820f9017c2424236430aa64eff3`.
The LZ11-expanded content-index1 application is the source, not boot-index8.
The original software and packaged cryptographic material remain private.

| Native address | Observed operation |
| --- | --- |
| `0x800B9624..0x800B9718` | Builds the descriptor with historical URL `http://nwcs.wapp.wii.com/hcf/version.enc`, local name `version.enc` and private packaged key-resource references. |
| `0x800423B4`, `0x800416BC` | Construct the worker and its separate VF download-task object; they do not parse a version response. |
| `0x80052174..0x800521FC` | Creates an object with two big-endian 32-bit words, constructor values 2 and 400, and exposes those words as an eight-byte destination. These are local constructor values, not a captured server reply. |
| `0x80095A50..0x80095A60`, `0x80095D70..0x80095D80` | Real startup passes that destination through command `0x17`. |
| `0x80042114..0x80042228` | Worker performs the VF read, providing destination pointer and capacity, with descriptor filename. |
| `0x801A9780..0x801A9890` | Opens the VF file, obtains its size, rejects size greater than supplied capacity with status `0x16`, otherwise reads into the supplied destination. |
| `0x80095F30..0x80095F48` | Compares the first downloaded word against unsigned client value 2. The surrounding startup configuration can bypass this comparison. |
| `0x80044EA8..0x80044EBC` | Shifts the second downloaded word left ten bits and compares a candidate size against the resulting unsigned 32-bit byte limit. Large values wrap; no stronger semantic meaning is assigned here. |

The VF reader does **not** require exactly eight file bytes: synthetic lengths
0 through 8 return success and preserve any unwritten constructor tail. Lengths
9, 16, 328 and 8192 return `0x16` before the read. This early return also bypasses
the close/unmount calls in this routine. No JWC24 fallback reproduces these
partial-file semantics as a fabricated version reply.

The independent `inspect_version_data` requires exactly eight explicit bytes as
a stricter local completeness policy. It reports both words, the observed
newer-than-2 comparison, the native wrapped limit and whether the shift loses
high bits. It does not validate release metadata, compatibility, freshness or
native startup success. Values 0 and unsigned high-bit values remain observable;
there is no invented permitted-release range or default feed.

## Opaque HTTP capture boundary

The pinned [Dolphin WC24 file structures](https://github.com/dolphin-emu/dolphin/blob/3eb30c7620b4475b2e0404228ba0d2b238a132f1/Source/Core/Core/IOS/Network/KD/WC24File.h)
describe a 320-byte envelope with IV and RSA fields. Its
[KD downloader](https://github.com/dolphin-emu/dolphin/blob/3eb30c7620b4475b2e0404228ba0d2b238a132f1/Source/Core/Core/IOS/Network/KD/NetKDRequest.cpp)
strips that envelope and applies AES-OFB when task settings request encryption.
These are separately identified emulator implementation sources, not original
Nintendo IOS or proof of HCFJ's retail encrypted delivery. That downloader does
not itself verify the RSA field in the cited path.

`inspect_version_capture` supports only a **local inspection shape** of 328 bytes
(320 envelope plus eight opaque bytes), with local `Wc24`, version-1 and type-1
header guards. The retail IOS header policy and a genuine HCFJ wire sample remain
unverified. The inspector does not decrypt, verify the signature or bind those
eight opaque bytes to a valid decoded version record. Metadata explicitly keeps
those claims false. The decoded-VF and opaque-capture inspectors are separate;
passing one does not establish the other.

`ExperimentalVersionReplay` is an optional manual-mount adapter for inspecting
explicit captured bytes. Construction requires a matching caller-supplied
SHA-256 plus source and rights references. Those references record the caller's
intent; they do not prove origin or authorization. `get('/hcf/version.enc')`
returns the identical original input bytes and all other targets return 404.
It never constructs, repairs, signs or changes the response. There is no
standalone HTTP server, enabled route, redirect or task-provisioning command;
the shared server does not mount it. Its mode is always
`opaque_capture_inspection_experiment`, with usable native delivery false.

## Running the bounded inspectors

```powershell
.venv/Scripts/python.exe tools/inspect_wii_speak_version.py --decoded-vf PRIVATE_FILE
.venv/Scripts/python.exe tools/inspect_wii_speak_version.py --capture PRIVATE_CAPTURE
.venv/Scripts/python.exe -m unittest tests.test_wii_speak_version
```

The CLI reads at most the selected local limit plus one byte and emits metadata
only. It sanitizes failures rather than echoing private file paths or contents.
No sample response, source bytes, key, device ID or release metadata is included.

The native harness executes the fingerprinted original constructor, VF reader,
error mapper and the two word-consumer slices in synthetic RAM. Allocation, VF
path/mount/open/size/read/close/unmount and SDK error-state queries are explicit
mocks. Code, reads and writes are bounded; object and stack guards are checked.
It cannot establish filesystem, IOS crypto, scheduler, server, account, voice,
audio, Message Board or UI behavior. Its original executable is optional and the
native tests skip when that private input or Unicorn is unavailable.

Remaining blockers are a genuine authorized version capture, original IOS
encryption/signature and task-registration confirmation, exact current-provider
policy, and native coordinated testing. The DWC/friend/voice/microphone paths
are still a separate investigation. This batch does not claim Wii Speak is ready
for an end-to-end user test.
