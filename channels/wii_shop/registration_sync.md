# Retail IAS registration synchronization

October 26, 2026. The original v21 connection worker's registration-sync call
now runs offline through its complete request, response and state consumer.
This closes a protocol gap after [GetChallenge](startup_account.md), without
claiming authenticated registration or enabling a service route. The existing
original browser, assets and preview are unchanged.

The [native report](../../research/wii_shop_registration_sync_native_20261026.json)
pins the original main executable and verifies six recovered private files
against their extraction inventory. Inventory consistency is not independent
provenance of the enclosing archive. Original software, source bodies,
disassembly and all actual device material remain private and outside Git.

| Original retail boundary | Executed role |
| --- | --- |
| `0x80088E58` through call `0x80088E6C` | Worker supplies its challenge and invokes registration sync |
| `0x80088620` | Clears operation response state, sets sync operation, copies challenge and dispatches run |
| `0x80321BA0` | Original registration run vtable |
| `0x80087500` | Complete run, account-field assignment, sync-state and side-effect decisions |
| `0x80087CF0` | Signing-data construction, IAS request and response dispatch |
| `0x80088480` | Complete account/token/expiry/country/optional-field response extraction |
| `0x80074D40` → `0x800749C0` → `0x800844A0` | ECString token-setter wrapper → internal C-string setter → MD5 helper |

The harness stops when the sync call returns to the connection worker. It does
not execute subsequent account checks, CheckDeviceStatus, persistence recovery,
connected-state assignment or the complete asynchronous/browser startup flow.

## Explicit standalone component

`jwc24.wii_shop_registration` implements four offline operations:

- `parse_registration_sync_request`: strict structural parsing of the reviewed
  IAS `SyncRegistration` and `GetRegistrationInfo` request shapes.
- `registration_sync_signing_bytes`: reconstructs the exact native sync signing
  message from parsed proof fields, without signing or verifying it.
- `serialize_registration_sync_response`: serializes explicit evidenced account
  facts or an explicit service error; it generates no identity or token.
- `plan_ecdk_registration_sync`: returns the state and save request for a
  complete response in the connection worker's ECDK-sync mode. It performs no
  config write or other side effect.

The action namespace is `urn:ias.wsapi.broadon.com`, Version 2.0. In addition
to IAS common fields and optional PostalCode, each request contains DeviceCert,
Signature, CertChain and Challenge. These are opaque values, not authenticated
proof. Common fields exclude ECS SerialNo/ECVersion and CAS ApplicationId/TIN/Age.
Register, Transfer and Unregister have different signing inputs and behavior;
they are deliberately outside this component's accepted operations.

The signed request uses the environment's strong-prefixed DeviceToken when the
tested token trigger is set. This differs from the weak-prefixed selection
previously observed for GetChallenge. Neither token spelling validates identity.
Request/account/proof values are excluded from representations and errors.

Zero-status fixtures require explicit account ID, token, country, optional
expiry/extended-account/device-code facts, and a source reference. Nonzero status
forbids account facts. Status and its evidence reference have no defaults.
References are caller assertions, not independent provenance, authorization or
permission checks. Empty required account/country strings are retained when
explicitly supplied; missing required elements are a different native path.
Omitted optional fields remain distinguishable on the wire and become empty
fields in the freshly cleared native response object.

The serializer rejects XML metacharacters in opaque response account/token
facts because the original response reader copies raw element text. Escaping
those facts would silently change them. Its typed booleans emit lowercase
`true`/`false`; the native reader also accepts literal `1`/`0`, but rejects tested
uppercase/mixed-case or empty boolean text. XML byte/depth/text limits and the
serializer's canonical policy are local safeguards, not native capacity claims.

## Exact signing bytes differ from SOAP serialization

For both reviewed sync operation names, the original signing boundary receives
literal UTF-8 concatenation of `<Challenge>`, the challenge value, and
`</Challenge>`. It does not include SerialNumber, country, MACs, or additional
registration fields used by other operations.

The original SOAP builder **separately escapes proof element text**. With the
synthetic challenge `a&b`, the signed message contains `a&b`, while the SOAP
Challenge element contains `a&amp;b`. Re-serializing an XML tree as the signing
message would change these bytes. The native regression compares the independent
reconstructor directly with the intercepted original signing input.

The harness supplies explicit synthetic signature/certificate-chain outputs at
the signing boundary. No device signer or signature check executes. Recovering
this exact message contract does not establish certificate trust, challenge
freshness, device binding, replay protection or server-side authentication.
Empty challenge exits the original run before signing with `-4004`.

## Complete native response and state behavior

The original response reader requires AccountId, DeviceToken and Country.
DeviceTokenExpired, ExtAccountId and DeviceCode are optional. The original run
assigns the complete response fields only after extraction succeeds, then uses
the real token setter: `ST-` plus the supplied token and `WT-` plus lowercase
MD5 of the token's exact UTF-8 bytes. Empty token clears both derived values.
The assignment calls wrapper `0x80074D40`; that wrapper extracts the string and
calls internal setter `0x800749C0`, which invokes MD5 helper `0x800844A0`.
Non-ASCII tokens are independently matched against the original MD5 path.
These historical derivations are not cryptographic authentication.

The actual connection worker sets `useECDKSyncRegistration` before this call.
In that mode, a complete response requests a config save and preserves existing
ticket-sync flags/times. The pure planner mirrors that bounded state contract.
It preserves every supplied local field on an ordinary reported service error.

Important separate outcomes are verified:

- Explicit wire error `901` is mapped to an **unregistered** result. The original
  run clears account/token/country/optional fields and all four sync times, sets
  ticket sync needed, preserves import-all, and requests a config save. Its zero
  return here is not an authenticated or connected account.
- A complete response with an expired-token flag assigns fields and requests a
  save, then returns `-4042`, meaning registration is needed.
- Missing Country returns `-4006` without assigning environment account fields.
  If the earlier expiry field was true, the final return becomes `-4042` instead.
  Partially extracted response fields do not imply completed account assignment.
- Reported error and transport/signing failures do not assign the tested local
  state. An out-of-range signing error is mapped to `-4001` by native code.
- The run ignores a failed config-save return in the tested complete-response
  path. Zero native status cannot establish that state was durably saved.

The other original mode chooses `GetRegistrationInfo`. It can mark import-all
when account identity changes, create a shop log, or request title removal after
an unregistered response. These native decisions are tested with explicit
side-effect stubs. **No titles are removed.** That mode's cleanup/persistence
state machine is outside the pure planner rather than replaced with assumed
cleanup success. The tested failed removal stub also does not change the run's
zero return, so that return cannot establish cleanup completion.

## Validation and remaining integration

Twenty-three focused tests exercise exact signing bytes, both operation names,
strong-token selection, full state comparisons, Unicode token hashing, explicit
empty versus omitted fields, unregistered/expiry/partial/error paths, ignored
save failure, privacy, namespace isolation and bounded synthetic inputs.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_registration tests.test_wii_shop_registration_native
```

Original XML helpers, state assignment, token setter and MD5 execute unchanged.
Only signing, transport, allocation/free, logging, time, locks, config save,
title removal and shop-log boundaries are stubbed. The harness pins source,
bounds instructions/writes and checks object, stack and allocation guards.
Native tests skip when the private executable is unavailable. Returned wire
fields echo synthetic fixtures and are not a safe logging API for real accounts.

Before a runtime route can use this component, establish authorized certificate
trust and signature verification, challenge/device/session binding, registration
authority and persistence semantics. Then integrate the enclosing original
connection/browser flow and its error recovery. No credentials, actual Wii
backup, private profile, installation, purchase or live account was accessed.
