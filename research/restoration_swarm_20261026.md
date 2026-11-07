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

## October 27: preparation, deployment and additional native consumers

Seven further scoped code commits through `e4b292f` add the following, without
changing original UI assets, selecting providers or activating a console:

- Preflight loads the same explicitly selected News/HBNJ publications as the
  server and shares their ownership, transport and route-conflict contract.
  Only actual HBNJ snapshot-owned tasks bypass missing legacy file checks;
  unrelated payloads still fail. Snapshot expiry is separate from file mtime.
  News' generic-manifest checks explicitly do not implement native SDK subtask
  registration. A clean staged export passed 29 related tests independently
  of the older uncommitted server experiments.
- HBNJ's independent guide/national/regional validators now ship in the wheel.
  Their checks are preserved; old tools remain compatible entry points. Two
  actual wheel tests passed outside the checkout in a fresh environment,
  including all 109 decrypted/decoded routes and content/expiry/conflict
  rejection. A reproduced working-directory shadow-package bypass is prevented
  by the child interpreter's safe-path option and explicit package path.
  Collection/packing still use source tools; automatic runtime activation and
  genuine current provider data remain open.
- Forecast preserves explicit daily probabilities `0..100` and unavailable
  `255`, and rejects invalid source values rather than substituting zero.
  Current temperature packing rejects overflow instead of wrapping into a real
  value or the `-128` missing marker. Compact-only tables now point at their
  actual data offset rather than zero. Thirty-seven focused tests passed.
  The separate original-code proof checks 1,024 probability slot/byte cases
  with protected code/input pages and immutable guards. It is an isolated
  validation block, not full native weather validation or rendering.
- CMOC now connects its existing FD decoder to the complete observed response
  gate and actual SDK header/numeric behavior. There are 284 full-handler and
  32 SDK accessor comparisons. Missing-request/incomplete-body zero completions
  cannot become checked-header success. The original `%03d` conversion reads
  three characters, including signs: `0100` becomes 10. Missing/malformed
  values leave initialized zero; that is not authentication. Actual socket
  construction, host overrides, requests, genuine Mii data and authorization
  remain unimplemented.
- Shop's registration-sync path now runs from the actual worker call through
  original XML, response extraction, account assignment and token derivation.
  The exact signed challenge bytes differ from escaped SOAP field text. The
  standalone component requires explicit facts and returns a pure state plan;
  88 focused startup tests passed, including 23 new registration tests.
  Unregistered, expired-token, partial response and failed-save outcomes remain
  distinct. Signing/certificate authority, replay/session binding, durable
  registration and the full original startup/acquisition flow are still open.

The new components use synthetic fixtures. Original binaries, SDK material,
private keys and device backups remain outside Git. No original title was
patched or launched, and no actual Wii backup, isolated vWii profile, real
provider feed, account, order, vote or notice was changed by this batch.

### Verification at `e4b292f`

The full current local worktree passed **1,058 tests in 372.458 seconds**, with
one explicit skip for the optional local wheel-build backend. The separately
executed clean-export installed-wheel tests passed both cases in 97.5 seconds.
The full worktree still includes older uncommitted experiments; its broad pass
does not turn those experiments into reviewed commits or original experiences.
The private full-run log is `private/swarm-sixth-full-20261027.log`.

The seven code commits through `e4b292f` are pushed. That checkpoint's local
evidence does not cover subsequent implementations, newly acquired provider
content or real-device behavior. Tests use original software only as private,
pinned comparison inputs and synthetic data as service fixtures. The complete
channel inventory and its unresolved gates remain the completion criteria.

GitHub CI for full commit `e4b292fd26cdff9a1ca9adc2663eb86e0c85f328` also
passed compilation, package installation and **856 tests with 332 reported
skips** in 24.692 seconds (run 40421240916, job 121915925310). The public
checkout's private-fixture/optional skips are not native or full local evidence.

## October 28: native request/receive paths and durable Shop proofs

