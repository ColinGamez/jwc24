# Shared Wii Mail delivery state

The shared service provides local account/check/send/receive/delete CGI paths.
It is separate from each channel's notice-generation logic. A queued Demae or
Wii no Ma notice is not proof of a provider order, mailbox import, Message Board
display or the original channel's own notification semantics.

## Retryable batches

Pending mail includes queued `.eml` files and offered but unacknowledged `.sent`
files. Receive attempts replay the same outstanding batch after a connection
failure or service restart. New arrivals remain queued until that batch is
acknowledged. A send retry does not create another copy while identical content
is queued or outstanding.

The batch's `maxsize` budget includes each message's multipart prefix and CRLF
normalization. Metadata/ignored part and the closing boundary are outside that
reported `mailsize`. Oversized front entries do not hide later fitting mail.
The ten-message batch limit is an existing local service policy, not a newly
recovered universal native mailbox limit.

Delete requests must supply a nonnegative `delnum`. JWC24 currently requires
it to match the outstanding batch count. Partial acknowledgments remain
unsupported rather than guessing which messages reached native storage.
Before removing files, the service atomically writes a private retirement
intent. An interruption halfway through deletion can then finish the same
acknowledgment on retry or restart. Entries already covered by that intent
are not advertised as unacknowledged mail. New same-content submissions finish
prior retirement before deduplication, so an acknowledged old file cannot
silently consume a new notice.

A durable random generation marker is committed before a new message is
published. Mail-check flags combine that marker with outstanding queue
identities, ignoring `.eml`/`.sent` transitions. This preserves retry stability
and distinguishes identical content legitimately submitted again after an
acknowledgment. Flags also make older retained entries discoverable if an older
service stopped between message creation and its flag update. File publication
uses temporary files and atomic replacement; no existing mailbox is migrated
or rewritten by installing this code.

## Request and verification boundaries

The listener bounds request bodies, applies an inactivity timeout and rejects
ambiguous/malformed lengths, unsupported transfer framing and truncated bodies
before account or message processing. Storage failures return an unavailable
response rather than accepting mail. Account representations omit identifiers
and credentials. No real device key or account is used in synthetic tests.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_mail tests.test_mail_delivery
.venv/Scripts/python.exe tools/verify_mail_service.py
```

Fault tests cover atomic-publication failure, partial retirement, restart/replay,
same-content resubmission, stale account snapshots, multipart byte boundaries,
request truncation and timeout. This supports one shared service instance with
its thread lock; concurrent independent writer processes, sudden power loss,
exactly-once delivery and a complete stock-client partial-ack contract are not
verified. Direct filesystem copying must not be mistaken for accepted mail.
Count-only acknowledgments cannot distinguish a delayed duplicate delete from
the acknowledgment of a newly claimed batch of the same size. Client ordering
and that stock-protocol edge still require native verification.

This is JWC24 queue/retry policy. It is not code recovered from Nintendo.
The existing public mail implementation references and
[Dolphin's upstream KD implementation](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/Network/KD/NetKDRequest.cpp)
are separate interoperability references, not proof of original service
behavior or a functioning native receive path. A separate
[local Dolphin receive patch](dolphin_receive.md) now captures the previously
untracked importer and persistence/retry fixes, with temporary-mailbox C++
tests. It has not been installed into the active test emulator or verified
through real native receipt/display. No live service, credentials or console
backup was changed. Real receipt remains part of the coordinated validation
pass.
