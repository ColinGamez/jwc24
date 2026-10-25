# Native v21 socket/HTTP initializer boundary

October 25, 2026. **The two previously stubbed startup initializers are
socket/HTTP setup wrappers, not proof of EC/plugin initialization or
GetECConfig.** Original diagnostics corroborate `SOInit`, `SOStartup` and
`NHTTPStartup` at the observed call boundaries. This work executes their bounded
caller instructions with all external operations intercepted; it does not start
real threads or run the socket/HTTP implementations.

The [metadata report](wii_shop_network_initializers_20261025.json) pins the
original installed-v21 main executable, four native slices and diagnostic
literal hashes. It records only API-name tokens, addresses, synthetic states
and test results. No original bodies, disassembly, full request queries or
credentials are published. The installed-content fingerprint establishes
agreement with the comparison target; Nintendo's signature is not independently
verified.

## What the actual callers do

| Native caller | Observed boundary |
| --- | --- |
| `0x8002F560`, called at `0x800136D8` | Selects a heap group, obtains a `0x18000`-byte allocation aligned to 32 bytes, constructs a heap and passes allocator callbacks `0x8002FAA0`/`0x8002FAC0` to `0x800BF214`, bracketed by `SOInit` diagnostics |
| Same caller after a zero result | Obtains a `0x4000`-byte worker stack aligned to 32, publishes it at object offset `0x330`, sets object state 1 and returns 1 |
| `0x8002F680`, called at `0x800136E0` | Passes thread-object offset `0x18`, entry `0x8002F710`, argument 0, stack size `0x4000`, priority 14 and attribute 1 to the creation boundary `0x801CC6D0`; then calls resume boundary `0x801CCE00`, sets state 2 and returns 1 |
| Worker entry `0x8002F710` | Stores an explicitly stubbed preparation value, calls `0x800BF3E0` bracketed by `SOStartup` diagnostics, then passes allocator callbacks `0x8002FAE0`/`0x8002FB00` and priority 15 to `0x800B0B30`, bracketed by `NHTTPStartup` diagnostics |
| Polling prefix `0x8002F820` | In state 2, queries `0x801CC0E0` with the thread object. Only a nonzero result permits copying worker state/error/preparation fields into the caller object |

The worker's state block is at `0x803B2D18` in emulated RAM. The harness supplies
its contents; it reads no real device/configuration state. Worker success sets
state 3 and error 0. This is a state of the observed socket/HTTP wrapper, not an
ECommerce connected flag or permission to download.

The diagnostic labels identify the API family associated with the calls. They
do not independently establish the complete SDK implementation or every
callee's internal behavior. Callback pointers are observed original arguments;
the allocator callbacks themselves are not executed in this harness.

## Verified failure and polling branches

- A nonzero `SOInit` stub result makes preparation return 0 before worker-stack
  allocation or launch. A missing worker-stack allocation likewise returns 0.
- A zero thread-creation result sets state 4 and the original marker **50100**,
  returns 0 and skips resume/worker execution. Its original screen/message
  interpretation is not established here.
- A negative `SOStartup` result enters the original error-helper boundary
  `0x800A9EDC`; the caller negates that helper's synthetic result before storing
  the worker error. It skips `NHTTPStartup`. Nonnegative socket results continue.
- Any nonzero `NHTTPStartup` result sets worker state 4/error 50100. Literal zero
  sets worker state 3/error 0.
- A zero completion-query result leaves object state 2 and does not copy the
  worker result. States 0, 1 and 4 leave this polling prefix without querying;
  state 3 reaches the next timer/callback branch, where this harness stops.

## Harness boundary and reproduction

`tools.verify_wii_shop_network_initializers.verify_network_initializers(source,
results=None)` accepts the pinned original executable and optional
`SyntheticNetworkResults`. Every result/flag has a checked local type/range.
Its default results are explicitly invented synthetic return values, not live
service defaults. The return dictionary records boundary arguments, state
changes, guards and limitations; it contains no captured account data.

Only the selected initializer/worker/poll-prefix instructions and ordinary
register save/restore helpers execute unchanged. Allocator, heap construction,
memory-clear, logging, socket, HTTP and thread boundaries are explicit stubs.
The worker runs as a direct isolated invocation after synthetic launch success;
there is no scheduler and no asynchronous ordering claim. Polling stops at
`0x8002F884` or `0x8002F968` before unrelated timer/callback processing.

The harness rejects a changed executable, unexpected control flow, writes
outside the synthetic object/stack/selected globals, changed guard bytes and
instruction-limit failures. No browser, network, IOS, real account/key/ticket,
NAND state, full startup or EC operation is invoked. Synthetic writes occur
only in the emulator's memory; the owner's files remain unchanged.

Twelve focused tests pass, covering callback/stack/priority arguments, success,
each failure gate, the negative socket-result conversion, nonnegative socket
results, completion polling, other polling states, source rejection and input
bounds:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_network_initializers
```

The report records nine synthetic execution profiles. The only retained next
leads are the poller's direct call sites `0x80027434`, `0x800284A4` and
`0x8002EDE0`, plus the unexecuted phase-3 branch. They were not traversed. Plugin
registration, the actual EC initialization/connect caller, full browser handoff
and GetECConfig's position in a real launch remain separate unfinished work.

The sibling native request-builder harness was independently reviewed for
synthetic input/output bounds, private representations, pointer containment,
header-vector bounds, original version-pointer checking and intercepted
transport. No material XML-shape/provenance mismatch was found. Its verified
request contract belongs to its separate report; these network-wrapper tests
do not execute that builder or imply a full connection.
