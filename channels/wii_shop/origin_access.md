# Retail v21 origin admission and page-trust predicates

Verified October 25, 2026 using the fingerprinted original main executable,
SHA-256 `aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898`.
The [metadata report](../../research/wii_shop_origin_validation_20261025.json)
records 22 synthetic cases and the checked older-source inventory. Original
code/data and source bodies remain private. This does not verify a Nintendo
signature or reconstruct the browser's complete security policy.

The [native harness](../../tools/verify_wii_shop_origin.py) executes the original
origin callback at `0x80091150`, its hostname predicate at `0x800A6D90`, the
inlined page-trust scan, and native strlen/strcmp. Logging and the current-URL
getter are explicit synthetic stubs. The native test-mode override is always
OFF; the harness exposes no option to enable it or patch an origin decision.

## The boundary receives separate browser fields

`verify_origin_access(source, *, protocol, hostname, port, current_url,
callback_present=True)` accepts bounded synthetic **preparsed** protocol,
hostname and port fields. The separate current-URL callback returns synthetic
raw bytes or NULL. The harness does not parse any of those fields from a URL.

Some tests deliberately provide inconsistent fields to establish this boundary.
Those combinations are not evidence that a real browser would produce them,
canonicalize URLs the same way, or permit an origin bypass. The results contain
only flags, counts and guard metadata; they never echo supplied hostnames or
URLs.

## Executed retail behavior

| Native result | Verified condition and limit |
| --- | --- |
| Admission flag / callback return | Hostname has the exact case-sensitive suffix `.shop.wii.com` and is shorter than 256 bytes |
| HTTPS flag | Protocol field equals the exact lowercase string `https` |
| Trusted-page flag | Independent raw current-URL callback string has no literal `/ext/` starting at indices 0 through 126 |

The suffix is read through the original table at `0x8032F538`, which points to
the standalone original string at `0x8032F528`. The hostname predicate performs
a bounded 256-byte scan and compares the suffix using native strcmp. A
255-byte synthetic hostname with the suffix is admitted; a 256-byte hostname
is rejected. The leading dot matters: bare `shop.wii.com` is rejected. A
case-changed suffix, trailing dot or appended other domain is also rejected by
this raw predicate. These are string-predicate results, not DNS validation or
browser hostname-normalization findings.

Protocol and port are not admission conditions in this hostname predicate.
Changing the supplied protocol from HTTPS to HTTP or another string preserves
the hostname admission result, while clearing the HTTPS flag unless the field
is exactly lowercase `https`. Different synthetic port integers likewise
preserve admission. This does **not** establish permission to invoke a commerce
method over those protocols: the HTTPS/trust flags, plugin state, individual
method restrictions and later account checks are separate boundaries.

The trusted-page scan examines the raw full callback string, rather than
parsing its path. A literal `/ext/` in a query or fragment clears trust too.
Case-changed `/EXT/` and percent-encoded text are not decoded by this scan.
It checks marker start indices 0–126; a marker starting at 126 is found even
though its lookahead extends beyond 126, whereas one starting at 127 is not.
This is not a claim about what raw encoding the real browser URL getter returns.

An absent current-URL callback and a callback returning NULL are separate
executed cases. Both leave this native trust flag true, while hostname
admission and the HTTPS flag retain their independent results. This observation
does not prove those missing-callback states occur in a real initialized client
or grant global/method permissions.

## Older source is a lead, not a replacement for retail execution

The audit verifies these older files against the private extraction inventory:

- `common/lib/ec/ec_chkDownload_bw.cpp:187-218` supplies the hostname-suffix
  predicate lead and its 256-byte hostname bound.
- `common/lib/ec/ec_js.cpp:926-1015` supplies the callback/trust/HTTPS lead.
  The retail function contains the corresponding native decisions.
- `common/lib/ec/include/ecxtypes.h:24` defines the older EC_MAX_URL_LEN as 255.
  The older trust loop uses that value; retail v21 instead checks marker start
  indices below 127. The old constant must not substitute for this observed
  retail boundary.

The older `ec_js.cpp:958-983` also defines method/global restrictions, and its
global getter requires both admission and an initialized EC object before its
per-global trust gate. Those are separate source findings. This harness does
not run a global/property getter, create a JavaScript object or invoke a commerce
method, and does not claim a complete retail method-permission table.

The existing loopback preview constructing Shop/Sound objects therefore does not
establish native ECommerceInterface access. The original suffix predicate rejects
the synthetic preparsed hostname `127.0.0.1`; this audit introduces no host
override, protection patch, DNS change, certificate change or bypass.

## Containment and validation

The entire original executable fingerprint must match before emulation. Only
the identified predicate, string-helper and register-save/restore ranges may
execute. Unexpected native control flow or writes fail closed. The only writable
native state is the three output-flag bytes and a bounded synthetic stack.
Synthetic callback/test-mode pointers, input bytes and stack/state guards are
checked after execution. No native origin predicate or string helper is stubbed.

The harness caps each supplied string at 1,024 bytes and execution at 100,000
instructions. These are local containment limits, separate from the observed
native hostname and trusted-scan limits. The recorded cases used at most 2,352
instructions. Instruction-budget exhaustion and invalid string/type inputs are
explicit regression cases.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_shop_origin -v
```

Thirteen tests pass. The existing private source helper supplies only the
selected original executable; no full NAND, owner credentials, tickets, browser,
network, Dolphin, account state or full startup is used. No original file,
runtime module, live service or owner backup is changed by this work.