Eight implementation/test commits after `cdd1115` now cover the next completed
slices. A separate bounded Forecast source-audit note records actual negative
provenance evidence rather than treating retrieval as a weather update.

- Nintendo's CSData language predicate feeds an exact-byte ListData handoff.
  Original raw/LZ10/LZ11 installation executes through constructor, validator
  and publication. The raw branch copies its full configured allocation;
  that allocation and its synthetic tail are distinct from received data.
  The async callback/poll component preserves retained versus skipped bytes,
  retry resets and raw versus manager-normalized errors. Its 157 native
  comparisons show why a zero normalized result can still accompany a failure.
  The inner request-manager, real endpoint response and genuine catalog/media
  remain unverified.
- CMOC's complete FD descriptor constructor, original formatting and actual
  configuration predicate now match an explicit producer. Word 4 selects the
  decimal target; word 8 stays in the correlation prefix; the cached tail is
  caller-supplied because native construction leaves it unchanged. Canonical
  target decoding can be used by a future backend. Twenty-three original
  comparisons and the 47-test CMOC regression pass. Actual SDK setup, socket
  serialization, `.ces` processing, identity and real first-data responses remain
  unfinished.
- Body Check's full selected read consumer and opaque-pair gate distinguish
  unchecked result 2, CRC decisions and retained diagnostics. Its task producer
  matches original SDK initializer kind 3 and eight local setters, preserving
  existing identities and unknown bytes. Twenty-nine task-side native cases
  execute 192 setter entries. Prepared images and zero native returns do not
  establish VFF/task persistence, key import, real delivery or health-record
  meanings. No downloaded health-record table has been recovered.
- The Shop verifier checks AP-certificate and challenge signatures under an
  explicit NG-certificate pin, with the original 60/384-byte signing wrapper and
  Base64 path independently executed. Four narrowly selected private SDK headers
  strengthen layout evidence; public Dolphin crypto remains separate emulator
  corroboration. No Nintendo CA chain, enrollment or exclusive key possession
  is inferred from a caller pin.
- The new challenge store issues genuine local eleven-byte challenges and
  commits operation/device/title-bound issuance before returning IAS bytes.
  Actual crypto precedes an atomic, expiry-rechecked single-use receipt. Race,
  restart, replay, changed issuance and actual SQLite COMMIT-denial cases pass.
  The composed native test runs GetChallenge construction/response reading,
  signing wrappers and registration SOAP with full 512-character certificate
  fields into real local proof consumption. It deliberately supplies a reported
  registration error, preserving the distinction between proof receipt and
  account assignment. The combined 74-test Shop suite passes. Account authority,
  durable registration, complete startup and acquisition remain open.

The [Forecast source capture findings](forecast_source_capture_findings_20261028.md)
record exactly two approved requests. The checked daily epochs are consistent
with effective dates, not an established issue time. The observation selector
also fails on the retained HTML sample. No genuine source-age receipt, normalized
weather, reference substitution or active payload was generated. No provider API
credentials were found in the bounded configuration check; broader access and
full source-time evidence remain unresolved. Request details and provider code
remain private under the existing source policy.

### Verification at `91f54c0`

The complete current local worktree passed **1,137 tests in 370.111 seconds**
with one explicit optional-wheel-backend skip. Its private UTF-8 log is
`private/swarm-seventh-full-20261028.log`. As before, it includes older
uncommitted experiments; their passing tests do not make those changes reviewed
commits or native completion. Subsequent implementations require their own checks.

GitHub CI at full code commit
`91f54c073776ece8fe5e573ef17b2866b701c17b` passed compilation, package installation
and **921 tests with 343 reported skips** in 28.392 seconds (run 40560768610).
The public/private evidence scopes remain separate. No physical console,
emulator launch, profile, real account, order, vote, notice or actual Wii backup
was changed. Original software, SDK headers, keys, provider code and captures
remain outside Git.

## October 28: dated public weather input and original consumer constraints

Six scoped commits after `5693036`, through `3cdf64e`, add the following
implementation and evidence. They have been pushed; none activates a provider
or changes an installed title/profile.

