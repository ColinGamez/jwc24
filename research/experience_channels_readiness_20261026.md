# Experience-channel offline readiness, October 26, 2026

This bounded pass covers Forecast, Demae, Wii no Ma and Wii Fit Body Check.
It does not establish completion of their original experiences. No Dolphin
process was launched, no NAND or game save was changed, and the owner's actual
Wii backup was not read or modified. Existing unrelated worktree edits remain
untouched.

## Concrete addition

The new [Forecast bundle validator](../channels/forecast/bundle_validation.md)
joins the two existing binary checks and adds optional verification of both
RSA/SHA-1 signatures against an explicitly supplied public key. It also checks
cross-file current-location and weather-condition references, locales,
overlapping validity windows and optional current-time validity.

A read-only check of the retained private generated pair found 653 catalog
locations and 655 current records. Both signatures verified against the
supplied JWC24 public key. All current location/condition references resolved.
Two location keys repeat identical current records; these are retained and
reported, while contradictory repeated records fail the local policy.

The same pair **failed the current-time check**: `forecast.bin` was outside
its validity window. Successful historical structure/signature checks do not
make old weather current. No timestamps or generated files were changed, and
the private provider acquisition or refresh job was not run or modified.

The new checker is a read-only offline gate. Live refresh/publication still
needs to invoke it explicitly. Signature verification against a supplied key
does not check the installed client trust patch or prove real-Wii acceptance.

## Checks completed

- 93 focused tests passed across the new bundle checker, existing Forecast
  validator/CLI, Body Check inspector, Wii no Ma metadata, interactions,
  bootstrap, catalog and local movie/category server behavior.
- The new bundle module contributes 14 tests, including real temporary
  RSA-2048 signatures generated with OpenSSL, corruption in either file,
  unavailable-verifier errors, missing and conflicting references, validity
  boundaries and read-only CLI output. No production private key is used by
  those tests.
- The current-window check covers the files' validity intervals, not individual
  observation timestamps. A regression retains an old observation in a current
  envelope and checks the explicit `observation_timestamps_checked: false`
  metadata. Provider observation freshness remains a separate requirement.
- All 217 `test_demae*.py` tests passed. Their synthetic/native harnesses and
  local endpoint checks retain their previously documented mock boundaries.

## Remaining channel requirements

| Channel | Existing evidence | Still required before claiming completion |
| --- | --- | --- |
| Forecast | Native format builders, individual validation, previous scheduler/native weather-load observations, new paired/signature checks | Refresh authorized provider data; validate freshness and matching trust in the isolated profile; check banner, location setup, full forecast and Wii no Ma weather panel together |
| Demae | Nationwide directory retention, reviewed partial menus, native parser/model harnesses, explicit phone confirmation and separate notice queue | Branch-specific fresh variants/sizes/prices and stock semantics; native item/basket/checkout wiring; actual order and notice display verification; full postal delivery path |
| Wii no Ma | Bootstrap and metadata routes, past native startup progress, durable local interaction receipts, local media/catalog tests | Original-compatible Flash shop payload; native media codec/playback and DSi transfer; registration/setup and household-room flow; review generated experimental artwork against original-only direction; actual notice delivery |
| Wii Fit Body Check | Stock title/dependency inventory, bounded plaintext dataset-header inspector | Legitimate Japanese Wii Fit/Plus save and personal profile; dataset fields/records; WC24 registration/authentication; native save-backed startup, mail/questions and balance-board behavior |

The Wii no Ma generated poster/frame and Rakuten catalog experiments are not
proof of recovered original assets or original commerce behavior. They remain
preserved existing experiments. The Body Check inspector checks only a
twelve-byte CRC-covered header area, not health-record semantics or outer
authentication. Directory presence likewise does not make a Demae restaurant
deliverable or an observed menu currently orderable.

Relevant detailed records remain [Demae status](../channels/demae/README.md),
[Wii no Ma status](../channels/wii_no_ma/README.md), and
[Body Check inventory](../channels/body_check/research.md). A coordinated
hardware pass should follow completion of the missing source/implementation
requirements; these tests do not remove those requirements.
