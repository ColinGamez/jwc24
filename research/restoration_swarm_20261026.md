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

## Continued implementation after the 17-commit checkpoint

The next swarm used the same four worker slots and committed additional scoped
components rather than rerunning the broad Nintendo index:

- News now builds/signs explicitly supplied native buffers, verifies coherent
  references/signatures/locales/windows, atomically publishes generations and
  serves all 24 binary routes. The shared manifest listener accepts an explicit
  publication/key pair and preserves signed bytes without another envelope.
  There is still no chosen publisher, current article importer/record builder,
  automatic refresh or installed-client trust/IOS/VFF/UI proof.
- Nintendo now decodes selected software titles and linked rows from the actual
  subsequent ListData format. Original constructor/validator/accessor/wide-copy
  checks corroborate that subset. Unknown nonempty tables remain undecoded;
  genuine catalog/media, full loader/authentication and browsing remain open.
- CMOC's FD record now has an explicit-values codec and actual native startup
  state-copy comparisons. Opaque field meanings, genuine values, HTTP/header
  negotiation, encryption/authentication and menu completion remain open.
- Demae now checks combined item consumption, owned variant copying, exact stock
  comparison, native price formatting and basket-code reselection. Explicit
  zero yen remains valid structural data. A separate conservative candidate
  gate does not confer orderability. All 38 retained branch observations remain
  expired and their 248 parent items lack provider IDs/variant rows; no item
  route, order or notice was enabled using those incomplete observations.
- Existing local Dolphin incoming-mail source was located and captured in a
  public GPL patch against a pinned upstream commit. Index/friend write failures
  now propagate, replay IDs preserve distinct real notices and MIME boundaries
  must be complete lines. Twelve new generated-mailbox/MIME tests and 18 existing
  filesystem tests pass. The installed emulator and all existing profiles are
  unchanged; native receipt/display and a live receive/delete transaction remain
  unverified. Source/build distinctions are in the dedicated mail report.
- Wii Speak's actual VF version reader and two word consumers are compared in
  guarded RAM. Exact 8-byte inspection is a stricter local completeness policy;
  constructor defaults are never generated as a service reply. Opaque capture
  replay remains an unmounted experiment with crypto/delivery/voice false.
- Body Check's existing header-only component was reviewed and committed with
  a fixed CLI error that excludes paths. The original CRC matches 67 synthetic
  twelve-byte cases with guarded reads and no native writes. Records, medical
  meaning, authentication, legitimate saves and native flows remain unverified.

Three inspector entry points also work directly from the source checkout
without an installed project package. Source-only command checks are separate
from the native comparisons. Private originals and GPL emulator changes are
not interchangeable provenance categories.

## Validation and repository integrity

The earlier checkpoint's initial local worktree suite passed 696 tests and its
then-final offline suite passed **862 tests**, with no reported skips. This includes existing
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

## Latest continued validation

The complete current local worktree passed **939 Python tests with no reported
skips** in 235.673 seconds. This includes older uncommitted experiments and local
private/optional inputs; it is not an assertion that all those experiments were
committed or that any native application is complete.

A corrected export containing every tracked test module passed **776 tests,
with 208 reported skips**, in 75.165 seconds in the local environment. This is
tracked-code validation, not an environment isolated from every external tool
or fixture path. An earlier intermediate export omitted the new CMOC test
module; it was corrected before this complete export run. No original bytes
were copied into the export or staged.

Actual GitHub CI on the complete implementation checkpoint
`f4a88d4fb7ce5a3dc002dd203adc7c4fe235d5cb` passed **740 tests with 303 reported
skips** in 14.998 seconds (run 40248819221, job 121336026642), including compilation
and package checks. Class/subtest skip accounting, optional dependencies and
available external fixtures make these counts distinct; none is a completion
percentage. Native private comparisons cannot be replaced by a skipped CI test.

The local Dolphin `tests` target built and passed 12 new receive/MIME tests plus
18 existing filesystem tests. Its full `dolphin-emu` application candidate also
built successfully in the separate source tree. That tree contains existing
SSL diagnostics; a clean patch-only application build is not claimed. The
candidate was not launched or copied over the installed emulator. Its private
binary identity and the public patch identity are recorded in the mail report.

Three source-checkout inspector entry points passed isolated `--help` checks
without an installed JWC24 package. These are command-loading checks, not
additional native service acceptance.

## Work that still prevents final completion

The [channel inventory](../channels/README.md) controls the full scope. Continue
from the verified contracts instead of repeating the broad collection searches:

1. Connect the implemented News publication/routes to verified client trust,
   native registration/VFF acceptance and authorized current article inputs. The owner requested source investigation. The original-provider and
   alternative reviews record NTV/Reuters candidates and access gaps; no
   provider, account or article feed was enabled.