- Nintendo ListData tables 1 and 2 now preserve inline names, raw identifiers,
  row order, duplicates and first-match relationships. The original classification
  consumer maps kinds outside 1..10 to `FF`; that is distinct from rejecting
  a record. Seventy Nintendo-focused tests pass. Full table meanings, genuine
  catalog/media, transport/authentication and native browsing remain open.
- Body Check's original opaque-header decision is traced into its update-notice
  transition and privately bound to the actual embedded message resource.
  Fifty native flow cases and an original message constructor/getter comparison
  support the projection. This is not a recovered health-data schema or a
  verified rendered screen; the original header words remain opaque.
- Forecast's original validator accepts wind direction zero. The public range
  check now preserves it, with a regression for every native record form.
  Original Japanese formatting selects km/h, not the JMA source's m/s. Calm
  plus missing speed exposes an original invalid-read boundary in two isolated
  synthetic cases; missing wind cannot safely be replaced with a guessed zero.
  Primary condition keys and secondary graphical selectors are independently
  checked; provider codes cannot simply be copied into graphical selectors.
- Original index validation, first-match lookups, availability and selected
  display branches pass 10,426 comparisons. `FF` can still match a supplied
  dictionary entry; using a missing byte alone does not establish that an
  unsupported UV/laundry/pollen card disappears. Actual graphics remain outside
  this intercepted-boundary proof.
- The owner confirmed that no Weathernews API configuration or permission-letter
  file is available and authorized the best public alternative. The previous
  permission assertion is not independently verified. A new opt-in JMA parser
  and bounded four-request capture utility preserve real provider issue and
  observation dates separately from forecast targets and retrieval time.
  Thirty-five focused tests pass, including atomic-export failure handling.
  Four actual official GETs produced a complete private source-record bundle;
  this is source acquisition, not native weather publication or national coverage.

The [JMA source contract](../channels/forecast/jma_source.md) records terms,
credit requirements and the remaining exact area/station associations,
temperature roles, unit conversion/quantization, condition graphics, native
attribution, source-age policy and global-coverage gates. Missing sky conditions
and indices remain missing. No historical values or invented measurements were
substituted. The private Weathernews experiment remains unchanged.

### Verification at `3cdf64e`

The complete current local worktree passed **1,209 tests in 329.269 seconds**,
with one explicit skip for the absent optional wheel-build backend. The private
UTF-8 log is `private/swarm-eighth-full-20261028.log`. This run covers the six
new scoped commits and still includes older uncommitted experiments; their
passing tests do not make them reviewed changes or native completion.

GitHub CI for full code commit
`3cdf64e759aa7fc5d7c9b317c9535153fc6c6354` passed compilation, package installation
and **985 tests with 349 reported skips** in 28.622 seconds (run 40568497131,
job 122416049627). Missing private originals and optional inputs remain explicit
public-checkout skips. No native application was launched, no channel payload
was activated, and no actual Wii backup or test profile was changed by this batch.

## November 7: source-to-measurement projections and configured CMOC setup

Five scoped code/test commits after `a3fb7bb`, through `170cc56`, are pushed.
The previous goal turn was progress: it committed dated source acquisition and
native consumer proofs. This continuation rechecked the actual worktree before
extending those contracts. Existing unrelated Wii no Ma/provider/artwork work
remains untouched.

- The JMA association projection retains every published short-range temperature
  point and alternate weekly group, with independent forecast-field and
  observation-station presence. Historical metadata replay covers 58 offices,
  142 short rows, 92 weekly rows and 142 candidate lists; 37 lists have multiple
  alternatives. No first/nearest point or native city is selected. Explicit
  temperature projection retains raw values, unused slots, separate issue and
  target dates, group/point identities and all receipts. Real `17` evidence is
  distinguished from synthetic `05`/`11` and before-05 probes; unfamiliar target
  shapes reject under documented local restrictions.
