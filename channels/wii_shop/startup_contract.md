# Retail v21 URL setup and navigation

Verified October 24, 2026 against the installed main DOL SHA-256
`aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898`.
These are isolated URL/navigation contracts, not a recovered complete startup
sequence or an observed HTTP request.

## Native execution

`tools.verify_wii_shop_url.verify` executes builder `0x8002BC10` and its actual
formatter `0x802BD290` in Unicorn without mocking either routine. Before entry,
the two base-string pointers are replaced with synthetic strings in emulated
RAM. No browser, network, NAND identity or account state is accessed.

The mode word at `0x80360728` selects the alternate base for values 2 and 8;
other tested values use the normal base. The installed normal pointer at
`0x8035F4F8` refers to the bare Shop host, while the alternate pointer at
`0x8035F4FC` refers to the previously identified manual-link template. These
addresses are static evidence; semantic names for all mode values are not
established by this test.

The function takes a suffix pointer in r3 and concatenates the selected base
and suffix using `%s%s`. It does not insert a slash or encode query text. The
formatter receives a 255-byte size argument, allowing 254 payload bytes plus
the terminator. The builder separately clears byte 255 and publishes the
256-byte buffer at `0x8036BF08` through pointer slot `0x803607D8`.

Synthetic cases cover normal/alternate modes, empty strings, exact-capacity
and oversized inputs, and preservation of an already encoded query suffix.
Output and pointer publication match independent expectations; guards on both
sides of the buffer remain intact. The harness rejects embedded NULs and
unbounded inputs before emulation. Native tests skip when private software is
absent; fingerprint mismatches are rejected.

## Native URL initialization and browser dispatch

`tools.verify_wii_shop_navigation.verify_navigation` now executes additional
original instructions with synthetic state. It rejects any executable with a
different fingerprint and stops on control flow outside the selected routines.

- The constructor dispatcher at `0x801D0910` walks the table at `0x802CE920`.
  Its 46 entries include `0x80028CE0`, which copies the normal base pointer from
  `0x8035F4F8` into the published URL slot. That initializer executes unchanged;
  the other 45 constructors return through stubs. The entry path calls the
  dispatcher through `0x801D08F0` before calling the application entry routine.
- In the application-entry slice `0x80023DF0..0x8002407C`, a stubbed launch-mode
  query supplies mode 0. With argument counts 0 and 1, the native branch leaves
  the constructor's URL intact and never reads the poisoned argument-vector
  pointer. These cases do not append `/startup`. They do not establish the mode
  or arguments supplied by an actual Wii Menu launch.
- The import table pairs `WWWOpenUrl` with callback slot `0x803605B4`. The loop
  at `0x80028944..0x80028978` resolves 117 names and writes the returned pointers
  to their associated slots. The loop executes unchanged, with a synthetic
  module handle and a stubbed resolver at `0x80258A80`. This verifies the table
  binding without loading Opera.
- The startup slice `0x800136A8..0x800136F0` accepts only result 1 from the
  prerequisite query at `0x801FE1C0`. It stores that comparison in object byte
  8, then requests initialization through `0x8002F560` and `0x8002F680`. Other
  tested results (0, 2 and unsigned -1) select the local EULA-page pointer at
  `0x8035F4E8` instead. The query and both initialization calls are stubs;
  their real configuration, success/failure and asynchronous work are untested.
- The dispatch thunk at `0x800293A0` loads the browser handle from object offset
  `0x240`, loads the current published URL, and tail-calls `WWWOpenUrl`. Both
  synthetic URL selections reach the callback unchanged, and callback results
  0, 1 and unsigned -1 propagate to the thunk's caller. The callback is a stub;
  no browser or network is invoked.

The harness runs these slices separately. It does not execute all intervening
initialization, establish their full runtime order, identify the prerequisite
query's configuration key, or show what happens after a real navigation. The
local EULA destination is evidence of that branch's role, not proof of the
query's complete semantics. Every URL used during these tests is synthetic.

Reproduce the checks with the private installed v21 executable available:

```powershell
python -m unittest tests.test_wii_shop_url tests.test_wii_shop_navigation
```

## Static caller leads and remaining work

Direct call sites were found at `0x80023EBC`, `0x80023FBC`, `0x80024064` and
`0x80024078`. Some prepare title-ID strings before calling the builder; another
passes a caller-supplied string. The mode-zero cases above show a path retaining
the bare host. Other launch modes and argument shapes still need execution
checks; the real Wii Menu launch parameters remain unobserved.

The nine absolute `/startup` strings inspected earlier are manual-link
templates. The resource archive contains local support/error pages and browser
configuration, but its listed `opera.ini` does not supply a home URL. Therefore
neither those literals nor the isolated routines prove the main storefront HTTP
request or its redirect chain.

Next is identifying the real launch parameters and prerequisite configuration,
then capturing browser requests in a controlled runtime profile. No
network redirect, replacement page, TLS modification or channel patch is
implemented by this offline work. Derived disassembly remains private.
