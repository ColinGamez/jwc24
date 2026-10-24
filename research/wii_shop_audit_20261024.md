# Wii Shop source audit — October 24, 2026

## Result and scope

The Nintendo collection contains substantial commerce **client-library** evidence.
This audit verified 21 selected recovered files (350,890 bytes) against their
existing local extraction inventory. It did not recover or verify a complete
Shop backend, storefront package or retail executable match.

The files remain under the private Nintendo research tree at
`workbench/wii/channel-hunt/packed-resources/shop-build-lead/`. The inventory
records their member paths beneath
`ios_releases/ios_release_090406170009/build/gba/sw/`. Matching these recorded
hashes confirms consistency with that extraction inventory; the enclosing
original archive was not independently re-extracted for this audit.

The [metadata report](wii_shop_source_audit_20261024.json) includes relative
paths, sizes, SHA-256 values, literal operation leads and build references.
It contains no recovered source bodies, credentials, account files or tickets.
`tools/audit_wii_shop_sources.py` reproduces it from the supplied private root.
Four focused tests check metadata-only output, source drift, missing/duplicate
provenance and path containment. No recovered program was compiled or executed.

## Evidence map

| Recovered file under `common/lib/ec/` | Evidence reviewed | Limit |
| --- | --- | --- |
| `ec_connect.cpp` | Service discovery, EULA prerequisite, account/device-status branches and registration synchronization | Library control flow, not a captured retail startup |
| `ec_register.cpp`, `ec_checkReg.cpp` | Challenge, registration operation selection and registration-status API | Identity/authentication implementation is not reproduced |
| `ec_chkDevStat.cpp` | Device-status operation and ticket-sync/account state handling | No live account was queried |
| `ec_soap.cpp`, `ec_soap.h` | SOAP action construction, service identifiers and response parsing | Literal-call extraction is not a full schema audit |
| `ec_js.cpp` | Opera plugin objects, native commerce bridge, origin/protocol checks | No storefront page or retail bridge compatibility test |
| Title-list/content/purchase modules | Catalog, title acquisition, ticket synchronization and commerce operations exist in the library | Presence does not prove an operational compatible backend |
| `devroot/tools/bw/wiishopping.mk` | Separate Shop/Opera package and installation dependencies | Referenced packages are not verified present |

The report detects ten literal SOAP call sites and two dynamic-action sites.
It deliberately does not infer every possible action from filenames or treat
the absence of a literal call as absence of an operation. Several operations
are selected dynamically or implemented through other classes.

## Recovered connection flow

The reviewed `ECConnect::run` first checks EULA agreement, then discovers
service configuration through ECS `GetECConfig`. The request includes an
`ECVersion` field. The response reader obtains these five fields:

| Field | Client use |
| --- | --- |
| `ContentPrefixURL` | Cached content prefix |
| `UncachedContentPrefixURL` | Uncached content prefix |
| `EcsURL` | ECS service URL |
| `IasURL` | IAS service URL |
| `CasURL` | CAS service URL |

The client installs those URLs into its environment. If an account exists,
it checks device status. An absent account or qualifying status failure leads
to challenge/registration synchronization, configuration persistence where
needed, a nonempty-account check and another device-status check. Receive
failures and cancellation have distinct early exits. A successful path marks
the connection ready. This is a branch-sensitive library flow, not a claim that
every startup sends every listed operation.

The registration code contains dynamic operation selection including
`SyncRegistration` and `GetRegistrationInfo`; the connection path enables its
ECDK synchronization option. Following that dependency is still required before
implementing registration. `CheckRegistration` is a separate API in the reviewed
sources, not a mandatory step established by the connect function alone.

## Browser and service boundary

The JavaScript plugin registers 16 global names, including
`ECommerceInterface`, progress, title/ticket collections and payment objects.
The reviewed code checks origin access and tracks HTTPS/trusted-page state;
many native methods use protocol/test-mode guards. Serving arbitrary HTML is
therefore insufficient to establish that native commerce calls will work.
The development test-mode branch is not evidence of retail behavior.

SOAP requests use IAS/ECS/CAS service identifiers and service/action-specific
`SOAPAction` values. These direct commerce operations are a separate protocol
surface from JWC24's WC24 task/mail adapters. Shared logging, configuration and
test utilities may be reusable; the existing transport does not substitute for
commerce account, catalog or title-acquisition services.

## Build-package leads

The reviewed makefile refers to:

- `wstrunk1316_repack.zip`: Shop package installed into a separate SDK tree.
- `RevoEX-2_2-080806_1338_opera_build-2077-1.zip`: Opera update dependency.
- `lndir_1.0.1-ead_patch.zip`: build/tooling dependency.

Correction from October 25: the index's `wstrunk1300_notes.conf` hit is under
`vcs-history/control/seed/` and explicitly marked synthetic. It is a scanner
fixture, not a genuine package/version lead. The real base-package reference
remains the verified installer above. This is a snapshot/index result, not proof that all archives
have been exhaustively searched. The build-script references must not be
reported as recovered storefront assets. No installer or make target was run.

## Restoration sequence

1. **Identify the retail target.** Record the actual Shop title/version and
   executable/content fingerprints from an available Japanese-system setup;
   compare its bridge and service calls against this library revision.
2. **Recover the entry flow.** Locate original storefront assets or capture
   startup requests in an isolated Dolphin profile, with account/device values
   redacted. Resolve page origins, TLS expectations and native bridge behavior.
3. **Prove read-only startup and browsing.** Implement only response contracts
   supported by the matched client. First milestone: original entry UI and
   catalog navigation against a controlled local service, with no simulated
   success for unsupported account or purchase operations.
4. **Validate acquisition separately.** Establish entitlement, ticket/TMD,
   content integrity and installation behavior with suitable test content.
   Catalog availability does not establish permission or technical ability to
   install an arbitrary title through the unmodified channel. No original
   signing material or purchase authority is established by these sources.

The first implementation boundary is a separate Shop adapter with explicit
read-only capabilities. No Shop route, TLS interception, account mutation,
purchase, download or NAND installation was added during this audit.

## Installed-client follow-up

The subsequent [installed-client audit](wii_shop_client_audit_20261024.md)
identifies Shop version 21 and verifies all 18 installed contents against its
TMD. Main executable markers overlap this library, and bundled support pages
and static startup/service URL candidates are recorded. This supplies a
concrete comparison target; exact source matching and runtime startup behavior
are still open. Original content and account data are not included in reports.