- A separate measurement projection converts one explicitly selected observation
  using exact rational arithmetic before rounding each unit independently.
  Its JWC24 policy is nearest-half-away-from-zero, QC-0-only eligibility and
  explicit native-range rejection. Incomplete wind pairs become unavailable
  together, avoiding the verified calm/missing-speed invalid-read boundary.
  Source records, station, dates and receipts remain exact. Thirteen public
  tests include actual short-payload packing/validation using explicit synthetic
  identity/clock and missing sky condition; no active payload is written.
  A private replay of five actual October observations also preserved every
  source record/date/receipt; it is historical evidence, not a live refresh.
- Original resource membership is now verified from retained TMD/content through
  the unique compressed member and every padded TPL texture span. All 27 original
  textures were inspected privately. Unchanged selector code reaches 59
  definitions; 162 original integer-substitution cases connect sun textures to
  crescent/full-moon alternatives. No raster, raw definition records or original
  text enters Git. These are graphic membership/appearance facts, not complete
  floating-point/GX rendering or JMA condition equivalence.
- CMOC now has an independent configured-request setup projection compared with
  the complete original cached worker and outer SDK constructor. It preserves
  zero-size configured state separately from no configuration, bounded prefixes,
  receive capacity, decompressor predicate and attempted standard-header order.
  Resource/crypto initialization, lower SDK request creation, header acceptance,
  sockets and asynchronous lifetime remain explicit intercepted boundaries.
  Nineteen native cases include maximum accepted header lengths; the 63-byte
  application-version bound is a local accepted subset, not a recovered producer
  limit. Seven focused tests pass. Earlier root regression independently passed
  all 53 CMOC tests before the added header-boundary test.

The [source credit document](../channels/forecast/ATTRIBUTION.md) accompanies
the public JMA tools, with agency/source URLs and a JWC24 processing notice.
Official terms were rechecked on November 7. No original manual or screen is
rewritten. The original manual's historical provider credit and interrupting
message field do not establish an inline replacement-credit solution; the
actual service-distribution credit path still needs verification.

Next concrete evidence leads remain recorded privately: exact native-city to
published-area/station provenance, provider-code-to-original-graphic semantics,
source-kind-specific freshness and actual forecast shapes; CMOC's complete
event-2/event-4 body/finalizer lifecycle, where finalization can force flag
`0x20` if prefix comparison never completed. That flag must not be globally
renamed "changed data." Current input feeds, complete service/authentication
contracts and the full channel inventory's native/hardware gates remain open.

### Integrated run and shared-lock correction

The complete current local worktree at code checkpoint
`170cc56336623084a594695f1665562ba5444a53` ran **1,255 tests in 749.573 seconds**,
with **one error and one optional wheel-backend skip**. Its private UTF-8 log is
`private/swarm-ninth-full-20261107.log`. This is not recorded as a passing run.
As before, the worktree includes older uncommitted experiments.

The error was the existing concurrent Rakuten publication test: the shared
directory lock attempted to flush an initialization byte after another handle
had locked that byte. A deterministic actual-OS test reproduced the same
`PermissionError` before correction. Commit `776bc98` removes the unnecessary
initialization write. Windows permits locking past EOF; the file remains
persistent and existing nonempty files remain compatible. No unrelated
Rakuten or Wii no Ma changes were staged.

After the fix, **50 affected regressions passed in 97.699 seconds**, covering
the actual OS lock, Rakuten, artwork publication, News publication and HBNJ
publication. The four lock tests also passed a separate final 0.412-second run
with file-identity assertions. They cover held empty files, real child-process
exclusion, timeout, exception release and preservation of existing bytes.
The original full run was not repeated after this narrow correction; its
failed result and the subsequent affected-suite pass remain separate evidence.

Public GitHub CI for `170cc56` passed compilation, package installation and
**1,028 tests with 352 reported skips** in 27.751 seconds (run 42355571829,
job 128352812531). Shared-lock code commit
`776bc98aef8aa7c812cf93fde262d49b01604ee1` subsequently passed compilation,
package installation and **1,032 tests with 352 reported skips** in 30.879
seconds (run 42356729801, job 128356326001). Neither
public CI nor these native comparison harnesses establish full original UI or
hardware behavior. No emulator was launched, active weather/provider switched,
native payload installed, real account/order/vote submitted, or actual Wii backup
changed by this continuation.

