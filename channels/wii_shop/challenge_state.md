# Durable local challenge issuance and proof consumption

October 28, 2026. `jwc24.wii_shop_challenges` connects the recovered
[GetChallenge wire contract](startup_account.md) to the
[pinned-device proof verifier](device_proof.md) using actual private SQLite
state. This is JWC24 replacement-service implementation, not a recovered
Nintendo nonce algorithm, account service or original server database.
Existing browsing, offline fixtures and native UI assets are unchanged.

## Issuance and proof flow

`ChallengeStore` requires an explicit private directory and accepts an optional
explicit clock. It never selects a NAND/profile, acquires credentials or opens a
listener. `ChallengeBinding` requires the caller's device-certificate SHA-256
pin, full DeviceId, NG low word, title, next sync operation and evidence label.
Those are operator assertions; this component does not enroll or authorize them.

`issue()` first applies the existing IAS GetChallenge parser and requires the
request's canonical DeviceId to match that binding. Supporting this explicit
identity is a local service-path restriction; the standalone codec can still
inspect broader native optional-field forms. The caller supplies a lifetime of
1–3600 seconds, with no default. These lifetime bounds are local policy, not a
recovered Nintendo expiry contract.

The service generates eight random bytes encoded as eleven URL-safe ASCII
characters. The resulting 64 random bits fit the native eleven-byte capacity
without XML escaping, truncation or multibyte interpretation. The full issuance
binding and local issue/expiry times are committed before the existing serializer's
IAS response is returned. A uniqueness conflict retries bounded generation;
it never replaces an older issuance, even after expiry or consumption. A failed
commit or already expired response returns no issued result. Status zero in this
GetChallenge response means that JWC24 actually issued its own challenge; it
does not report a registered or connected Nintendo account.

`consume()` requires the signed registration request, SOAPAction and explicit
current binding. It checks the stored binding/window before invoking real
certificate/signature verification. Crypto executes outside the write lock.
A second transaction then rechecks the same issuance, current expiry and unused
state and commits exactly one receipt. Simultaneous valid proofs have one winner.
Invalid proofs do not consume the nonce. Expiry during crypto, changed issuance,
database failure and replay produce no receipt. Consumption persists across
store/connection restarts.

The private record retains canonical binding metadata, its digest, times, a
receipt ID and the accepted raw request's SHA-256; it does not retain SOAP bodies,
device tokens, certificates or private keys. The digest checks stored consistency;
it is not protection against a malicious administrator who can rewrite the
database and its metadata. No audit rows are automatically deleted or reused.

## Receipt boundary and remaining authority

Only store-produced result objects can report a completed issuance/consumption
commit. A successful receipt adds local expiry/single-use evidence to the
mathematical proof result. The system clock is not independently verified.
The pin's provenance, Nintendo issuing-CA chain, exclusive key possession,
device enrollment and account authorization remain explicitly unverified.
Challenge replay prevention does not repair the separate deterministic Dolphin
application-key limitation or expand the signed fields beyond the literal
Challenge element.

Every duplicate, including an identical request, is rejected by this component.
The receipt ID is not an idempotent registration result or an account token.
Registration/account mutation is not in this transaction, and there is no live
IAS error mapping, retry/recovery policy, signing service, entitlement or connected
state. Those operations must be integrated with an authorized account store and
the original client's retry lifecycle before enabling an actual account route.
No original flow is replaced with an invented account-success response.

## Verification

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_challenges
```

Sixteen tests use generated binary-curve keys and temporary private databases.
They exercise real certificate/message verification and SQLite commits, including
a two-connection race, restart/replay, invalid proof/context, expiry before and
after crypto, changed issuance, collision exhaustion, unknown database refusal,
and actual SQLite COMMIT denial with rollback. The original retail GetChallenge
reader also consumes an issued response unchanged through the existing guarded
native harness. A composed check also uses the original GetChallenge request,
issued-response reader, signing wrapper and full registration request builder
with actual 512-character certificate Base64 fields, then verifies/consumes the
resulting proof locally. The harness's old 96-byte synthetic-certificate limit
is expanded only for the two observed 512-byte certificate fields; environment
and challenge limits remain unchanged. The synthetic registration response is
a reported service error, so this request/receipt proof assigns no account.
Native comparison skips without its private original/dependencies;
crypto tests skip explicitly if the local OpenSSL curve backend is unavailable.

The combined 74-test Shop codec/proof/native suite also passed locally. These tests
make no network/account/profile call, import no real credential, publish no
provider content and modify no actual Wii backup. They do not prove the complete
Shop startup, original IOS signer, browser/account flow or acquisition service.
