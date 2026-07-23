# HBNJ adapter

This adapter targets the untouched Japanese v512 TV no Tomo WAD with title ID
`0001000148424e4a` (`HBNJ`).

On first-run, HBNJ natively creates a 4 MiB `wc24dl.vff`, `wc24pubk.mod`, and a
`header.bin` download task in slot 10. The adapter adopts that native slot and
redirects it to the replacement service. EPG and string payload fixtures remain
available to the adapter, but they are not provisioned as speculative tasks;
their native registration sequence must be observed first.

`prune_duplicate_tasks` removes only same-title, same-filename duplicates when
the manifest adopts a task at a different canonical slot. This migrates the
early experimental header task in slot 110 without touching unrelated WC24
entries.

The header task uses `mode: adopt`: its native task type, group ID, title
metadata, and scheduler record are preserved. Only its URL, payload-security
flags, error state, and due time are changed. Tasks created by the platform use
the Dolphin channel-content type (`3`) and key scheduler records by the low
title code (`HBNJ`).

The active header fixture is rebuilt by `tools/pack_hbnj_guide.py`. Native
downloaded display strings are null-terminated UTF-16BE; the retired Shift-JIS
fixtures are retained only as reverse-engineering evidence and must not be
served.

`tools/update_hbnj_daily.py` performs the complete national collection,
schema audit, native packing, and independent binary audit in a private staging
directory. It atomically publishes to `generated/current` only after every
stage succeeds, so a failed upstream collection leaves the previous guide live.
It also builds and validates one EPG per native area ID under
`generated/current/areas/<id>`. Requests such as `/1016/epg.bin` resolve to the
matching regional payload, with the national package retained as a fallback.

The task layout is based on confirmed reverse engineering from the retired
workspace. It is not considered production-compatible until a clean WAD launch
requests these slots and imports all three payloads without a scene bypass.

Channel-specific CGI endpoints (`activate.cgi`, `query.cgi`, `popularity.cgi`,
and `/bin*`) are served by the adapter with the native `X-RESULT` success
contracts. The production app reaches those endpoints through
`tvepgp.wapp.wii.com` over legacy TLS 1.0/1.1, so local testing uses a separate
port 443 listener and a private development certificate. Dolphin certificate
verification must be disabled only for this local development environment; the
original setting is backed up before that change.
