# JWC24

JWC24 is my project to revive discontinued Japanese WiiConnect24 services for
4.3J Wii software. The goal is one replacement WC24 platform that can support
multiple original channels without modifying or redistributing their WADs.

The first channel I brought back is **TV no Tomo Channel G-Guide for Wii**
(`HBNJ`). It now boots from a clean Japanese v512 WAD in Dolphin, completes its
original setup flow, downloads data through the Wii's native WC24 scheduler,
and displays a current Japanese television guide.

> This repository documents and develops the replacement service. It does not
> contain Nintendo software, WADs, NAND data, private keys, or downloaded guide
> data.

## Japan-first. Original-channel-first. Native WC24.

JWC24 is an independent implementation built from my own testing and reverse
engineering. It is not a WiiLink24 fork, frontend, or server clone, and it is
not affiliated with WiiLink24.

What defines this project is its focus:

- **4.3J comes first.** JWC24 is designed around Japanese system software and
  Japan-only channels instead of treating them as later regional additions.
- **Original WADs stay original.** The target is to revive clean channel
  releases by recreating the services and data formats they expect.
- **The experience must stay original.** Preserve Japanese assets, copy,
  layouts, sounds and native flows. Placeholder content, invented metadata and
  repurposed controls are not finished restoration work. The Shop experiment's
  remaining [fidelity gaps](channels/wii_shop/authenticity.md) are documented.
- **The native WC24 path matters.** Downloads go through Dolphin's emulated
  IOS WC24 scheduler, task table, encrypted delivery, and VFF storage.
- **One foundation, multiple channels.** TV no Tomo is the first proof, while
  the shared transport is being built for other 4.3J WC24 applications and
  Wii Mail.
- **Reverse engineering is part of the result.** Parsers and independent
  validators document the recovered formats instead of hiding channel-specific
  behavior behind replacement screens.

The short version: JWC24 is about preserving how Japan's original Wii channels
actually worked, then giving them new data without replacing their identity.

## What I have working

- The original HBNJ WAD runs without channel binary patches.
- Dolphin's WC24 scheduler downloads native `header.bin`, `epg.bin`, and
  `str.bin` files from JWC24.
- JWC24 produces the channel's original WC24 AES-OFB envelope, Nintendo LZ10
  compression, and HDPK data structures.
- The guide covers all 54 Japanese broadcast areas and 376 terrestrial
  services.
- Area-coded requests receive compact regional payloads; Gunma currently has
  11 stations and 3,475 programs across the channel's full eight-day window.
- Current titles, times, genres, and Japanese program descriptions are packed
  into their native TV no Tomo records.
- The original genre-search table is populated with 12 Japanese categories,
  and the date carousel receives eight consecutive broadcast days.
- The original activation, query, popularity, and synchronization CGI calls
  receive the response contracts expected by the channel.
- A daily job collects, validates, packs, independently checks, and atomically
  publishes a new guide.
- The shared Wii Mail service implements account registration, Dolphin's
  challenge/HMAC check, multipart sending, persistent recipient queues,
  multipart receiving, and deletion independently of any one channel.

## Why it is more than a TV no Tomo patch

The shared code in `jwc24/` handles WC24 task inspection, safe provisioning,
payload delivery, encryption, compression, and validation. TV no Tomo lives in
`channels/hbnj/` as the first channel-specific adapter.

That split is intentional: future 4.3J channels can have their own manifest,
data generator, validators, and CGI behavior while reusing the same WC24
transport and mail service.

```text
original 4.3J channel
        |
        v
Dolphin IOS /dev/net/kd/request
        |
        v
native WC24 download task
        |
        v
JWC24 transport and channel adapter
        |
        v
validated replacement data
```

## Current project status

The [project-wide restoration inventory and coordinated test plan](channels/README.md)
tracks every requested channel, including News, Nintendo Channel, Check Mii Out
and additional stock Japanese applications. It separates unfinished service
contracts from offline checks and native acceptance. A new read-only
`jwc24 preflight` command checks combined manifests and optional task/account
inputs; encrypted downloads now select each payload's owning title key, so
multiple encrypted channels can share a listener without sharing keys.
The [paired Forecast validator](channels/forecast/bundle_validation.md),
[CMOC framing checks](channels/cmoc/framing.md) and
[offline Shop display preflight](channels/wii_shop/offline_preflight.md) add
specific preparation gates. They do not mark those channels complete.

