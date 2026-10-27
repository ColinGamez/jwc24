# Explicit pinned-device proof inspection

October 27, 2026. `jwc24.wii_shop_proof` adds an offline mathematical check
behind the recovered [registration sync contract](registration_sync.md).
It verifies the supplied application certificate and exact challenge-message
signature against an explicitly pinned device certificate. It generates no
device identity, signature, registration, account, entitlement or service route.
The original channel assets and existing browsing experiment are unchanged.

## Three separate evidence boundaries

The [metadata report](../../research/wii_shop_device_proof_validation_20261027.json)
distinguishes these inputs:

1. Seven recovered Shop client source files match their existing extraction
   inventory. The original v21 retail executable remains pinned by SHA-256
   `aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898`.
   Its actual signer wrappers, copies, strings and Base64 encoder execute in the
   bounded harness; the ES signing boundary supplies synthetic fixture bytes.
2. Four selected original SDK headers were streamed from the retained archive
   into a new private evidence directory. Exact member names, byte counts and
   hashes are recorded. This did not extract the whole archive, authenticate its
   origin, compile recovered source or inspect a real device/profile. Original
   headers and source bodies remain outside Git.
3. The public Dolphin implementation provides separate crypto and certificate
   generation corroboration, pinned to commit
   `3eb30c7620b4475b2e0404228ba0d2b238a132f1`. Its
   [IOSC implementation](https://github.com/dolphin-emu/dolphin/blob/3eb30c7620b4475b2e0404228ba0d2b238a132f1/Source/Core/Core/IOS/IOSC.cpp)
   signs the application certificate body and message SHA-1 digests. This is
   emulator implementation evidence, not execution of Nintendo IOS cryptography.

The original headers confirm the ECC certificate structure and a 384-byte
device-certificate type. The retail signer copies a 60-byte raw signature and
384-byte signer certificate, then independently Base64-encodes both. Public
[Dolphin certificate types](https://github.com/dolphin-emu/dolphin/blob/3eb30c7620b4475b2e0404228ba0d2b238a132f1/Source/Core/Core/IOS/IOSC.h)
corroborate the same layout. The scalar and coordinate encoding is corroborated
by its [ECC arithmetic](https://github.com/dolphin-emu/dolphin/blob/3eb30c7620b4475b2e0404228ba0d2b238a132f1/Source/Core/Common/Crypto/ec.cpp)
and [big-integer operations](https://github.com/dolphin-emu/dolphin/blob/3eb30c7620b4475b2e0404228ba0d2b238a132f1/Source/Core/Common/Crypto/bn.cpp):
30-byte big-endian `r`, then `s`; public keys are 30-byte `x`, then `y`.
The binary-curve parameters match local OpenSSL's `sect233r1`.

| ECC certificate field | Offset / size |
| --- | --- |
| Signature type | `0x00`, four bytes, reviewed value `0x00010002` |
| Raw signature | `0x04`, 60 bytes |
| Issuer | `0x80`, 64 bytes |
| Public-key type | `0xC0`, four bytes, reviewed value 2 |
| Subject name | `0xC4`, 64 bytes |
| Opaque word | `0x104`, four bytes |
| Public `x || y` | `0x108`, 60 bytes |
| End | `0x180` |

The original SDK calls the word at `0x104` a date; Dolphin calls it an ID.
The parser preserves its bytes without assigning either meaning. The SDK's
comments also contain an older `NC` naming example. This component supports the
`NG` device / `AP` application naming profile corroborated by public Dolphin;
it does not claim that an actual owned device's generated subjects were observed.

## Explicit caller context and checks

`inspect_registration_sync_proof()` accepts raw SOAP bytes, SOAPAction and a
`PinnedDeviceContext`. No profile or key lookup has a default. The context
requires an explicit SHA-256 pin of the whole device certificate, full 64-bit
request DeviceId, low 32-bit NG identifier, title identifier, challenge,
operation and evidence reference. The reference is a caller assertion and is
excluded from representation/output.

The original client builds DeviceId from a device-type high word and the ES
identifier low word. The function therefore checks the explicit full request
value and low-word context separately; it does not assume a device-type value.
It verifies these stages in order:

- The existing strict registration parser, expected operation/challenge/device
  values and exact pinned device-certificate digest.
- Exact 60/384-byte canonical Base64 shapes and reviewed certificate types;
  bounded ASCII identity labels, NG identifier, AP title identifier and exact
  application-to-device issuer relation.
- Application-certificate ECDSA/SHA-1 signature under the pinned device key,
  covering the unchanged bytes from `0x80` to the certificate end.
- Message ECDSA/SHA-1 signature under that application's key, covering the exact
  UTF-8 `<Challenge>` concatenation already recovered from the original client.

OpenSSL validates the binary-curve public points and verifies both signatures.
Raw scalar bounds are checked before DER conversion. The verifier uses bounded
temporary public-key/signature files and fixed subprocess timeouts. Errors do
not return input values, key material or external-tool stderr. It uses no
network or persistent device/account store.

The supported local challenge subset is nonempty UTF-8 of at most eleven bytes
without control characters. Rejecting XML-normalization-sensitive control input
is a local subset restriction, not a claim that the original channel rejects
every such input. No whitespace, certificate bytes or signed message bytes are
repaired. Unsupported certificate forms remain unfinished work.

## A valid proof is not a trusted account

The caller's certificate pin is not independently enrolled or authenticated here.
In particular, this function **does not verify the device certificate's issuing
CA signature or a Nintendo root chain**. A generated device certificate without
a valid issuing-authority signature deliberately passes when the caller pins it;
the result explicitly reports that missing authority check. The pin must come
from a separately authorized enrollment process before any runtime use.

The request signature covers the challenge element only. Other SOAP fields,
including the operation, device/account/token fields, are not added to that
signed message. The same challenge proof can mathematically verify for either
reviewed sync operation if the caller supplies a matching context. Consequently
operation-bound issuance, expiry and atomic replay consumption remain separate
requirements. This mathematical verifier does not query a challenge store. The
separate [durable local challenge component](challenge_state.md) adds issuance
and single-use receipts, without changing this verifier's authority flags or
claiming an authenticated account.

Mathematical validity also does not prove exclusive private-key possession or
physical-console origin. The pinned public Dolphin signing implementation uses
deterministic application signing material; this inspection does not establish
its secrecy or replace it with an invented hardware-security assumption.

The returned inspection has separate false flags for pin provenance, Nintendo
CA-chain verification, freshness/replay and enrollment/account authorization.
Exclusive private-key possession is also explicitly unverified.
Its verified metadata is available only after this function completes; an
unchecked result object cannot claim verified signatures. There is no
authenticated-account result, token, registration success or server integration.

## Original wrapper and regression verification

`tools/verify_wii_shop_signing.py` executes original entry `0x80078570`, its
`0x80078430` raw signer helper, the actual copy/string routines and Base64
encoder `0x800830E0`. It intercepts only allocation/free, logging and ES call
`0x8025AA90`. Synthetic ES returns supply the signature/certificate bytes;
no actual device signer, original IOS ECC routine or credentials are used.
Reads/writes, code ranges, instruction count, objects, heap, input and stack
guards are bounded. Only the original Base64 initialization globals may change
outside those synthetic objects. Nonzero ES results preserve prior outputs and
skip Base64 conversion; they are not treated as signature success.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_proof tests.test_wii_shop_signing_native
```

Generated OpenSSL keys are temporary, and all test identities/data are synthetic.
Tests cover actual two-signature verification, altered certificates/messages,
wrong pins/device/title/challenge/operation, invalid points/scalars/Base64,
unavailable backend, explicit authority limits, exact native wrapper outputs,
nonzero ES paths and a native-wrapper-to-crypto handoff. Private-input and optional
emulator/backend tests skip explicitly when their inputs are unavailable.

The source/header audit can be repeated with explicit private inputs:

```powershell
.venv/Scripts/python.exe -m tools.audit_wii_shop_proof_sources --main PRIVATE_MAIN --source-root PRIVATE_SOURCE_ROOT --header-root PRIVATE_HEADER_ROOT
```

Remaining gates are actual IOS/hardware crypto acceptance and owned naming
profile, authorized device/certificate enrollment and CA trust, challenge/session
policy and replay-safe persistence, account authority and entitlement, the full
original startup/browser flow and native UI. No actual Wii backup, isolated
vWii credentials, installation, purchase or live account was accessed.