## November 7 continuation: exact identities, source ages and callback finalization

Four scoped implementation commits extend the previous `f7b25c8` checkpoint:
`7bc4d06` checks selected JMA source ages, `b4d3295` models CMOC body/finalizer
callbacks, `681cdda` projects four reviewed JMA conditions and checks native text
consumption, and `6155f76` checks exact catalog/provider-area identities. The
preceding goal turn and this continuation are progress, not whole-goal completion.

- [Source age checks](../channels/forecast/jma_freshness.md) require explicit
  limits and explicit report/observation selection. Provider report issue,
  station observation and national observation times remain independent of
  metadata retrieval age. Exact expiry rejects; fetching historical data again
  cannot renew weather validity. The returned earliest deadline covers the
  checked inputs, not every dependency of an unbuilt native payload. Thirteen
  tests include unchanged historical-bundle acceptance at its old check clock
  and rejection at a November 7 clock. No source record is retimed.
- [Identity assessment](../channels/forecast/jma_identity.md) checks all 2,380
  reciprocal edges in the captured JMA hierarchy and pins the whole experimental
  catalog plus exact row. Real retained catalogs give Tokyo different numeric
  keys: `(1, 1, 1)` versus `(1, 2, 1)`. Existing catalog provenance remains
  third-party/unverified, not Nintendo origin. The representative Takasaki
  chain ends in a southern-Gunma forecast whose published temperature point is
  Maebashi. No native-city identity or city measurement claim is inferred from
  this relationship. Assessment remains pending for publication.
- [Condition projection](../channels/forecast/jma_conditions.md) maps the actual
  JMA canonical labels for codes 100/200/300/400 to the independently inspected
  original sun/cloud/umbrella/snowman selectors. This is an explicit JWC24
  replacement policy, not a recovered original provider dictionary. The other
  114 known codes report unsupported status. Source issue/target dates and
  detailed qualified forecast sentences remain separate from canonical labels.
  Historical replay has 12 mapped and 21 unsupported slots. Fourteen original
  lookup/pointer handoffs, 28 UTF-16 length checks and 38 control-branch cases
  pass; full fonts, fitting, glyph rendering and composite semantics remain open.
- [CMOC callbacks](../channels/cmoc/callback_lifecycle.md) preserve event-2 body
  and event-4 finalization accumulation, prefix comparisons/latches and flags.
  The original finalizer can set `0x20` without a completed prefix comparison,
  so the bit is not globally interpreted as changed data. Native comparisons
  cover 840 lifecycles and 1,652 dispatcher calls, with actual guarded prefix
  comparisons. Configured cipher/decompressor/hash boundaries remain explicitly
  intercepted, not cryptographic or authentication proofs. The real combined
  header/capacity invariant and SDK transport remain unfinished.

After all four components were frozen and reviewed, the combined Forecast/JMA
and CMOC regression selection passed **245 tests in 74.803 seconds**, with no
reported skips. This includes available private-source/native comparison tests.
It is a targeted pass, not a replacement for the earlier failed 1,255-test full
run and subsequent 50-test shared-lock regression pass. Those results remain
recorded above. Public CI may skip private-input tests; that skip count must be
reported separately.

No new network weather capture, source activation, native payload publication,
Dolphin launch, profile/credential modification or actual Wii backup access
occurred in this batch. Unrelated existing Wii no Ma/provider/artwork worktree
changes remain unstaged. All channel/data/authentication/native UI and physical
hardware gates in the [inventory](../channels/README.md) remain in scope.

## November 7 continuation: receive geometry, actual hash semantics and real morning reports

Five scoped implementation commits after `3aa82a6` are pushed through
`2a9db55`: `4ff651a` receive geometry, `f3e3a15` the original manual's additional
condition mapping, `659b047` actual HMAC/string-check execution, `bbed8e2` raw
source-URL validation and `2a9db55` genuine VPFD51 XML temperature records.
This is further progress toward the full inventory, not channel completion.