The [Nintendo collection index](research/nintendo_collection_index_20261022.md)
maps the local research tree and existing archive catalogs to JWC24 follow-up
work. The [early Wii SDK PDF review](research/sdk_pdf_review_20261022.md) covers
19 platform manuals and their channel-specific uses and limits.
The [goldmine WC24 follow-up](research/goldmine_wc24_followup_20261022.md)
records three later archived manuals, postal-tool evidence and shared diagnostics.
The [Wii Shop track](channels/wii_shop/README.md) serves 844 grouped Japan titles
over loopback HTTPS to the original v21 browser in an isolated Dolphin profile.
Historical captures now supply the home/list layouts, 834 detail views, 836
controller pages and [835 More Details pages with 1,670 original screenshots](channels/wii_shop/descriptions.md).
The preview preserves captured scrolling, paging and return context. A recovered
generic no-results view replaces the modified template for zero-match name
queries; its original Japanese keyword-search flow remains unverified.
The [captured Virtual Console menu](channels/wii_shop/captured_navigation.md)
now preserves its original control meanings and title-search input. Original
Japanese controller-button artwork replaces the English normal/hover variants;
this does not establish a fully recovered Japanese interface.

[Historical metadata](channels/wii_shop/title_metadata.md) supplies 835 captured
names/publishers and 774 historical point amounts. Separate [image roles](channels/wii_shop/image_roles.md)
cover 776 list icons and 835 detail images. Missing data, current offers and
ownership are not invented. Remaining original Japanese/category screens,
artwork gaps and native visual checks are recorded in the [completion list](channels/wii_shop/completion.md).
Accounts, purchases, content acquisition and installation remain unfinished.

The [CAS catalog codec](channels/wii_shop/soap_contract.md) is an offline,
source-backed protocol component without a live account or commerce route.
The separate [ECS configuration codec](channels/wii_shop/ec_config.md) supplies
explicit offline fixtures checked against selected original v21 request,
response and URL-storage code. The [origin checks](channels/wii_shop/origin_access.md)
and [network initializer checks](research/wii_shop_network_initializers_20261025.md)
separate those boundaries from the still-unfinished full startup and account connection.
[Manual recovery](channels/wii_shop/manual_recovery.md) found a partial Japanese
game guide but no Shop operations guide; it stays disconnected from the UI.
[Native startup](channels/wii_shop/startup_contract.md) and [EULA/manual command](channels/wii_shop/bridge_contract.md)
checks are distinguished from actual browser evidence. Original assets,
software and device data stay private; current templates still need native
Dolphin visual verification.

TV no Tomo has reached its real program-guide UI with current listings. The
latest build validated:

- 54 broadcast areas
- 376 stations
- 123,803 programs across eight broadcast days
- 104,665 program descriptions
- 12 native genre-search categories
- every header-to-EPG station key
- every EPG-to-string record index
- every regional native payload

The next work is focused on visual testing of the completed genre and date
flows, restoring the bundled Japanese Forecast and News channels through their
native WC24 tasks, incoming-mail support in Dolphin's KD implementation,
friend registration, easier local server setup, and adapters for more Japanese
WC24 channels. Forecast comes before Wii no Ma bootstrap work because the room
UI integrates weather state.

Wii no Ma's native Flash shop is unfinished: no compatible `index.esf` entry
is configured, so new bootstrap builds set `shopvalid=0`. The paid catalog
and Rakuten product artwork are separate features; they do not implement the
native Flash shop or in-channel checkout.

## Demae Channel restoration

Demae (`HCHJ`) is an active experiment, with Hot Pepper restaurant discovery
and a planned Demae-can phone checkout handoff. The original home flow is
preserved; the QR handoff belongs after browsing and basket selection.

- The persistent local archive retains **9,400 restaurant listings across all
  47 prefectures**, including source history and reviewed branch links. This
  is a partial directory snapshot, not complete delivery coverage.
- The latest reviewed menu imports retain **248 listed items from 38 branches
  in 38 prefectures**. Observations expire for use after 24 hours; retaining
  history does not make old prices or availability current.
