# Original header gate and channel-update notice

October 28, 2026. The [opaque header-pair predicate](completion.md) now connects
to its selected original caller, vtable transition, later selector phase and
message resource. This recovers an existing notice without creating a new
screen, rewriting Japanese text or assigning version meanings to header words.

The pinned private HFNJ v256 decoded application remains 4,110,944 bytes with
SHA-256 `ca6677094a9293219b4122038b916cb64f6361b5b4106a670ade438292d4969c`.
The private `health_message.bmg` is 24,160 bytes with SHA-256
`22049c1e62a52e1d0d6ba3000aca6d4c07aed50128a476ee1818bc6e784a7b27`.
The [validation report](../../research/body_check_notice_validation_20261028.json)
records numerical boundaries, source hashes, aggregate results and limitations;
it contains neither message text nor original assets.

## Observed path and message binding

The factory at `0x8022B92C..0x8022B940` installs primary vtable `0x803E8628`.
Its separate interface table begins at primary `+0x28`. Resolving methods from
the primary pointer matters: offsets `+0x130` and `+0x134` select
`0x802B6880` and `0x802B67D8`, respectively.

The complete selected caller at `0x802B63B0..0x802B6470` first evaluates two
context-word predicates and a manager byte. Their complete meanings remain
opaque. If the first context word has mask `0x300`, it returns without reading
the header. A nonzero manager predicate, or the selected secondary-context
predicate, chooses a separate context/error handler. That handler remains
outside this handoff; it is not replaced with an invented result.

For the supported header path, the original predicate reads only the two
halfwords at downloaded offsets 12 and 14. Its existing result controls:

| Predicate result / explicit phase | Observed intent |
| --- | --- |
| False | Set native state `0x2B`; invoke the separate secondary-context entry `0x80230DA8` |
| True, transition phase | Set state `0x33`, store selector `0x2D` and control 1; request an existing dialog close if it is busy |
| Later selector phase, dialog still busy | Retain the queued state; no message request |
| Later selector phase, dialog not busy | Enter state `0x2D` and request message `0x754C`, variant 0 |

The original transition, complete selector at `0x802B6DE8`, primary-vtable
dispatch and message-request method at `0x802B8920` execute in the verifier.
An explicit later phase is required: the code does not infer that a dialog is
closed just because a close was requested. The two busy predicates are sampled
independently, preserving asynchronous behavior.

The selected resource is an existing **Body Check channel-update announcement
that directs updating the channel through Wii Shop**. This identifies the
notice's purpose; it does not establish that the two header words are a version
tuple, that an update is currently available, or that the notice rendered.
Original Japanese copy remains private and unchanged.

The resource binding is independently checked by executing original BMG
constructor `0x800C1ED4` and getter `0x8023522C`. With message `0x754C` and
variant 0 they select MID entry `0x754C00`, returning the exact retained resource
record at offset `0x451C`. Neither constructor nor lookup is replaced by a stub.

## Immutable-title resource membership

The optional read-only audit checks the pinned retained stock WAD and source
TMD, decrypts only content index 2, verifies its TMD hash/size and expected
content SHA-256, then selects the unique `message.carc` member. A bounded Yaz0
decode and nested U8 lookup recover `health_message.bmg` in RAM and compare all
bytes with the retained resource.

This establishes exact membership in that retained title artifact. It does not
verify Nintendo's signatures or independent provenance of the enclosing WAD.
No original bytes, title key, resource body or message text are written to Git
or included in reports. The audit does not read the owner's actual Wii backup,
modify any title/profile, or run original software on a device.

## Offline API and verification scope

`jwc24.body_check_notice.plan_header_notice()` requires the opaque pair result
and explicit context predicates, including whether to advance the selector and
its independently sampled later dialog state. It returns a pure state/message
request decision. Context/error branches outside the proved slice raise
`BodyCheckNoticeUnsupported` rather than claiming the original handler's result.

`inspect_dataset_notice()` connects that decision with the existing bounded
plaintext-header inspector. It requires the sixteen-byte/CRC safety policy
when the path consumes a header. A context-blocked path does not claim a CRC
check or require fabricated padding. The CRC covers only bytes 4–15; arbitrary
trailing bytes, freshness, cryptographic validity and payload meanings remain
unverified. The isolated native predicate itself does not perform that CRC
check, so the inspection policy is deliberately stricter.

The native verifier runs fifty flow cases covering false/true opaque pairs,
separate UI phases, busy-state changes and context masks. Only UI message/close,
secondary asynchronous entry and the unsupported alternate-handler boundary
are mocked. Actual context getters, manager predicate, header predicate,
vtable targets, transition and selector execute. Code, reads/writes, inputs,
state, globals, stack, instructions and runtime are guarded. A separate actual
BMG constructor/lookup comparison adds one resource-binding case; the WAD
membership audit is separate file/format evidence, not native UI execution.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_body_check_notice tests.test_body_check_tasks tests.test_body_check_completion tests.test_body_check tests.test_body_check_crc_native
.venv/Scripts/python.exe tools/verify_body_check_notice.py PRIVATE_HFNJ_DOL PRIVATE_HEALTH_MESSAGE_BMG
```

Forty-three focused tests passed locally, including eleven new tests. Seven new
public tests need no private original or native emulator. Native tests and the
optional source-WAD membership test skip truthfully when their inputs or
dependencies are absent. The CLI checks one full notice path and the message
binding, emits metadata only and bounds its file reads.

Still required are the alternate handler, real asynchronous/service lifecycle,
actual embedded-message rendering and dismissal, complete header/payload
meaning, genuine current source, trust/task delivery, legitimate game-save and
board prerequisites, and remaining original questions/mail/UI. No native
application, profile or service was launched, and no substitute screen or
production dataset was introduced.
