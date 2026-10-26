# Project-wide restoration and coordinated validation

Updated October 26, 2026. The target is the original Japanese applications and
their native flows, with replacement services behind them. This inventory is
broader than the adapters already implemented. It is not a completion claim.

| Channel or service | Established implementation/evidence | Remaining completion gate |
| --- | --- | --- |
| [TV no Tomo / HBNJ](hbnj/README.md) | Native scheduler delivery and program-guide UI previously observed; country-wide builders and validators | Current eight-day data, genre/date/search/banner flows and repeat refresh in the coordinated native pass |
| [Forecast / HAFJ](forecast/README.md) | Native payload builders, previous download/weather-load observations, new [paired/signature validation](forecast/bundle_validation.md) | Refresh expired retained data; match isolated-client trust; original setup/banner/globe/full UI and Wii no Ma panel checks |
| [News / HAGJ](news/readiness.md) | Structural/graph/native task checks and [explicit signed publication plus shared-listener binary routes](news/publication.md) | Authorized current articles and native-record generation, installed-client trust/IOS registration/VFF/decompression, automatic hourly refresh and original UI |
| [Nintendo Channel / HATJ](nintendo/readiness.md) | CSData/reference checks plus [selected downloaded software titles and linked records](nintendo/listdata_contract.md) compared with original constructors/consumers | Complete tables and loader/manager lifecycle, download/auth/registration, genuine catalog/media, language eligibility, review/bookmark behavior and native UI |
| [Check Mii Out / HAPJ](cmoc/framing.md) | Bounded record framing/correlation plus [FD first-data fields and state-consumer checks](cmoc/startup_record.md) | Full FD meanings and genuine values, retrieval/auth/encryption, native menus/discovery/search, submission/contest/vote receipts and WC24 delivery |
| [Demae / HCHJ and address helper HCCJ](demae/README.md) | Nationwide directory, partial menu observations, [native item/variant ownership, stock/price and basket-code matching](demae/item_model_flow.md), phone confirmation and notice queue | Fresh actual branch variants/orderability, native images/shop/full basket/checkout integration, notice display and full postal delivery |
| [Wii no Ma / HCIJ](wii_no_ma/README.md) | Bootstrap/metadata routes, previous startup progress and local catalog/media/interaction tests | Original-compatible Flash shop, native playback/DSi transfer, household/setup flows, authentic artwork and native notices |
| [Wii Fit Body Check / HFNJ](body_check/research.md) | Verified client/dependencies, bounded plaintext-header inspection and [original CRC comparisons](body_check/header_crc.md) | Legitimate Japanese Fit/Plus save/profile, complete dataset semantics, registration/authentication and native question/mail/board flows |
| [Wii Shop](wii_shop/completion.md) | Captured browsing experiment, private original scripts, bounded native protocol checks, [offline display preflight](wii_shop/offline_preflight.md) | Full original Japanese screens/assets, startup/account contract, authorized acquisition/install behavior and native validation |
| [Wii Mail](mail/README.md) / shared WC24 | Retryable server batches/retirement, per-title delivery and [local Dolphin importer/persistence patch](mail/dolphin_receive.md) with temporary-mailbox tests | Install/review isolated candidate, live CGI/scheduler/native receipt/deletion/display, friend acceptance and original channel notices verified together |
| Everybody Votes | No client identified in the bounded stock-package inventory | Locate/verify the client and recover channel-specific contracts; no invented manifest or poll/vote results |
| [Today and Tomorrow / HAVJ](today_and_tomorrow/README.md) | Bundled affinity resource, local save and resource-consumer evidence; local-core track | Original date/birthday/Mii/prediction/save behavior; trace a concrete request before inventing a hosted feed |
| [Wii Speak / HCFJ](wii_speak/README.md) | [Version-file reader and two-word consumers](wii_speak/version.md) checked in guarded RAM; separate DWC/NAS/GameSpy leads | Genuine version capture, IOS crypto/task/delivery, actual voice/WFC/provider compatibility, hardware and original UI |
| [Digicam Print / HCDJ](digicam_print/README.md) | Native URL-controller/TLS/formatter checks; distinct provider and WC24 message boundaries | Authorized real printing/provider/upload/product/session contracts, native notices and original photo/controller UI |
| Internet, Region Select, Mii/Photo applications | Supporting browser/system/local applications; inclusion does not establish a hosted WC24 service | Inventory the dependencies used by restored channels separately from standalone replacement services |
| [Online multiplayer](online_play/README.md) | Provider integration plan | Per-game/region Wiimmfi or alternate-provider setup and actual multiplayer validation; not implemented |

