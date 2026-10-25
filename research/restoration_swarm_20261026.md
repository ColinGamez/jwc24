# Project-wide restoration checkpoint, October 26, 2026

The owner requested the full Japanese service baseline and one coordinated
native validation pass. Four concurrent worker slots (coordinator plus three
workers) covered shared WC24, News/Nintendo/CMOC, experience channels and Shop.
This checkpoint records completed scoped work, not a finished restoration.

## Implemented and verified

- Shared delivery now selects a distinct private envelope-key path for each
  payload's owning title. Synthetic HTTP decryption tests cover two channel
  owners, compressed payloads, assets, filename aliases and unencrypted data.
- Read-only multi-channel preflight checks local inputs, cross-manifest
  conflicts and optional task/account/key-file prerequisites. The shared
  origin override changes only in-memory manifests. Native readiness and
  project completion are always explicitly unverified.
- Forecast bundle validation joins current records to catalog/condition keys,
  checks locale/window consistency, and optionally verifies both signatures
  against an explicitly supplied JWC24 key. Observation age is not inferred
  from envelope validity. The retained pair verifies historically but fails
  the current-window requirement.
- CMOC's bounded independent inspector now supports both native size encodings
  and a separate header-correlation predicate. Six original retail routines
  execute against synthetic inputs without service stubs. Deliberate local
  safeguards reject malformed extended prefixes that trigger unchecked native
  reads. This does not implement authenticated startup or Mii/contest semantics.
- Shop server assembly and offline preflight share the same pack loader.
  The current snapshot rendered 2,605 HTML routes and attempted 3,374 static
  display dependencies. All HTML routes passed, but two local font routes
  and four external third-party style references keep the overall check
  failing. No external dependency was fetched or original asset invented.

## Validation scope

The initial full local worktree suite passed 696 tests. The final full local
worktree suite passed **745 tests**, with no reported skips, after code review
and fixes. These totals include existing uncommitted experiments; they do
not imply that unrelated work was committed or independently restored.

Newly staged code was also exported separately from the older dirty worktree.
The shared-preflight/delivery tests passed 16 tests, Forecast passed 14,
CMOC passed 16, and Shop preflight/server passed 15. For CMOC native checks
the separately exported test suite was explicitly pointed at the existing
private original executable; no original bytes entered the index or commit.
The first export run without that private input correctly skipped native
CMOC tests. These scoped counts overlap the 745 total and must not be added.

Independent cross-review caught incomplete task-flag validation, unsafe
manifest labels in metadata, ignored quoted CSS imports and the need to state
the observation-age limitation. Fixes or explicit scope flags were checked
before committing. Documentation links in the staged cross-channel inventory
were checked against indexed files, rather than relying on unrelated local
documents.

## Open work and next investigation order

The [complete channel inventory](../channels/README.md) controls scope. News
still lacks a verified registration/container/article contract. Nintendo
Channel still lacks the CSData load/validation/record contract. CMOC still
lacks its first-response semantics and authentication. These are implementation
gates, not requests for the owner to test incomplete success responses.

Next recover the News data-consumption and Nintendo CSData paths from the
actual clients, keeping any independently published protocol observations
separate from Nintendo provenance. Continue Shop's original startup/account
and Japanese screen recovery. Demae verified variants/orderability, Wii no Ma
original-compatible Flash/media, Body Check's legitimate save and dataset
requirements, and the additional verified stock channels remain open as
documented. Private originals are evidence inputs, never executable tools to
run blindly or material to publish.

No Dolphin launch, live account/order/submission, profile/DNS change or device
installation occurred. The real Wii backup and credentials remained untouched.
The region-changed physical console is a separate future validation target;
the authorized isolated Dolphin/vWii profile remains the development hub.
