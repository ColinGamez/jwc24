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

## What I have working

- The original HBNJ WAD runs without channel binary patches.
- Dolphin's WC24 scheduler downloads native `header.bin`, `epg.bin`, and
  `str.bin` files from JWC24.
- JWC24 produces the channel's original WC24 AES-OFB envelope, Nintendo LZ10
  compression, and HDPK data structures.
- The guide covers all 54 Japanese broadcast areas and 376 terrestrial
  services.
- Area-coded requests receive compact regional payloads; Gunma currently has
  11 stations and 397 programs.
- Current titles, times, genres, and Japanese program descriptions are packed
  into their native TV no Tomo records.
- The original activation, query, popularity, and synchronization CGI calls
  receive the response contracts expected by the channel.
- A daily job collects, validates, packs, independently checks, and atomically
  publishes a new guide.

## Why it is more than a TV no Tomo patch

The shared code in `jwc24/` handles WC24 task inspection, safe provisioning,
payload delivery, encryption, compression, and validation. TV no Tomo lives in
`channels/hbnj/` as the first channel-specific adapter.

That split is intentional: future 4.3J channels can have their own manifest,
data generator, validators, and CGI behavior while reusing the same WC24
transport. Wii Mail support is also planned because it is part of the wider
WC24 experience.

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

TV no Tomo has reached its real program-guide UI with current listings. The
latest build validated:

- 54 broadcast areas
- 376 stations
- 14,871 programs
- 12,897 program descriptions
- every header-to-EPG station key
- every EPG-to-string record index
- every regional native payload

The next work is focused on in-app polish, multi-day guide rollover,
popularity synchronization, easier local server setup, Wii Mail, and adapters
for more Japanese WC24 channels.

## Repository layout

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

That command collects all regions into private staging, validates the complete
guide, creates native HDPK payloads, independently parses them, and publishes
only after every check passes. A failed build leaves the previous live guide
untouched.

The shared command-line tools can audit WC24 state, inspect the local account,
validate channel manifests, provision tasks, and run the replacement server:

```powershell
py -3 -m jwc24 audit --dl-list "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24dl.bin"
py -3 -m jwc24 account --config "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24msg.cfg"
py -3 -m jwc24 validate-manifest channels\hbnj\channel.json
py -3 -m jwc24 serve channels\hbnj\channel.json --nand-root "$env:APPDATA\Dolphin Emulator\Wii"
```

Provisioning defaults to a dry run, creates timestamped backups when applied,
and refuses to overwrite unrelated occupied task slots. The original WAD is
always treated as immutable input.

## Project boundaries

The public repository intentionally excludes:

- WADs, tickets, TMDs, extracted content, and NAND files
- Wii identities, MAC addresses, WC24 keys, and emulator saves
- collected schedules and generated HDPK payloads
- TLS private keys, rollback snapshots, and reverse-engineering dumps

JWC24 is still early reverse-engineering software. I develop it against
separate Dolphin data with backups and keep all copyrighted or
machine-specific material outside the repository.