The [expanded package inventory](../research/channel_scope_followup_20261026.md)
distinguishes verified title identities from uninspected behavior. The
[experience-channel review](../research/experience_channels_readiness_20261026.md)
records the current source and implementation blockers. The private Nintendo
index, manuals and channel executables are evidence inputs; generic SDK
guidance does not supply missing service schemas. Original material, private
keys and device backups remain outside Git.

## Shared preparation before opening a channel

Run the full offline suite first:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests
```

Tests that need private originals or optional native-emulation dependencies
may skip in a fresh checkout. Review the skip count. Passing available tests
does not establish original rendering, complete service behavior or hardware
compatibility.
The public CI job now runs this available offline suite as well as compilation
and package checks. Private-fixture skips remain visible and are not native
verification. Wii no Ma's [fixture boundaries](wii_no_ma/testing.md) preserve
assertions for present inputs; missing private media is not replaced with
invented published content.

The new read-only multi-manifest preflight checks payload presence, task-slot
and route/filename conflicts, optional task/account prerequisites and optional
key-file presence/size. Select one origin in memory for a combined listener:

```powershell
.venv/Scripts/python.exe -m jwc24 preflight `
  channels/hbnj/channel.json channels/forecast/channel.json channels/wii_no_ma/channel.json `
  --base-url http://127.0.0.1:8080
```

The checked-in manifests retain different historical/local origins. Without
an explicit common origin, this combination correctly fails the shared-listener
check. `--base-url` does not rewrite their files or device registrations.
Use a client-reachable address when preparing a real-console deployment;
loopback above is an offline example, not a console network configuration.

Optional `--dl-list`, `--config` and `--nand-root` inspect only explicitly
selected inputs. They have no default profile. Keep those inputs confined to
the authorized isolated test profile. No profile, task, ID, save, credential,
DNS rule or original backup is changed. Output excludes private paths, URLs,
device IDs and secrets. Missing optional inputs remain `not_supplied`.

`--max-payload-age-seconds` is an optional file-modification-age policy. It is
not internal payload freshness validation. Forecast's separate current-window
check is not provider-observation-age verification either. Schema/signature,
task completion, VFF consumption and native rendering remain separate gates.

The download server now selects the private envelope key belonging to each
payload's manifest title. Multiple encrypted channels can share the listener;
assets and regional variants retain their owner's key. This removes a server
restriction without proving a stock client trusts replacement data. `serve`
accepts the same in-memory `--base-url` selection. No server is started by
`preflight`.

## One coordinated native validation session

Prepare every source-supported offline path before requesting device testing.
Unrecovered formats and missing original screens must be implemented/recovered
first; they cannot be closed by testing an invented response. Regenerate
time-sensitive inputs immediately before the session and retain validation
reports and source provenance privately.

Use the authorized isolated Dolphin profile as the first hub. The owner's
actual Wii backup remains untouched. The new physical NTSC-U console changed
to Japan is a distinct target: its installed menu/IOS/title versions, settings,
network reachability and save prerequisites need their own recorded results.
No profile or console setup is inferred from the region label alone.

For each implemented channel, record the exact working-copy title/build,
first-run and returning-user state, original navigation, downloads, refresh,
error handling, sounds/animations, content consumption and expected mail
notice. For shared WC24, record scheduler readiness, each task result,
destination data, internal sequence/time evidence and actual UI use
separately. A listening port, HTTP 200 or passing parser test is insufficient.

The session should cover HBNJ's guide/date/genre/search, Forecast's location/
globe/weather and Wii no Ma integration, Demae's browsing/item/basket/provider
handoff/notice, Wii no Ma's room/media/setup, and each newly implemented
channel's complete native flow. Do not label pending News/Nintendo/CMOC or
Shop commerce behavior ready merely to put it on the checklist. Add those
flows once their offline implementation gates are satisfied.

One prepared session reduces repeated setup and avoidable testing cycles.
Real-device findings can still require fixes and another validation pass;
offline checks cannot guarantee the absence of hardware-only failures.
