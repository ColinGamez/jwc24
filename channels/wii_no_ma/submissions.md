# Wii no Ma local submission backend

`InteractionStore.submit(endpoint, form)` supplies a durable local backend for
the existing movie-rating, paid-rating, questionnaire and picture-rating
experiments. Its immutable result contains the local receipt identifier and
the existing XML response. It returns only after the SQLite transaction commits;
an insert, retry update, migration or commit failure produces no result.
The HTTP adapter must send `result.response` after this call succeeds.

The underlying `record()` API remains available for callers that only need a
receipt. `get_response()` still supplies the existing static XML for compatibility
with earlier experiments and inspectors. Calling that static function, or
receiving its XML through a GET request, is not evidence of a stored submission.
The shared HTTP adapter now uses `submit()` to bind its POST response to the committed receipt.

## What is persisted

Each distinct endpoint and form has a private local receipt. The database
retains all submitted string fields, repeated values in their submitted order,
the first and last receipt timestamps, and the number of identical attempts.
Distinct endpoints and changed fields remain distinct receipts. Reopening the
database after a successful submission recovers the same fields and identifier.
The default server location is `private/wii_no_ma/interactions/receipts.sqlite3`.
Form contents may include device and household information; they are not public
catalog data and must stay outside Git.

Schema version 1, stored in this database's SQLite `user_version`, fixes legacy
retry matching. Legacy JSON is parsed and canonicalized for fingerprints, so
whitespace, object-key order and escaped Japanese characters do not create new
receipts. Original stored JSON, identifiers and existing attempt counts are
preserved. When older duplicates exist, only the earliest receipt anchors new
identical attempts; the other historical receipts remain intact. This does not
combine old attempt counts or infer a number of voters. Schema changes and
fingerprint migration occur in the same serialized transaction as submission.
Malformed legacy data, including duplicate JSON object keys (even when one key
uses Unicode escapes), rolls back the upgrade and remains available for repair;
it is not replaced with an empty database.

## Original contract evidence and limits

The locally preserved original HCIJ v1025 HDPK resources establish these four
response roots. Each requires a `code` value in the inclusive range 1 through 999
and permits an optional `msg` with a maximum of 100 UTF-16 code units.

| Endpoint | Original schema root | Retained experimental code |
| --- | --- | --- |
| `/url2/evaluate.cgi` | `Evaluate` | 1 |
| `/url2/pay/pevaluate.cgi` | `PayEvaluate` | 1 |
| `/url2/enquete.cgi` | `Enquete` | 2 |
| `/url2/piceval.cgi` | `PicEval` | 1 |

Source sizes, SHA-256 hashes, decoded field constraints and verification scope
are recorded in [the validation report](../../research/wii_no_ma_submission_validation_20261026.json).
Original resource bytes stay private. This is static original-schema evidence;
the native XML parser was not executed for this batch.

The experimental code values originally came from the separately preserved
third-party `room-server` implementation. Their meanings have not been verified
against an original Nintendo acknowledgment completion consumer. The nearby
original Flash `EvaluateClassController` exposes `SetInfo1`, `GetInfo1`,
`SetInfo2` and `GetInfo2`; its configuration dispatch is not evidence of HTTP
result-code semantics. No original copy, UI layout or asset was replaced here.

Persistence is real local service behavior, but request-field meanings,
identity/eligibility checks, original vote aggregation, paid authorization and
native acknowledgment/menu completion remain unfinished. Receipts are not vote
totals or original Nintendo service records. This component does not process
purchases, send notices, modify household saves, or change device profiles.

## Verification

`python -m unittest discover -s tests -p 'test_wii_no_ma_submission.py' -v`
uses synthetic forms and temporary databases. It verifies all four response and
reopened-receipt pairs, failed inserts and retry updates, legacy Unicode JSON
retry matching, prior fingerprint repair, transactional migration rollback for
invalid or ambiguous legacy JSON, and
absence of storage for invalid forms or an unavailable response. Existing
interaction tests additionally exercise concurrent workers and restart recovery.
These are local backend checks, not a Dolphin or hardware test.

The HTTP binding has three loopback regressions covering all four endpoints,
reopened UTF-8 forms/retries, storage failure without a static acknowledgment,
malformed/empty forms and body framing. Shared request bodies are bounded before
reading, duplicate lengths and unsupported transfer encoding close the request,
and GET consumes its own framed body before the next persistent request. This
protects receipt dispatch and neighboring binary routes; it does not verify
original NHTTP request meanings or result-code semantics.
