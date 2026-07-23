# JWC24

JWC24 is an experimental, reusable replacement-service toolkit for Japanese
WiiConnect24 channels running under Dolphin. It preserves original channel
WADs and works with Dolphin's native WC24 scheduler, per-channel download
tasks, and VFF storage.

The platform is deliberately split into two layers:

- `jwc24/` implements shared WC24 task parsing, provisioning, validation, and
  HTTP payload delivery.
- `channels/` contains one manifest per revived channel. Channel-specific
  binary generators and CGI handlers can be added beside each manifest.

TV no Tomo (`HBNJ`, title ID `0001000148424e4a`) is the first working adapter,
not a special case in the WC24 core. The current proof of concept reaches the
native program-guide UI with modern Japanese listings.

## Current status

- Clean Japanese v512 HBNJ WAD boots without binary patches.
- Native `header.bin`, `epg.bin`, and `str.bin` WC24 delivery works.
- WC24 AES-OFB envelopes and Nintendo LZ10 payloads are generated locally.
- All 54 Japanese broadcast areas and 376 terrestrial services are collected.
- Daily collection, validation, native packing, and atomic publishing work.
- TV no Tomo CGI compatibility includes the known native `X-RESULT` contracts.

Still experimental: genre/detail metadata, region-specific EPG packages,
multi-day rollover, automatic server installation, popularity synchronization,
Wii Mail, and adapters for additional 4.3J channels.

## Repository policy

This repository contains source code and documentation only. It deliberately
does **not** contain:

- WADs, tickets, TMDs, extracted channel content, or NAND files
- Wii identities, MAC addresses, WC24 keys, or emulator saves
- downloaded/generated schedules or HDPK payloads
- local TLS private keys, rollback snapshots, or reverse-engineering dumps

You must provide your own legally obtained channel and Dolphin NAND.

## Safety model

- Provisioning is a dry run unless `--apply` is supplied.
- Every applied edit creates a timestamped backup beside `nwc24dl.bin`.
- Occupied task slots are never overwritten unless they already belong to the
  same manifest and use the expected filename.
- Dolphin must be closed before applying a manifest.
- The original WAD is treated as immutable input.

The `account --bootstrap-local` operation promotes an already generated WC24
identity to the registered state for a local replacement service. It does not
contact Nintendo, WiiLink, or another third party, and it refuses NANDs that
have never generated a WC24 ID.

## Commands

```powershell
py -3 -m jwc24 audit --dl-list "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24dl.bin"
py -3 -m jwc24 account --config "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24msg.cfg"
py -3 -m jwc24 validate-manifest channels\hbnj\channel.json
py -3 -m jwc24 provision channels\hbnj\channel.json --dl-list "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24dl.bin"
py -3 -m jwc24 serve channels\hbnj\channel.json --nand-root "$env:APPDATA\Dolphin Emulator\Wii"
```

## Build today's HBNJ guide

Python 3.11 or newer is recommended.

```powershell
py -3 tools\update_hbnj_daily.py
```

This performs four gates before publishing anything:

1. strict collection for all 54 areas;
2. schema/reference/time-window validation;
3. native UTF-16BE HDPK packing;
4. independent binary parsing and cross-file validation.

Only a fully valid build is atomically published to
`channels/hbnj/generated/current`. A failed update leaves the previous guide
untouched.

## Run the service

Validate and provision manifests with Dolphin closed:

```powershell
py -3 -m jwc24 validate-manifest channels\hbnj\bootstrap.json
py -3 -m jwc24 validate-manifest channels\hbnj\channel.json
py -3 -m jwc24 provision channels\hbnj\channel.json `
  --dl-list "$env:APPDATA\Dolphin Emulator\Wii\shared2\wc24\nwc24dl.bin"
```

Provisioning is a dry run unless `--apply` is supplied.

Start HTTP delivery after generating payloads:

```powershell
py -3 -m jwc24 serve channels\hbnj\channel.json `
  --nand-root "$env:APPDATA\Dolphin Emulator\Wii" --port 80
```

Local HTTPS CGI testing additionally requires a private development
certificate; do not commit it.

## Architecture

```text
clean 4.3J NAND
      |
      v
manifest-driven task provisioner --> Dolphin IOS /dev/net/kd/request
                                          |
                                          v
                                  replacement HTTP service
                                          |
                                          v
                           channel adapter / payload generator
```

Each future channel gets its own manifest, payload generator, validators, and
optional CGI adapter while sharing the WC24 transport and safety machinery.

## Warning

JWC24 is early reverse-engineering software. Keep NAND backups, test in a
separate Dolphin user directory, and never provision task tables while Dolphin
is running.
