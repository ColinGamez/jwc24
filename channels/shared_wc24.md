# Shared WC24 preparation and delivery

The read-only `jwc24 preflight` command checks one or more channel manifests
before starting a listener or changing a test profile. It checks payload
presence, slot/route/filename conflicts, a shared service origin, and optionally
the exact selected task table, WC24 account configuration and envelope-key
file presence/size. It never provisions tasks, registers an account, opens a
network connection or modifies a profile.

```powershell
.venv/Scripts/python.exe -m jwc24 preflight `
  channels/hbnj/channel.json channels/forecast/channel.json channels/wii_no_ma/channel.json `
  --base-url http://127.0.0.1:8080
```

`--base-url` changes the loaded manifests only in memory. The server's `serve`
command accepts the same option. It must be an HTTP(S) origin without a path,
credentials, query or fragment. Existing manifest files retain their original
values. Device registrations also retain their values: preflight reports a
task endpoint mismatch rather than silently changing them.

`--dl-list`, `--config` and `--nand-root` have no default profile. Use only the
explicitly authorized isolated test profile for this project. Output excludes
input paths, task URLs, console IDs, passwords and mail check IDs. Invalid
inputs produce fixed diagnostic codes. Missing optional inputs are reported
as `not_supplied`. Exit status is zero for passing supplied preparation checks,
one for reported preparation problems, or two for invalid command inputs.

Native registered tasks are matched by slot, owning title and filename. The
check also compares endpoint/type/signature flags. Created tasks require the
exact flags used by JWC24's provisioner. Server-encrypted tasks require the
established `0x0A` flag bits. Other flags in adopted native tasks are preserved
and remain opaque; `raw` may represent a prebuilt envelope, so the manifest
alone cannot establish its encryption semantics.

The shared server now selects `wc24pubk.mod` by each payload's owning manifest
title, removing the previous one-encrypted-channel restriction. Filename
aliases, assets and regional variants retain that ownership. File contents
are not read by preparation checks. Duplicate filenames and missing/wrong-size
keys fail instead of falling back to another title's key. Synthetic HTTP tests
decrypt two channels' responses with different fixture keys and confirm that
the other key does not recover the expected payload. No device key is used in
those tests.

`--max-payload-age-seconds` is an optional modification-time policy. It does
not parse internal validity fields. A passing preflight does not prove payload
schemas, trust on the installed client, scheduler readiness, individual task
success, delivery, VFF consumption, original rendering or mail display. Those
unverified boundaries are explicit in every report; project completion and
native readiness are never inferred from these checks.