- [Receive geometry](../channels/cmoc/receive_geometry.md) executes the original
  wire/intermediate storage resets and capacity/rounding fragments. The wire
  storage has `0x440` bytes; a configured offset plus `0x400` capacity must fit
  that storage. All 4,225 locally supported span/prefix combinations are checked:
  2,145 fit, 2,080 exceed it. Actual resource sizes are not inferred from these
  synthetic combinations. The new composition gate rejects excess capacity and
  missing rounded backing without changing the original setup projection or
  inventing padding. Five focused tests passed in 7.436 seconds.
- [Original HMAC execution](../channels/cmoc/hash_processing.md) matches all
  seven RFC 2202 HMAC-SHA1 vectors under three chunk arrangements and additional
  binary/block-boundary cases. The application resolves `+0xC8` from supplied
  or C-string key length, not the fixed twenty-byte digest size. Its final check
  uses a bounded **string comparison**: an equal NUL can end comparison before
  later mismatching bytes. Original guarded overlong cases attempt a twenty-first
  digest read. Independent results distinguish native acceptance from full-span
  binary equality; neither establishes service authentication. Nine tests passed
  in 14.379 seconds, covering 98 SDK, 90 wrapper and three guarded-overread cases.
- [Original manual/component evidence](../channels/forecast/condition_semantics.md)
  supports JMA 101, sunny with intermittent cloud, using native selector 2.
  The retained original manual image was privately inspected and independently
  reviewed; its TMD/archive membership is checked. Actual original floating-point
  component calculations preserve sun/cloud placement in 84 cases, and 150
  selected caller suffixes preserve secondary/high-bit values. Full paired-single
  prologs, composition loops, GX and night/arrow meanings remain unverified.
  Policy v2 supports five source categories and explicitly leaves 113 unsupported;
  the historical 33-slot replay now has 13 supported and 20 unsupported slots.
  Nineteen focused tests passed in 5.336 seconds; prior v1 evidence is retained.
- [Real VPFD51 source records](../channels/forecast/jma_xml_temperatures.md)
  preserve genuine November 7 05:00/11:00 report announcements, separate earlier
  transmission times, four exact temperature points and reference-ID-bound
  nonmonotonic target periods. A general maximum remains distinct from morning
  minimum. The oversized long feed was rejected under its two-MiB audit bound;
  complete prefix entries were discovery leads only. Both actual document GETs
  completed independently within bounds. This XML evidence does not establish
  the separate website JSON array layout or a before-05 report-time sample.
  Eighteen focused tests passed; the final related 80-test selection also passed.
- Independent XML review found raw URL controls silently removed by `urlsplit`.
  Both exact-route contracts now reject raw ASCII whitespace/controls and DEL
  before parsing. The existing JSON source/capture selection passed 36 tests in
  0.135 seconds after the correction. A numeric XML token/type annotation still
  does not prove unit, qualifier or native conversion eligibility.

Public GitHub CI for full code checkpoint
`2a9db55b176e0c40d5762a72b85772d1a7a6fc4c` passed compilation, package installation
and **1,118 tests with 361 reported skips** in 30.559 seconds (run 42370748111,
job 128398171222). Missing private originals remain public-checkout skips, not
native completion evidence.

The first full-worktree attempt at this checkpoint wrote
`private/swarm-tenth-full-20261107.log` but has no final result. Its tool handle
became unknown and no matching unittest process remained. It is not counted as
a passing or completed run. The subsequent named-test run uses
`private/swarm-eleventh-full-20261107.log`; these logs remain private.

The named full-worktree run subsequently completed successfully: **1,355 tests
in 370.973 seconds, with one reported skip**. All code/tests remained frozen at
`2a9db55` during that run. It includes the available private original-code/source
comparisons and older uncommitted experiments. Their passing tests do not make
the unrelated changes reviewed, committed or native-complete. The prior failed
1,255-test result and its separate lock fix remain historical evidence; this is
a new complete passing checkpoint, rather than a rewrite of that old result.
The sole skip was the installed-wheel test's unavailable optional local
setuptools build backend; no native-original/source comparison skip was reported.

