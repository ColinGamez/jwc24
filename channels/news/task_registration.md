# News task registration and slot mapping

October 26, 2026. This extends the [buffer-format investigation](format.md)
through actual original callers and the reader's slot loop. No task database,
emulator profile, real Wii backup or service endpoint was changed.

## Original call chain and scope

The Japanese HAGJ v7 DOL is pinned by SHA-256
`8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852`.
The original code and derived disassembly remain private.

Static tracing establishes these distinct operations:

1. The startup state machine queues an existing-data read through
   `0x80040C0C`. The worker's kind-zero path calls the original loader at
   `0x800427E4`. Its missing/unusable-task path can invoke registration at
   `0x80043178` with original default interval/count arguments 30 and 240.
2. After buffer validation, calls at `0x8000851C` and `0x80008610` pass the
   selected buffer's byte at `+0x2F` and halfword at `+0x5C` to job creator
   `0x80041514`. That creator preserves nonzero values; zero selects 30/240.
3. The queued kind-two worker path reads those descriptor fields and invokes
   `0x80043178`. Its original branches can create a missing task or update an
   existing matching task's count.

The harness executes the job creator and the registration caller separately.
It does **not** execute the complete startup state machine, real message queue,
worker scheduling, open-library/readiness/settings gates or actual IOS writes.
The static connection between those phases is not a live first-run test.

## Captured native registration intent

For a synthetic missing-task result, the unmodified registration caller makes
one add-task call with the following observed setter arguments:

| Boundary | Original caller argument |
| --- | --- |
| SDK task initializer | `1` |
| Virtual-file size | `0x3A0000` bytes |
| Base URL | Descriptor's explicit URL pointer |
| Server interval | `1440` |
| Subtask parameters | mode `2`, mask `0x00FFFFFF`, flags `0x0103` |
| Priority | `100` |
| Task flags | `0x40000000` |
| Interval | Caller-supplied value, normally forwarded from the job creator |
| Retry margin | `720` |
| Local base filename | Original integer formatting produces `2.bin` |
| Count | Caller-supplied halfword, sign-extended at the setter boundary |

These are observed calls, not proof that the SDK accepts or commits arbitrary
values. A matching synthetic existing task follows the update path without
initializing a replacement. Injected setter/add failures stop later operations
and enter the original error path; successful mocked SDK returns are never
reported as a real registered task.

The application's descriptor halfword **2** is distinct from the initializer's
argument **1**, the actual SDK-assigned task identifier, and the task-table slot.
Tests use an explicitly synthetic assigned identifier of 5. This evidence must
not be converted into “24 native tasks” or a fixed IOS slot. The existing generic
channel-content manifest provisioner does not implement this News subtask
registration contract.

## Native local filenames and reader order

`0x8007D000`, the original SDK subtask-filename getter, executes with its actual
string copying and formatting helpers. A synthetic task context and base name
`2.bin` yield `2.bin.00` through `2.bin.23`. Its enabled flag selects the suffix;
disabling it preserves `2.bin`. Capacity 9 fits a suffixed name and its terminator;
capacity 8 produces the original insufficient-capacity return. SDK context
availability and the task identity are synthetic prerequisites in this test.

The original reader slice at `0x80042E30` through `0x8004309C` starts with the
hour returned by a mocked calendar service and visits:

```text
hour, hour-1, ... modulo 24, until all 24 slots have been considered
```

Every possible supplied hour is tested. File-name retrieval, file opening,
buffer loading and file closing are explicit stubs in that reader-loop test;
the filename getter is tested separately. An original load-result branch that
stops after the current slot clears remaining synthetic buffer/size references.
This establishes control flow, not that any downloaded file is present or valid.
The clock's live source and its relation to real hourly publications remain
unverified, so the bundle inspector's hourly-coverage flag stays false.

## Remote URL corroboration is separate

The separately reviewed official [Dolphin WC24 download-list implementation](https://github.com/dolphin-emu/dolphin/blob/3eb30c7620b4475b2e0404228ba0d2b238a132f1/Source/Core/Core/IOS/Network/KD/NWC24DL.cpp)
appends a two-digit subtask suffix to eligible URL and local-file requests.
For the all-24-bit News mask, this corroborates the expected `news.bin.00`
through `.23` request shape. This is emulator implementation evidence, not an
execution of the installed Dolphin build or Nintendo's IOS scheduler. Its
snapshot and selected-file checksums are recorded in the validation report.

The original base template is still `news.wapp.wii.com/v2/%d/%03d/news.bin`.
Earlier tracing established the argument order but not the actual console
configuration values or complete locale-selection contract. No invented region,
language or hourly task registration is used to configure a server.

## Verification

```powershell
.venv/Scripts/python.exe -m unittest tests.test_news_tasks
```

Eleven tests cover malformed fixture options, fingerprints, missing and existing
task branches, SDK failures, queue refusal/fullness, all 24 local filenames,
capacity boundaries, all 24 calendar-hour orderings and the early-stop branch.
Native tests skip without the private DOL or optional Unicorn package.

Code/read/write ranges, instructions, synthetic allocations and stack guards
are bounded. Original SDK **caller** branches and integer formatters execute;
SDK task lookup/setters/commit, storage and queue/calendar services are mocked
where stated. Reports contain numeric settings, fixed synthetic filenames and
call names, without source code, credentials, real task URLs or message bodies.

Remaining gates are actual first-run prerequisites and caller configuration,
SDK/IOS registration acceptance, endpoint/trust preparation, real envelope and
decompression handling, scheduler/clock behavior, licensed current Japanese
news, complete freshness and native banner/article rendering.
