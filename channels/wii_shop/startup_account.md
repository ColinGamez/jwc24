# Retail startup and the first IAS account boundary

October 26, 2026. The real retail initialization caller and a subsequent IAS
operation are now identified. This does **not** establish complete startup,
registration, account connection or acquisition.

The [static startup report](../../research/wii_shop_startup_account_20261026.json)
checks thirteen direct call targets against the original v21 executable and
nine inventory-verified private source files. It exports names, addresses and
hashes, without original instructions, argument values or encryption parameters.

| Retail boundary | Evidence |
| --- | --- |
| Application initialization | `0x8002735C` calls `EC_Init` at `0x80088FD0` with eleven name/value arguments copied from `0x802CEA60` |
| EC platform setup | `EC_Init` calls `0x8008A3C0`; successful setup is followed by environment initialization at `0x80074010` |
| JavaScript plugin installation | Platform setup calls `0x80099F60` at `0x8008A700`; the plugin capability stores global getter `0x80091300` and origin callback `0x80091150` |
| Connection worker | Vtable `0x80322188` selects run entry `0x80088920`, containing the previously verified GetECConfig path |
| First IAS challenge | That worker calls `GetChallenge` at `0x80087A50` from `0x80088E48`, followed by registration-sync routine `0x80088620` |

The startup table includes allocator/free callbacks, logging level, Bluetooth
address, device code, plugin/current-URL callbacks and four credit-card encryption
parameter descriptors. Parameter values and encryption material remain private.
This later retail table has more fields than the older platform-init reference;
the old argument extractor must not be treated as the complete v21 startup API.
The earlier socket/HTTP setup wrappers are separate boundaries.

The older `ECInterfaceData` constructor accepts zero arguments and does not call
`EC_Connect`. Captured `oss.js` constructs `ECommerceInterface`, but construction
alone does not authorize an account. The exact retail public connection caller,
worker scheduling, runtime initialization order and browser argument flow remain
unverified. Static call evidence above does not execute those stages together.

## Independent offline GetChallenge component

`jwc24.wii_shop_ias_challenge` adds a strict IAS request parser and an explicit
response-fixture serializer. It has no listener, network operation, nonce
generator, signature verifier, credential lookup, registration handler or
connected-account state. Every response status and challenge requires a supplied
evidence reference. Those references are caller assertions, not authentication.
Identity, postal and challenge fields are excluded from representations and errors.

The [native IAS report](../../research/wii_shop_ias_challenge_native_20261026.json)
executes original operation `0x80087A50`, its SOAP constructor/start/end, response
wrapper/common reader and challenge extraction. Only transport, allocation/free,
logging, time and lock boundaries use synthetic stubs. The intercepted transport
receives caller-supplied synthetic response bytes; no HTTP request is sent.

Verified request differences matter:

- The action is `urn:ias.wsapi.broadon.com/GetChallenge`, with Version `2.0`.
- Common fields are Version, MessageId, optional DeviceId/DeviceToken/AccountId,
  Region, Country and Language. The optional PostalCode Name/Value attribute
  also appears when the synthetic environment supplies it.
- ECS SerialNo/ECVersion, CAS Age, ApplicationId and TIN are absent from this
  request even when their environment fields are populated. The IAS parser
  rejects them instead of borrowing another service's request schema.
- The native default token selection uses the weak-prefixed environment value
  when the raw-token trigger is populated. This does not verify any token.
- Common native fields use raw stream insertion. Malformed XML containing a raw
  ampersand is rejected by the independent parser, without rewriting identity.

Verified response behavior:

- The challenge capacity is **eleven bytes**; twelve bytes clear the value and
  return `-4034`. Three three-byte UTF-8 characters pass; four fail. This is not
  an eleven-character limit.
- Empty challenge text is accepted by this reader. Missing Challenge clears the
  old value and returns `-4006`. Neither case establishes acceptable signing or
  registration behavior.
- Nonzero error status stops challenge extraction; transport failure skips the
  common parser. Both retain a prior synthetic challenge in the tested paths.
- Literal ErrorCode `0` with informational ErrorMessage continues. Noncanonical
  `00` is an error. The older message-as-failure source rule is not applied here.
- Challenge is copied as raw element text: `A&amp;B` remains those seven bytes.
  The serializer's explicit local policy rejects `&`, `<` and `>` in supplied
  challenges instead of changing their meaning through XML escaping.
- The common reader's previously observed namespace-mismatch quirk is present:
  wrong response namespace can still return zero and extract a challenge. The
  serializer always emits the exact IAS namespace; zero native status alone is
  not evidence of namespace validation, authentication or connection.

XML byte, text, element, namespace, depth and output limits in the independent
codec are local defensive policies. The eleven-byte challenge capacity is the
separately matched retail behavior. The harness pins the executable, bounds
instructions and memory writes, and checks synthetic object/stack/heap guards.
Its returned wire/value fields echo synthetic inputs and are not a redacted API
for real account captures.

## Minimum chain and remaining work

The older connection worker establishes the useful order: EULA prerequisite,
GetECConfig discovery, conditional device/account-status work, GetChallenge,
signed registration synchronization, persisted configuration and further device
status before assigning connected state. The selected retail GetECConfig and
GetChallenge calls now corroborate portions of that sequence. The intervening
retail branches and asynchronous caller still need matching execution evidence.

The source registration-sync path signs challenge-related data and carries
DeviceCert, Signature, CertChain and Challenge. A catalog listing or a challenge
response cannot replace that proof. Account state, certificate-chain validation,
challenge/device binding, registration persistence and entitlement/ticket checks
remain unfinished. No success response for those operations is implemented.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_ias_challenge tests.test_wii_shop_get_challenge_native
.venv/Scripts/python.exe -m tools.audit_wii_shop_startup_account --main '<private original v21 main>' --source-root '<inventory-backed private Shop source root>'
```

Twenty codec/native tests pass with private original software available. Native
tests skip when that executable is absent. No Dolphin, profile, NAND, device
credentials, endpoint configuration or preview route changed.
