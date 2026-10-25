# Project-wide restoration checkpoint, October 26, 2026

The full Japanese restoration goal remains active. Four concurrent worker slots
(coordinator plus three workers) produced the scoped code and evidence below.
This is an offline implementation checkpoint, not a finished original-channel
experience or a request to run an incomplete final console test.

## Verified implementation

- Shared WC24 delivery selects each payload's owning title key. Read-only
  multi-manifest preflight checks conflicts, local inputs and optional explicit
  task/account/key-file prerequisites without modifying profiles.
- Shared mail replays unacknowledged batches, budgets multipart overhead,
  preserves new arrivals, and records acknowledgment intent before retiring
  files. Tests cover restart, partial deletion, same-content resubmission,
  storage faults and stalled/truncated requests. Native receive/import/display
  and count-only acknowledgment edge cases remain separate open work.
- Forecast checks all daily/weekly condition references and paired current
  records, locales, windows and optional signatures. The retained pair verifies
  historically but is expired. Observation freshness and installed-client trust
  are not inferred from those checks.
- News has a bounded structural decoder, explicit cross-buffer graph checks,
  original Japanese validator/CRC comparisons, and separate task/filename/reader
  comparisons. One job's 24-subtask intent is not 24 task registrations or a
  fixed IOS slot. Real IOS storage, signature/trust, native decompression,
  current articles and rendering remain unverified.
- Nintendo Channel CSData framing/CRC/decompression and follow-on list-reference
  construction are independently implemented and compared with selected original
  code. The configured endpoint, language eligibility, downloaded records,
  software/video catalog and original UI are still unfinished.
- CMOC ordinary/extended framing and header correlation match a bounded native
  subset. Authentication, FD startup semantics, Mii/search/contest/vote operations
  and their native UI are not implemented by those framing checks.
- Shop has shared pack assembly/offline display checks plus the verified retail
  EC/plugin initialization call sites and an offline IAS GetChallenge component.
  The snapshot renders 2,605 HTML routes and attempts 3,374 dependencies, with
  two missing font paths and four external modified-style references. Full
  Japanese fidelity, runtime startup, registration/signing, accounts, ownership,
  acquisition and installation remain unfinished.
- The provider catalog writer now uses its existing identity registry and a
  cross-process lock with unique atomic temporary files. Public clean-copy tests
  caught the previously unwired committed writer. This does not restore Wii no
  Ma's original Flash shop or make provider products orderable.
- Today and Tomorrow, Wii Speak and Digicam Print have separate evidence-based
  tracks. All 34 owned package contents match their source TMD sizes/hashes;
  Nintendo signatures remain unverified. Fortune has local resource evidence,
  voice has separate WFC/version dependencies, and printing needs a real provider.

## Validation and repository integrity

The initial local worktree suite passed 696 tests. The final local offline
suite passed **862 tests**, with no reported skips. This includes existing
uncommitted experiments and private originals; it is not proof of native UI
acceptance or a claim that unrelated work was committed.

The exported committed/staged code, run without private profile/package inputs,
also passed **672 tests with 280 explicit private/optional skips**. Skip counts
are test-framework counts, including class/subtest skips, not a completion
percentage. The public CI job now installs declared test dependencies and runs
the available offline suite in addition to compilation/package checks. Its
actual remote job result must be reported separately from this local export.

Scoped staged-only checks covered shared preparation/delivery, mail, Forecast,
CMOC, News, Nintendo, Shop and provider publication. Native tests that needed
original files were explicitly pointed at existing private inputs outside the
export; no original bytes were staged. These focused counts overlap the total.

Cross-review caught task-flag/privacy gaps, ignored CSS imports, the distinction
between envelope and observation freshness, mail retirement/retry bugs, encoded
versus decoded News limits, and misleading private-fixture assumptions. Public
fixture gates now skip only absent primary inputs; corrupt or incomplete present
inputs still fail. Synthetic prices/articles/media exist only inside tests and
are never published as channel data.

Completed changes were committed in scoped batches. Older unrelated worktree
edits and experiments remain intact. Proprietary sources/software, media, keys,
NAND data, extraction outputs and test logs remain private and ignored.

## Work that still prevents final completion

The [channel inventory](../channels/README.md) controls the full scope. Continue
from the verified contracts instead of repeating the broad collection searches:

1. Implement actual News transport/registration and signed-data acceptance,
   then acquire authorized current Japanese content. The owner was asked about
   a preferred feed/API; no publisher default or fabricated article was chosen.
2. Recover Nintendo's downloaded list records and full loader/manager lifecycle;
   implement actual software/video browsing and submission contracts.
3. Recover CMOC startup/authentication and real record meanings; connect actual
   Mii discovery, posting, contests, voting and native notices.
4. Finish original Shop screens/assets and source-supported runtime/account/
   entitlement/acquisition behavior. Do not substitute account success or treat
   the catalog as ownership.
5. Complete Demae real variants/orderability/native basket and notice delivery;
   Wii no Ma original-compatible Flash/media/setup; Body Check dataset semantics
   and legitimate Japanese Fit-save prerequisites. Country-wide provider
   retention is not complete delivery/menu coverage.
6. Continue the additional-channel native flows, Wii Speak's actual compatible
   communication service and Digicam's authorized fulfillment contract. Locate
   and verify an Everybody Votes client before inventing its protocol.
7. Finish shared Dolphin mail import/friend behavior, refresh time-sensitive
   inputs, and prepare the coordinated native validation pass for all genuinely
   implemented flows. Real-device findings can still require another fix/pass.

No Dolphin launch, live provider account/order/submission, console installation,
profile/DNS change or actual Wii-backup modification occurred. Tests used local
synthetic HTTP only; public research and Git transport are separate from native
service delivery. The region-changed physical Wii remains a distinct future
validation target. Only the authorized isolated profile may use owned vWii
credentials; no credential migration was performed by this checkpoint.
