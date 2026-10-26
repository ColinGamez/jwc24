# Coherent HBNJ refresh publication

The October 26, 2026 updater offers an explicit `--coherent` mode that publishes
a complete immutable generation and one atomic `current.json` pointer. The
existing default/`--legacy` mode is preserved: it validates a staging tree, then
replaces live files individually. Its sequence could expose a new header with
an old regional EPG/string pair; whole-guide atomicity is unverified. Preserving
that functioning experiment does not turn it into a validated coherent service.

The new path supports a supplied local normalized guide, with no network use:

```powershell
.venv/Scripts/python.exe tools/update_hbnj_daily.py `
  --coherent `
  --guide-file PRIVATE_NORMALIZED_GUIDE `
  --output-root channels/hbnj/generated/snapshots `
  --rights-ref PRIVATE_SOURCE_PERMISSION_REVIEW `
  --max-collection-age-seconds EXPLICIT_LOCAL_POLICY
```

The two final arguments are required in coherent mode deliberately. A rights reference records
the owner's review; it is not independent authorization. The maximum collection
age is an explicit local policy, not a measured publisher correction/issue
frequency. Coherent mode is opt-in; the existing argument-free updater remains
backward compatible and the daily wrapper now selects `--legacy` explicitly.
It continues the old collection, validation, guide archiving and per-file
`generated/current` output without inventing permission or an age policy.
It does not activate the new snapshot path or claim its guarantees.
Omitting `--guide-file` retains the existing collector branch, which was not run
in this batch. This work does not establish new Bangumi reuse permission.

The pipeline keeps the supplied guide bytes and schedule dates unchanged. It
checks the normalized national schema, packs the existing native structures,
builds all 54 regional pairs, copies all bytes to an owned staging generation,
then independently validates the copied guide, national/header payloads and
all regional EPG/string relationships. Existing per-area LZ10 and four-MiB
payload budgets are retained; filesystem overhead and native storage acceptance
are not newly proved. No station, program, description or empty slot is invented.

In coherent mode, source collection time must be timezone-aware, not future-dated and strictly
younger than the chosen policy. Independently, every station's first supplied
program must have started and its last supplied program must not have ended.
Program timestamps use the existing packer's JST clock convention: naive
normalized times mean JST, and aware times must carry UTC+09:00. This avoids
silently dropping another offset. These checks establish collection age and
schedule range, not a publisher issue time, a correction SLA, or gap-free
broadcasting. No publication time is substituted for a program time.

Each generation contains the private `guide.json`, the three national/header
files, 108 regional files, and a metadata/hash manifest. Local bounds are 64 MiB
per input and 256 MiB per generation; these are tooling policies. Publication
serializes through the existing cross-process OS directory lock, renames the complete staged directory,
then atomically replaces the pointer. Failure preserves the old pointer. A
complete orphan generation may remain if the pointer replacement fails. Old
generations and legacy `generated/current` files are never deleted or replaced.
The persistent `.publication.lock` file is not a stale marker: the OS releases
its actual lock when an updater exits or is killed, so another update can retry.
Cleanup resolves and checks its owned staging directory beneath the explicit
output root before recursive removal.

## Runtime snapshot integration

**Current implementation requires a source checkout.** The loader invokes the
existing `tools/validate_hbnj_guide.py`, `tools/validate_hbnj_payloads.py` and
`tools/validate_hbnj_area_payloads.py` beneath that checkout. The installed wheel
currently includes only `jwc24*`, so wheel-only `--hbnj-root` serving is not
supported by this batch. Missing validator tools fail closed. Packaging-safe
validation resources are a separate integration task, not a reason to skip the
independent checks or claim installed-package runtime coverage.

`jwc24.hbnj_publication.load_hbnj_snapshot(root)` reads one pointed generation,
checks contained paths, all recorded hashes and current source/schedule ranges,
repeats independent binary validation, and verifies that files did not change
during it. The returned `HBNJRouteSnapshot` holds immutable in-memory bytes for
exactly these raw payload routes:

- `/header.bin`
- `/1001/epg.bin` through `/1054/epg.bin`
- `/1001/str.bin` through `/1054/str.bin`

`snapshot.raw_payload(request_target)` returns the exact frozen **raw HDPK**
bytes, or `None` for an unrecognized target. It raises `HBNJSnapshotExpired` at
the earlier of the collection-age limit and any station schedule's end. The
server must map an expired recognized route to a retryable failure and must
not fall back to old/national data for unknown or expired regional routes.
The supplied `now` argument is only for deterministic offline checks; normal
serving uses the current clock.

The shared server must capture this object once at startup and apply the
existing HBNJ LZ10/WC24 envelope using the correct title's private key file.
These bytes are not a ready encrypted wire response. The snapshot component
never reads a NAND key or changes IOS tasks. A later publication changes only
the pointer; an already running prepared snapshot stays coherent until explicit
reload/restart, rather than switching individual responses mid-session. New
server mounting belongs to the separate shared integration batch.

## Validation

`tests/test_hbnj_publication.py` uses generated synthetic schedules only. It
executes the full offline 54-area/eight-day build path, independent parsers,
publication and load. It checks generation switching, all regional route bytes,
tamper/path rejection, stale/future collection, old schedules, exact expiry,
failure cleanup, pointer replacement failure and legacy-file preservation.
It makes no provider, account, profile, task or network calls. Native UI,
correct transport crypto, live freshness and actual program accuracy remain
unverified by these tests.

## Shared manifest listener

The source-checkout CLI can attach one validated generation while retaining the
existing HBNJ compression and key ownership:

```powershell
.venv/Scripts/python.exe -m jwc24 serve channels/hbnj/channel.json `
  --base-url http://127.0.0.1:8080 `
  --hbnj-root channels/hbnj/generated/snapshots --nand-root PRIVATE_ISOLATED_NAND
```

These paths require actual prepared inputs; no default profile is selected.
The listener requires the HBNJ title and three native task transport modes.
Its supplied snapshot replaces only those tasks' legacy payload-file reads;
missing legacy current files do not prevent snapshot use. All 54 regional pairs
and header use that snapshot with LZ10/WC24 encryption under HBNJ's own key.
Unknown areas and arbitrary suffix aliases return 404, and expiry returns 503;
neither falls through to stale or national data. Other manifest routes remain
available. Two loopback/CLI tests decrypt and inspect every one of 109 routes,
check conflict/expiry behavior and prove a changed pointer cannot mix requests.

The generation is captured once at startup. Publishing another generation does
not silently activate it in an ongoing server. Explicit restart/activation and
the original task/download refresh handoff remain runtime work; these tests do
not prove a complete live daily-update lifecycle or native display.
