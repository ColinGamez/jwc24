# Retail v21 EULA and manual-channel commands

Verified October 24, 2026 against the same main-executable fingerprint as the
[startup checks](startup_contract.md). This connects the bundled pages' command
names to native pending requests and title-launch arguments. It does not execute
the destination channels or accept an agreement.

## Executed native path

`tools.verify_wii_shop_transition.verify_transition` runs the original property
getter at `0x8002B360`, string comparisons and method-creation helper. The browser
function factory is a stub, but its context, callback pointers and output record
are checked. The captured callback then executes its native adapter and request
setter against a synthetic transition object.

| Page command | Native adapter | Pending request | Japanese destination title |
| --- | --- | --- | --- |
| `jumpToEULAViewer` | `0x8002AEE0` | 7 | `0001000848414B4A` (`HAKJ`) |
| `jumpToManualChannel` | `0x8002AF10` | 9 | `000100024843554A` (`HCUJ`) |

The adapters obtain the object through accessor `0x80018370`. The setters at
`0x8001A440` and `0x8001A4D0` write object offset 4 only when it is zero. When
another request is pending, its value and the rest of the object remain intact.
The adapter still returns status `0x11`; that status alone does not establish
that a new request was queued.

For a newly queued request, dispatcher `0x8001A530` executes with its four cleanup
calls stubbed. Its native switch table at `0x802F8470` selects the EULA or manual
branch. AREA decoding at `0x801FE4E0`, the native string comparisons, and selector
mapping at `0x80014350` execute unchanged. Only settings access is stubbed to
supply a synthetic three-letter `AREA` value or a read failure.

| Synthetic AREA | Decoded code | EULA destination | Manual destination |
| --- | --- | --- | --- |
| `JPN`; `TWN` / `ROC` | 0; 5 | `0001000848414B4A` | `000100024843554A` |
| `USA`, `BRA`, `HKG`, `ASI`, `LTN`, `SAF`, `CHN` | 1, 4, 7, 8, 9, 10, 11 | `0001000848414B45` | `0001000248435545` |
| `EUR`, `AUS` | 2, 3 | `0001000848414B50` | `0001000248435550` |
| `KOR` | 6 | `0001000848414B4B` | `000100024843554B` |
| Unknown value or settings-read failure | unsigned -1 | `0001000848414B45` | `0001000248435545` |

The fallback to the `E` destination is observed native behavior, not a proposed
region setting. At `0x801D0740`, the harness intercepts the launch routine and
checks the two title-ID words, launch-code argument 0 and null argument pointer.
No launch, cleanup, browser operation, network request or NAND write takes place.

## Failure and scope checks

Unknown, case-changed and suffixed property-name probes return getter status 8
without creating a function. Negative factory results return getter status 10
without changing the output record or pending request. Nonnegative factory
results produce getter status 7 and the synthetic function handle. These are
numeric bridge results; they are not HTTP statuses.

Output-record guards and the entire transition object, including guards, are
checked for unexpected writes. Busy pending requests are preserved and are
deliberately not dispatched by this harness. Unexpected native control flow,
input sizes/types and executable fingerprint mismatches are rejected.

```powershell
python -m unittest tests.test_wii_shop_transition tests.test_wii_shop_navigation tests.test_wii_shop_url
```

Browser function creation, origin access, the real settings reader, cleanup,
destination installation/content validity, IOS behavior and actual channel
transitions remain unverified. This does not establish whether a real Shop page
would expose the manual command on a particular platform. In particular, it does
not emulate an EULA acceptance or change `IPL.EULA`.

## Current private-profile metadata check

A read-only check found an installed TMD for the Japanese EULA target:
title `0001000848414B4A`, version 3, IOS 56, six referenced contents, TMD SHA-256
`0d62916ea2f5a4a31b022e3630b3ed0add95d4b6fce082ca715791aebb48ddbb`.
Its referenced contents and signature were not verified in this check.

The requested Japanese manual target has no TMD at
`title/00010002/4843554a/content/title.tmd` in this profile. No target was
installed or repaired. This is a profile observation, not a requirement to add
that channel before the ordinary Shop launch can be tested.
