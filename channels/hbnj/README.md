# HBNJ adapter

This adapter targets the untouched Japanese v512 TV no Tomo WAD with title ID
`0001000148424e4a` (`HBNJ`).

On first-run, HBNJ natively creates a 4 MiB `wc24dl.vff`, `wc24pubk.mod`, and a
`header.bin` download task in slot 10. After setup, the channel replaces that
bootstrap entry with native `epg.bin` and `str.bin` tasks in slots 10 and 11.
The two manifests model those observed phases separately, and the adapter
adopts the channel-created records instead of inventing speculative tasks.
The active adapter adds a JWC24-managed daily `header.bin` refresh in free slot
12. This keeps station, area, and genre metadata current after first-run setup
without replacing either native guide task.

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
It collects the channel's full eight-day date window, builds and validates one
EPG/string pair per native area ID under
`generated/current/areas/<id>`. Requests such as `/1016/epg.bin` resolve to the
matching regional payload. Unknown numeric area IDs fail closed instead of
receiving the oversized national package. Each regional pair is checked against
the Nintendo LZ10 24-bit limit and the channel's 4 MiB VFF capacity before
publication.
The collector also maps Bangumi's CSS genre categories to TV no Tomo's
one-based ARIB genre IDs. The native header contains the 12 Japanese labels
used by the original genre-search screen. Program descriptions are preserved
in the private guide JSON and packed into the first text pointer of each native
`str.bin` record. Every EPG detail record carries a validated one-based index
into that table; the optional second text pointer remains empty.

The task layout and binary structures are based on confirmed reverse
engineering and clean-WAD observation. A clean v512 WAD has imported all three
payload types through the original WC24 path without a scene bypass.

Channel-specific CGI endpoints (`activate.cgi`, `query.cgi`, `popularity.cgi`,
and `/bin*`) are served by the adapter with the native `X-RESULT` success
contracts. The production app reaches those endpoints through
`tvepgp.wapp.wii.com` over legacy TLS 1.0/1.1, so local testing uses a separate
port 443 listener and a private development certificate. Dolphin certificate
verification must be disabled only for this local development environment; the
original setting is backed up before that change.