- Local preview endpoints support paginated menus, category filtering and
  basket subtotal calculations. Phone confirmation and durable Wii Mail
  notices are implemented separately from native checkout.
- Offline checks exercise the native XML parser, menu-category consumer and
  menu model. These checks do not prove that the full menu UI renders.

**Native dish selection and checkout are unfinished.** Nine prefectures still
lack reviewed menu observations in the retained snapshot. Native item rows
also require size/variant details that have not been extracted. The current
integration does not submit orders or transfer a basket to Demae-can; final
item selection, options and charges must be confirmed on the provider site.

See the [Demae setup and current status](channels/demae/README.md),
[menu and basket progress](channels/demae/menu_basket.md), and
[native menu/item contracts](channels/demae/menu_contract.md).

## Online multiplayer compatibility

JWC24's planned setup will offer **Wiimmfi as the initial recommended provider**
for supported games, with **WiiLink WFC as an optional alternative**. This is a
planned integration: provider selection, game patching and multiplayer have not
been implemented or tested by JWC24. Compatibility must be checked for each
game and region. See the [online multiplayer integration plan](channels/online_play/README.md).

## Repository layout

- `channels/demae/` — Demae restoration status, source reviews and native contracts
- `jwc24/` — reusable WC24 transport, task, account, and server code
- `channels/hbnj/` — TV no Tomo manifest, service behavior, and documentation
- `tools/` — guide collection, native packing, validation, and inspection
- `.github/workflows/` — source and package checks

Private runtime material and generated data are deliberately excluded from
Git.

## Development notes

The project currently targets Dolphin and Python 3.11 or newer. The daily HBNJ
build is:

```powershell
py -3 tools\update_hbnj_daily.py
```

That command collects eight days for all regions into private staging,
validates the complete guide and native size ceilings, creates HDPK payloads,
independently parses them, and publishes only after every check passes. A
failed build leaves the previous live guide untouched.

The shared command-line tools can audit WC24 state, inspect the local account,
validate channel manifests, provision tasks, and run the replacement server:

```powershell
py -3 -m jwc24 audit --dl-list "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24dl.bin"
py -3 -m jwc24 account --config "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24msg.cfg"
py -3 -m jwc24 validate-manifest channels\hbnj\channel.json
py -3 -m jwc24 serve channels\hbnj\channel.json --nand-root "$env:APPDATA\Dolphin Emulator\Wii"
py -3 -m jwc24 mail-serve --data-dir private\mail
py -3 -m jwc24 launch --data-dir private\mail --dolphin "C:\path\to\Dolphin-JWC24-Mail.exe"
py -3 -m jwc24 mail-config --config "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24msg.cfg" --base-url http://127.0.0.1:8081 --data-dir private\mail
```

Local stock inputs can be identified and hashed without extracting or changing
them:

```powershell
py -3 tools\inventory_stock_titles.py --wads "Stock WADs" --nus-title "NusDownloader\titles\000300044B44474A\256"
```

Provisioning defaults to a dry run, creates timestamped backups when applied,
and refuses to overwrite unrelated occupied task slots. The original WAD is
always treated as immutable input.

`mail-config` is also dry-run by default. It creates or reuses a private local
account, reports every URL change, recalculates the WC24 config checksum, and
backs up `nwc24msg.cfg` before `--apply`. Private credentials and queued MIME
messages live under the ignored data directory.

`launch` is the normal day-to-day entry point. It reuses a healthy JWC24 mail
service when one is already running; otherwise it owns a temporary local server,
health-checks it before launching Dolphin, and shuts it down when Dolphin exits.

The server-side receive/delete protocol is implemented and independently
tested. Dolphin 2606 still skips WC24 download entries whose destination
filename is empty, so importing received mail into `wc24recv.mbx` requires a
Dolphin KD implementation patch; it does not require modifying a channel WAD.

## Project boundaries

The public repository intentionally excludes:

- WADs, tickets, TMDs, extracted content, and NAND files
- Wii identities, MAC addresses, WC24 keys, and emulator saves
- collected schedules and generated HDPK payloads
- TLS private keys, rollback snapshots, and reverse-engineering dumps

JWC24 is still early reverse-engineering software. I develop it against
separate Dolphin data with backups and keep all copyrighted or
machine-specific material outside the repository.
