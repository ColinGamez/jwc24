# Retail CheckDeviceStatus and ticket-sync decisions

October 26, 2026. The complete original v21 `CheckDeviceStatus` operation now
runs offline with synthetic transport: request construction, common response
parsing, balance/time extraction, and the following sync-state decisions. This
does **not** establish account authorization, registration, complete runtime
startup, an authoritative point balance, or ticket synchronization.

The [metadata report](../../research/wii_shop_device_status_native_20261026.json)
pins the original executable and three inventory-verified private source files.
It records eight complete-operation cases and five error/partial-state cases.
The source inventory establishes extraction consistency, not independent
provenance of the enclosing archive. Original software and recovered source
bodies remain private and outside Git.

| Original retail boundary | Verified role |
| --- | --- |
| `0x80088DF0` and `0x80088EB8` | Connection-worker virtual dispatch sites before and after registration |
| `0x80321340` | Original run vtable, with `0x80086BE0` at its run offset |
| `0x80086BE0` | Complete CheckDeviceStatus operation and sync decisions |
| `0x80086E50` | Request construction, transport handoff, response dispatch |
| `0x800870D0` | Balance/currency and three ticket-sync-time extraction |

The harness begins at either original dispatch site, supplies a synthetic object
through the expected global, and uses the original vtable to enter the operation.
It stops when the operation returns to the worker. The enclosing conditional
branches, scheduling, registration path and eventual connected-state assignment
are not executed. This is stronger evidence than a string reference, but is
still a bounded consumer test rather than a complete connection trace.

## Standalone backend component

`jwc24.wii_shop_device_status` supplies a strict request parser, an explicit
offline response serializer and a pure `plan_device_status_update` function.
No listener or existing preview route imports the component. It performs no
network request, credential lookup, signature verification, config write,
shop-log change, point credit, entitlement grant or connected-state transition.

The request action is `urn:ecs.wsapi.broadon.com/CheckDeviceStatus`, Version 2.0.
The retail wire contains the ECS common fields, including SerialNo, optional
ApplicationId/TIN and the optional PostalCode Name/Value attribute. It has no
operation-specific ECVersion and no CAS Age field. Account/device values stay
opaque and are excluded from representations and errors. Parsing does not
authenticate them. Arbitrary namespace prefixes and the optional correctly
resolved request type are accepted; unknown fields/actions are rejected.

A zero-status response requires explicitly supplied `EvidencedDeviceStatus`
facts: balance, ForceSyncTime, ExtTicketTime, SyncTime, and a nonempty evidence
reference. A nonzero-status response forbids those facts. Status and its evidence
reference have no defaults. References are caller assertions; this component
does not independently verify their provenance or truth. It emits the literal
native response wrapper and `Balance/Amount/Currency`, with currency `POINTS`.
No historical catalog price or account identifier is converted into a balance.

The serializer accepts actual Python signed 32-bit balance and signed 64-bit
times, including their endpoints, matched against the original numeric readers.
It does not claim all syntactically accepted numbers are meaningful server facts.
The original converters also accept a trailing suffix such as `123junk`; the
serializer intentionally accepts only typed integer facts. XML byte/structure/
text bounds and this canonical typed-value policy are local defensive rules.

## What the complete native consumer does

For a complete zero-status response, the original operation caches the supplied
balance and compares all three response sync times with the local snapshot:

- All equal: marks times as matching. Existing pending-sync and import-all flags
  remain set if they were already set.
- Any difference: marks times as different and requests ticket sync. It requests
  a config save only when changing the pending-sync flag from false to true.
- ForceSyncTime differs: also sets import-all. Other differences alone do not
  newly set that flag.
- The operation marks the sync check completed. It leaves the local sync times
  unchanged; the response times remain separate in the operation object.
- When the internal ECDK environment flag is false, it requests a shop-log update.
  It additionally requests clearing the ECDK sync-needed state only when no sync
  remains pending. ECDK here is an internal environment flag, not a vWii label.

The pure planner returns the resulting snapshot and these side-effect requests.
It does not execute them. Its inputs must contain the complete response facts;
it is not a model of partial parsing or error recovery.

Error paths matter for a future integration:

- Wrong currency returns `-4034` before changing the balance cache.
- Missing Balance/Amount returns `-4006` without changing the cache.
- Missing any later sync-time field returns `-4006` **after** updating balance
  and its cache flag. It does not mark the check completed or run the sync
  decision. The operation's three prior time values remain unchanged.
- Reported service error and transport error leave the tested snapshot intact
  and skip response extraction or the common parser as appropriate.
- The operation ignores the config-save return value: a synthetic failed save
  still returns zero and marks the check completed. A service must not interpret
  this return alone as proof of durable state or account connection.

## Verification boundaries and integration work

`tools.verify_wii_shop_device_status` runs the original request builder, XML
helpers, numeric converters, complete balance/time consumer and sync decisions.
The synthetic boundary stubs cover transport, allocation/free, logging, time,
locks, config save, shop log and clearing ECDK sync-needed state. The harness
counts the last three calls without performing their side effects. Instruction
limits, object/stack/heap guards and a native memory-write allowlist are checked.
The native connected flag remains false throughout these cases.

Seventeen focused tests compare both original worker dispatches and complete
native state with the pure planner; they also cover signed endpoints, optional
request fields, partial state, currency errors, transport/service errors, ignored
save failure, privacy and local input bounds. Native tests skip without the
private fingerprinted executable; the standalone component tests remain usable.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_device_status tests.test_wii_shop_device_status_native
```

Before connecting a route, establish authenticated account/device binding and
authoritative balance/sync facts, signing/registration and persisted-state
semantics. Then integrate the enclosing worker and original browser flow,
including its error and recovery behavior. This component supplies the next
verified request/consumer contract; it does not make startup or commerce complete.
No original assets, Dolphin settings, private profiles or Wii backup changed.
