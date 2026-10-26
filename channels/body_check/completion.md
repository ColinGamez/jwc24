# Original dataset-read completion and opaque header gate

October 27, 2026. The new offline component extends the existing
[header inspector and CRC proof](header_crc.md) through the complete selected
read-completion consumer and a separate header-pair predicate. It does not add
a download route, synthesize a service dataset, read game saves, or establish
an authenticated/current Body Check service.

## Original paths and bounded scope

The private decoded Japanese HFNJ v256 application remains 4,110,944 bytes,
SHA-256 `ca6677094a9293219b4122038b916cb64f6361b5b4106a670ade438292d4969c`.
No original executable, key, save, header content or genuine record is in Git.
The [aggregate validation record](../../research/body_check_completion_validation_20261027.json)
records numerical boundaries, source-region hashes, counts and limitations only.

The complete consumer at `0x802BBB90..0x802BBD38` receives an existing manager.
Its `+0x60` field points to a buffer object whose downloaded bytes begin after
the four-byte object prefix. The original file-reader wrapper passes a maximum
of `0x8000` bytes. This slice handles the reader's return, the header checksum,
the manager's opaque byte at `+0x20`, and its diagnostic word at `+0x24`.
The native reader itself, storage/crypto and the enclosing asynchronous task
lifecycle are separate boundaries.

| Explicit incoming condition | Observed selected-consumer outcome |
| --- | --- |
| Manager byte `+0x20` already nonzero | Return 0; do not invoke the reader; preserve the buffer and diagnostic |
| Reader result 2 | Return 1 without reading or checking the header; preserve buffer and diagnostic |
| Reader result 0, matching BE32-at-0 versus CRC-32 of bytes 4–15 | Return 1; preserve the buffer and existing diagnostic |
| Reader result 0, mismatching checksum | Clear all `0x8000` buffer bytes, set byte `+0x20` to 1 and diagnostic to -999; return 0 |
| Reader result 5 | Clear the buffer, set the flag, obtain a diagnostic through the existing getter/converter path; return 0 |
| Reader result `0xB006` | Separate original branch: clear the buffer, set the flag and diagnostic -5; return 0 |
| Other reader results | Clear the buffer, set the flag and diagnostic -5; return 0 |

The reader-result values remain opaque. In particular, result 2 is not renamed
“busy,” “missing,” or “success.” **Return 1 alone does not prove that a header
was checked, that bytes were newly downloaded, or that data is usable.** A
CRC-matching result zero does not clear an earlier diagnostic word. Those
distinctions are retained in the new API rather than normalized into success.

The file-read boundary supplies a returned length through a stack pointer.
The selected consumer does not read it after that boundary. Tests with explicit
returned lengths 0, 1, 15, 16 and `0x8000` produce the same checksum decision
for the same prepopulated buffer. This is not permission to accept a truncated
file: the existing inspector's sixteen-byte minimum remains a deliberate safe
policy, and the native buffer can contain prior bytes. Actual reader copy,
reported length, freshness and native consumption require separate evidence.

## Standalone state and header APIs

`jwc24.body_check_completion.evaluate_dataset_read_completion()` requires one
explicit, immutable full `0x8000`-byte **post-reader memory snapshot**, an unsigned
reader-result word, a boolean predicate for the existing latched byte, and a
signed diagnostic. It does not pad a file into a buffer or perform IO. Result 5
also requires an explicit converted diagnostic when that branch executes; the
external conversion is not guessed. The boolean predicate represents the
selected zero/nonzero check; the native fixtures use byte values zero and one.

Its immutable result separately reports the native return bit, reader invocation,
header checks, clear decision, next latched flag and diagnostic. Raw buffer and
diagnostic values are excluded from representations and metadata. It performs
no save or manager write. Metadata explicitly leaves payload meaning, freshness,
authentication, filesystem/crypto and native UI unverified.

`evaluate_header_pair_gate()` preserves the separate original predicate over
the opaque BE16 words at downloaded offsets 12 and 14:

```text
first > 1 OR (first == 1 AND second != 0)
```

`inspect_dataset_header_gate()` composes that predicate with the existing bounded
header-CRC inspector. It retains the sixteen-byte safe minimum and leaves bytes
4–11 and all bytes after 15 semantically opaque. The words are not assigned
invented health, eligibility, service-version, consent or date meanings.

The complete predicate at `0x802BBB10..0x802BBB8C` reads those two words through
the allocated global buffer object. A bounded static caller trace at
`0x802B641C` shows that a true result selects an existing virtual call at vtable
offset `0x130`, with arguments `0x2D` and 1; false selects offset `0x134`.
Neither virtual target nor its screen was executed in this proof. The component
does not substitute a new screen, label or navigation action for either branch.

## Original execution and verification

`tools/verify_body_check_completion.py` executes:

- The complete selected read consumer and original filename/last-diagnostic
  leaf wrappers.
- Original `memcpy`, `memset` and CRC instructions without replacing them.
- The separate complete opaque-pair predicate, including both original two-byte
  copy calls.

Only the actual filesystem-read entry `0x8031A3A0` and diagnostic converter
`0x801D7DFC` are intercepted. The synthetic reader boundary returns explicit
register/length state; it opens no file. Its buffer is explicitly supplied
post-reader RAM, so no provider bytes or fabricated health records are copied.
The diagnostic getter executes, but the converter's mapping remains unverified.

The verifier pins the source, bounds code/data/stack accesses and instructions,
permits only the consumer's observed manager fields and full buffer clear, and
checks all input, object, global and stack guards. Actual helper-entry counts
are checked in every case. Native read hooks prove that this selected consumer
reads only downloaded bytes 0–15 and does not read the returned-length word.
These are findings about this consumer, not every user of the dataset.

Twenty-five read-consumer cases cover all observed branches, prior latched
state, retained diagnostics, valid/corrupt headers, signed diagnostic boundaries,
opaque trailing-byte changes and independent returned lengths. Fifteen opaque
pair cases cover first-word values 0, 1, 2, 255 and 65535 with second-word
zero/nonzero boundaries. Every native outcome matches the independent component.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_body_check_completion tests.test_body_check tests.test_body_check_crc_native
.venv/Scripts/python.exe tools/verify_body_check_completion.py PRIVATE_ORIGINAL_HFNJ_DOL
```

Twenty focused tests passed locally. Six new public tests require no private
material or native emulator; the three new native tests skip explicitly when
the pinned original or optional dependencies are absent. The verifier emits
counts and scope, never original bytes, supplied buffer data or a private path.
An isolated temporary working-directory run passed all six public tests and
reported the native class as one explicit skip, with no private input available.

## Remaining baseline work

The bounded audit found allocation of the raw buffer object and its assignment
to manager `+0x60`; within the inspected manager range, the corresponding data
loads belong to this read/check/clear path. Its only recovered direct global
data read is the opaque pair predicate. **No record-table parser was recovered.**
That absence is not proof that no other consumer exists, or that trailing bytes
are health records. Do not invent a table schema from the filename or generic
WC24 documentation.

Still open are the remaining header meanings, complete dataset contract and
genuine source, native IO/task/envelope/trust, the predicate's downstream screen,
save-backed first-run and returning-user flow, legitimate Japanese Wii Fit/Plus
profiles, board input, questions, mail and native display. No actual Wii backup,
isolated test profile, original save, service endpoint or device was changed.
