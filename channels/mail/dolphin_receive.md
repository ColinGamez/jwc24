# Local Dolphin incoming-mail implementation

October 26, 2026. This is a JWC24 interoperability modification of public
GPL-2.0-or-later Dolphin source, including existing local experiments and the
new persistence/retry fixes. It is not recovered Nintendo IOS code or an
upstream Dolphin feature claim. No channel assets, console files, keys or NAND
contents are in the patch.

## Reproducible source

[The patch](../../tools/patches/dolphin_wc24_mail_receive.patch) targets public
Dolphin commit `cb9df1264526c37ed3901afc622c456e8ee137da`. It includes the receive
implementation, KD check/receive/send integration, configuration URL accessors,
friend confirmation, supporting send-list fixes and CMake/Visual Studio source
registration. It excludes the checkout's separate SSL/socket diagnostics.
The source's GPL notices remain intact. A checkout of that base can use:

```powershell
git apply --check C:/path/to/jwc24/tools/patches/dolphin_wc24_mail_receive.patch
git apply C:/path/to/jwc24/tools/patches/dolphin_wc24_mail_receive.patch
# Configure Dolphin with ENABLE_TESTS=ON using its normal build instructions.
cmake --build build --target tests
# Run the built tests executable, without launching Dolphin:
./tests --gtest_filter="WC24ReceiveTest.*:WC24ReceiveEnvelopeTest.*:FileSystem*"
```

The executable location depends on the generator/platform. A fresh export of
all fourteen affected base files accepted the patch; the resulting files
matched the tested local source. The local Release/MSVC x64 `tests` target
built successfully. That build checkout also contains separate SSL diagnostics;
this does not prove an independently compiled clean production emulator.
The installed emulator executable was not replaced.

## Receive and retry behavior

The KD path requests receive.cgi, parses a complete bounded multipart/mixed
response, imports each message into the receive VFF plus its control index and
then requests delete.cgi for the whole batch. The message file is padded to
32 bytes while the index retains its logical length. Existing metadata parsing
covers plain/multipart fields and selected Wii application/command headers.
The existing local startup path refreshes queued metadata and re-announces
retained mail to the scheduler; this is emulator behavior, not native-display
verification.

The new fixes require a successful index read, bounded message sizes and a
read-back of the persisted index before AddMessage returns success. Failed or
short index writes therefore prevent server acknowledgment. Replayed messages
with an explicit Message-ID and the same From/To headers reuse an existing
entry only when all bytes match. Conflicting reuse rejects; equal bodies with
new identifiers remain distinct. From/To scoping accommodates older clients'
fixed registration Message-ID across different friends. Messages without an
explicit ID do not get a guessed retry identity.

The multipart reader accepts the local service's bounded MIME subset, including
quoted/case-insensitive boundary parameters. Delimiters must occur on complete
boundary lines. Inline boundary substrings, longer prefixes and embedded NUL
bytes remain data. Missing closing delimiters or malformed framing reject
before any import or acknowledgment. This is not a general RFC MIME library.

Mail check, receive, send, download and account-registration transactions share
a mutex around the existing HTTP client. Friend confirmation now requires its
status write to persist. Removing a processed friend command commits its index
removal before deleting its VFF file, so a failed cleanup leaves an orphan
rather than an indexed missing file. Existing friend-discovery/send and
registered-generated-identity experiments are retained in the patch; they are
not proof of official account authentication or a replacement for owned device
credentials in other channels.

## Verification and remaining work

Twelve new C++ tests use generated MIME/FAT12 VFF/control/friend files in fresh
temporary profiles, with filesystem faults injected for failed/short index
writes and failed friend-status persistence. Eighteen existing filesystem tests
also pass. No existing profile, live account, provider order or console backup
is used. [The report](../../research/dolphin_mail_validation_20261026.json)
records the patch checksum and exact scope.

A live receive/delete CGI transaction, background scheduling under actual
channel traffic, Wii Menu parsing/display/deletion, real friend acceptance,
attachments/character sets across retained channel notices and original
notification semantics remain unverified. This patch is not installed in the
owner's active test emulator yet. Tests do not establish sudden-power-loss
atomicity, exactly-once receipt, arbitrary MIME compatibility, safe multiple
writers into the same mailbox or the complete stock partial-ack contract.
The backend's count-only acknowledgment limitation remains.