2. Extend the partial Nintendo ListData reader to the remaining genuine tables
   and full loader/manager lifecycle; implement software/video browsing and
   submission contracts from actual source data.
3. Complete CMOC FD field meanings, retrieval/authentication and startup;
   connect actual
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
7. Review/install only an isolated Dolphin mail candidate, verify live CGI,
   scheduler/import/friend/display behavior, refresh time-sensitive inputs and
   prepare the coordinated native validation pass for all genuinely
   implemented flows. Real-device findings can still require another fix/pass.

No Dolphin launch, live provider account/order/submission, console installation,
profile/DNS change or actual Wii-backup modification occurred. Tests used local
synthetic HTTP only; public research and Git transport are separate from native
service delivery. The region-changed physical Wii remains a distinct future
validation target. Only the authorized isolated profile may use owned vWii
credentials; no credential migration was performed by this checkpoint.

## Continued backend work after the 28-commit checkpoint

Seven implementation commits now connect additional actual backend operations:

- Explicit News records encode all six tables with supplied text/dates/IDs,
  explicit opaque fields, aligned storage and CRC. A private raw+provenance
  directory is atomically built; the existing signer/publisher can consume it.
  Loopback tests exercise encode/sign/publish/reload/download and exact text.
  The complete original article display constructor also preserves supplied
  titles and optional source suffixes. The separate ticker table's consumer,
  image decoding, live provider ingestion/trust and original UI remain open.
- HBNJ opt-in coherent publication snapshots all 112 inputs and captures 109
  regional/header routes. The shared listener applies existing title-owned
  encryption/compression and rejects expiry, unknown areas and route conflicts
  without stale/national fallback. The captured generation does not hot-reload.
  Argument-free legacy refresh remains operational; it retains its older
  per-file publication with atomicity unverified. New activation requires an
  explicit source-checkout command and isolated key input, not a profile edit.
  Wheel-only snapshot validation remains unsupported because the validators
  currently reside in the source checkout's tools directory.
- Wii no Ma's four retained submission experiments now bind their XML response
  to an actual committed SQLite receipt. Legacy JSON formatting/Unicode retries
  canonicalize without erasing old rows; ambiguous duplicate keys roll back the
  entire migration. POST/storage failures cannot return the static acknowledgment.
  Bounded shared HTTP framing and UTF-8 form checks protect neighboring routes.
  Original result-code/request meanings, eligibility, aggregation and UI success
  remain unverified; a receipt is not a counted original Nintendo vote.
- Shop's complete original CheckDeviceStatus request/response extraction and
  sync-decision consumer run from both original worker dispatch sites. The
  explicit-facts serializer and pure update plan preserve partial-state/error
  distinctions without assigning a connected account. Real registration,
  authoritative authenticated balances, persistence and full startup remain open.
- Forecast provider-age receipts are separate from native clock words. Review
  caught an incorrect first gate equating those clocks; it was corrected before
  the implementation checkpoint was pushed. Original code uses record+4 minus
  record+8 as a location-clock offset added to system time. Legitimate clock
  rebuilding is allowed; stale provider receipts still reject even with a new
  clock/fetch/hash. No real weather source was refreshed or private code changed.

The targeted weather audit found no retained raw provider body/header cache.
Old helpers discard headers and their outputs do not preserve independent
provider dates. Historical overseas weather substitution, unknown precipitation
converted to zero, repeated daily/six-hour values, copied wind and fixed indices
remain separate reasons not to approve that pipeline as current data. Timestamp
semantics are now documented carefully; native location clocks are not falsely
called observation timestamps. Original missingness evidence is static and does
not yet make every normalized field or display path complete.

The [Demae source check](demae_menu_access_20261026.md) found no verified current
provider variant/stock tuple or machine-feed contract. Personal/private-use
terms are distinguished from broader redistribution; no page-read permission,
stock fact, availability or merchant authorization was fabricated.

### Current verification

The complete current local worktree passed **1,011 tests with no reported skips**
in 377.995 seconds. It includes older uncommitted/private experiments, as before.
A staged-only export separately passed 37 receipt/shared-News/HBNJ/key-owner/
readiness checks, proving the new server behavior did not depend on unrelated
worktree edits. Scoped native comparisons and source checks overlap this total.

Actual GitHub CI on `03711bb42f07435d4312e8c383683f7276f65aea` passed **811 tests
with 315 reported skips** in 23.627 seconds, plus compilation/package checks
(run 40254534747, job 121353439062). Those skips remain private/optional evidence
gaps, not original-channel verification or a completion percentage.

No emulator was launched, installed executable replaced, native service restarted,
provider article/menu/weather/TV feed collected, real account/contact/order/notice
created, credential migrated or actual Wii backup accessed/modified. HTTP tests
used synthetic local fixtures; the separately identified public web research and
Git transport do not constitute channel/service delivery.
