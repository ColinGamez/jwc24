# Original dataset-task preparation

October 28, 2026. This extends the [read-completion work](completion.md) toward
the native WC24 task required for the Body Check dataset. It supplies local
SDK task-image preparation and original-code comparisons, without creating a
manifest, registering a task, importing keys or changing a profile.

The pinned private decoded HFNJ v256 application is 4,110,944 bytes, SHA-256
`ca6677094a9293219b4122038b916cb64f6361b5b4106a670ade438292d4969c`.
The [validation report](../../research/body_check_task_validation_20261028.json)
contains hashes, numerical boundaries and aggregate scope. Original executables,
resource bodies and signing/encryption material remain private and outside Git.

## Descriptor and SDK contracts

The complete caller `0x8031BEA0..0x8031BF7C` resolves `signkey.key` and
`enckey.key`, allocates an aligned `0x22C`-byte descriptor and invokes its actual
constructor at `0x8031A9A4`. The successful descriptor supplies:

| Observed setting | Value |
| --- | --- |
| Original dataset URL | `http://nwcs.wapp.wii.com/hfn/WiiFitDataAll.enc` |
| Original local filename | `WiiFitData.dat` |
| Flags byte | `0xC0` |
| Flags word | `0x0000000A` |
| Interval and server interval | 1440 each |
| Priority | 100 |
| Opaque word eventually stored at SDK task `+0x1F8` | 0 |

The flags word `0xA` is **not a download count of ten**. The constructor also
stores an opaque word with value 1 at descriptor `+8`; it does not select the
SDK initializer in this preparation path. That word's remaining use is unknown.
No current feed availability or replacement-provider authorization is inferred
from the original URL.

The complete preparation caller at `0x8031A5A0..0x8031A7B0` distinguishes an
explicit synthetic missing task (`-13`) from an existing task (`0`). A missing
task calls the original SDK initializer with **kind 3**. The initialized SDK
image has an unassigned ID `0xFFFF`; neither value is an IOS task-table slot or
an actually assigned task ID. The library/task context is supplied synthetically
in the harness, not read from a console or profile.

Both branches obtain a VFF name and inspect its existence. The observed `-12`
file result requests a VFF of **32,768 bytes**; a zero file result skips that
creation. These are boundary-call observations, not proof of usable VFF capacity
or filesystem persistence. The complete local setter chain at
`0x8031A7B0..0x8031A9A4` applies URL, flags byte, interval, server interval,
priority, flags word, opaque `+0x1F8` word and filename. It invokes key import
only when both descriptor key pointers are nonzero, then requests add or update.

## Local preparation API

`jwc24.body_check_tasks.DatasetTaskConfiguration` requires every identity,
setting, key-presence predicate and evidence reference explicitly.
`prepare_dataset_task(configuration, existing_task=...)` returns an immutable
512-byte **local SDK task image**. It performs no file, task-table, network,
credential, scheduler or key operation. Evidence references are assertions, not
independent authorization or provenance.

An explicit null existing image selects the observed unassigned kind-three
layout. An existing exact image retains its task ID, identity and unknown bytes;
only the selected local fields are changed. Copies include their terminators
and preserve later bytes. For example, replacing a longer filename by a shorter
one leaves the bytes after the new NUL untouched, as the original copier does.

The accepted local subset requires printable ASCII URL/filename bytes, URLs
with the observed HTTP prefixes, at most 235 URL bytes and 63 filename bytes,
the unprivileged setting ranges exercised by the native SDK, and explicit
matching identities for existing images. Those identity/string policies are
stricter than some native contexts. Native string validation permits inputs
that its smaller destination would truncate; the API refuses them rather than
silently rewriting supplied values. It does not claim native rejection of every
input outside its supported subset. SDK context, assignment, database capacity
and permissions remain unverified.

Metadata and representations omit URL, filename, identity words, evidence
references and raw image bytes. Key presence merely reports whether the
observed native import would be requested. No key body is read or generated.

## Actual original execution

`tools/verify_body_check_tasks.py` separately executes:

- The complete original resource/allocation/descriptor caller, including
  successful and failed allocation branches.
- The original descriptor constructor with explicit synthetic configurations.
- The complete missing/existing preparation caller and its original virtual
  result normalization.
- The actual SDK initializer, validation and all eight local setters, including
  their original string copy, comparison and integer-conversion helpers.

The substituted boundaries are context path/app-ID/version access, task lookup,
VFF existence/creation, key import, add/update and external time. All return
values are explicit synthetic fixtures. The time fixture reports unavailable;
the selected native setter retains its observed local-field change without
writing an external task-table time. No initializer, local setter or copy is
replaced by a stub. Native code/data accesses, writes, instructions and runtime
are bounded; immutable input, object, stack and global guards are checked.

The 29 native executions comprise two descriptor branches and 27 preparation
cases: missing/existing images, all key-presence combinations, field/copy
boundaries, existing VFF and selected external failures. Valid local images
match the independent preparation API byte for byte. Failure cases preserve
the native stop order: the selected lookup `-3` and VFF-existence `-1` results
return 16; injected `-1` at VFF creation, key import, add or update returns 12.
A key/database failure can occur
after every local field was written. A matching local image or zero return
therefore cannot establish successful registration or durable task state.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_body_check_tasks tests.test_body_check_completion tests.test_body_check tests.test_body_check_crc_native
.venv/Scripts/python.exe tools/verify_body_check_tasks.py PRIVATE_ORIGINAL_HFNJ_DOL
```

Thirty-two focused tests passed locally, including twelve new tests. Eight
new public tests require neither private software nor native emulation; the
four new native tests skip as a class when the pinned original or optional
dependencies are unavailable. The CLI performs four baseline native comparisons;
the full regression tests cover all 29 cases. It emits metadata only and uses
bounded reads with fixed diagnostics on unavailable input.

## Remaining baseline gates

No task is provisioned or activated by this component. Actual library readiness,
assigned-ID/slot selection, task persistence, VFF size/copy behavior, key import,
RSA trust, scheduler delivery, genuine current dataset, opaque fields, save and
board prerequisites, questions/mail and original screens still require their
own evidence. This does not replace a functioning native flow with a new error
or screen. The owner's actual Wii backup and isolated vWii profile are untouched.