While public code/tests stayed frozen for the integrated run, bounded private
research established concrete next steps: actual AES-CBC vectors through the
original CMOC core, Nintendo's manager-to-loader callback relay, and Global
Voices Japanese full-text/source-attribution records. These are next-work leads,
not new public adapters or completed service flows. The News source is a
supplemental Japanese international-feature candidate with actual older article
dates; third-party media/quotation handling and native credits/links remain
unresolved. No hourly coverage or full genre coverage is inferred from its feed.

No original asset, proprietary source, credential, article corpus or NAND data
was committed. No emulator was launched, actual Wii backup accessed, profile
modified, provider activated or native payload installed. Unrelated existing
worktree changes remain untouched. Full data/authentication/rendering/hardware
requirements across every channel remain in scope.


## November 7 continuation: original cipher, manager relay and complete source records

Five scoped implementation commits follow the preceding full-suite checkpoint:
`1eda2e0` optional crypto dependency/CI installation, `259fe5a` XML extrema
projection, `eb82bc8` CMOC cipher, `53d108f` Nintendo manager callback and
`7157caa` Global Voices Japanese supplemental source adapter.

- [CMOC cipher](../channels/cmoc/cipher.md): 69 actual-original comparison
  cases (18 SDK and 51 application) verify AES-CBC for 128/192/256-bit keys,
  chaining, in-place/separate output and application acquisition/error behavior.
  A requested return length can coexist with no output write; these facts remain
  separate. Sixteen focused tests passed. The optional crypto dependency is
  declared rather than supplied by copied original AES code. Callback integration,
  genuine resource envelopes/keys, compression and authentication remain open.
- [Nintendo manager relay](../channels/nintendo/manager_callback.md): 311 complete
  actual-original comparisons include callback thunk/relay, error and response
  precedence, loader callback/body and native memcpy. Twelve focused tests and
  the 82-test Nintendo selection passed. SDK state/request production and genuine
  catalog/authentication/media remain unfinished; synthetic compressed ListData
  verifies a handoff, not an original downloaded catalog.
- [XML extrema projection](../channels/forecast/jma_xml_projection.md): ten tests
  pass with actual 05:00/11:00 captures. Each report supplies twelve eligible
  extrema and four separately retained general maxima. Original decimal values,
  units, qualifiers, complete headers and date/reference bindings remain attached.
  A general maximum cannot supply an absent daily low. Source eligibility, native
  city identity and complete accepted payload assembly remain separate gates.
- [Global Voices source adapter](../channels/news/globalvoices_source.md): nineteen
  tests pass, including the complete privately retained feed/article/policy replay.
  Complete inert article structure, distinct author/translator/proofreading credits,
  original publication/modification/translation dates and source receipts remain
  separate. Independent review fixed discarded processing instructions and omitted
  policy-receipt date checks. This is supplemental international-feature coverage,
  not a full current/hourly provider. Third-party screenshot/video/quotation review,
  original native attribution and article rendering remain pending. No News payload
  can be published by this adapter.

The combined 48-module regression at frozen code checkpoint `7157caa` passed
**492 tests in 148.841 seconds with no skips, failures or errors**. Its UTF-8
log remains private at `private/swarm-focused-20261107b.log`; session 69316
completed with exit zero. This is a new affected-channel selection, not another
full-suite run. The preceding complete 1,355-test run at `2a9db55` and public
CI at `c0838e6` remain distinct historical checkpoints.

The owner has no Weathernews credential/permission file and authorized choosing
the best alternative. Continue the public JMA track; no Weathernews authorization
or invented issue/observation timestamps are assumed. No source activation,
native publication/install, emulator launch, profile/credential change or actual
Wii backup access occurred. Unrelated worktree changes remain untouched and the
full project inventory remains unfinished.
