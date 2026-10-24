# Retail v21 URL composition

Verified October 24, 2026 against the installed main DOL SHA-256
`aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898`.
This is a URL-builder contract, not a recovered complete startup sequence.

## Native execution

`tools.verify_wii_shop_url.verify` executes builder `0x8002BC10` and its actual
formatter `0x802BD290` in Unicorn without mocking either routine. Before entry,
the two base-string pointers are replaced with synthetic strings in emulated
RAM. No browser, network, NAND identity or account state is accessed.

The mode word at `0x80360728` selects the alternate base for values 2 and 8;
other tested values use the normal base. The installed normal pointer at
`0x8035F4F8` refers to the bare Shop host, while the alternate pointer at
`0x8035F4FC` refers to the previously identified manual-link template. These
addresses are static evidence; semantic names for all mode values are not
established by this test.

The function takes a suffix pointer in r3 and concatenates the selected base
and suffix using `%s%s`. It does not insert a slash or encode query text. The
formatter receives a 255-byte size argument, allowing 254 payload bytes plus
the terminator. The builder separately clears byte 255 and publishes the
256-byte buffer at `0x8036BF08` through pointer slot `0x803607D8`.

Synthetic cases cover normal/alternate modes, empty strings, exact-capacity
and oversized inputs, and preservation of an already encoded query suffix.
Output and pointer publication match independent expectations; guards on both
sides of the buffer remain intact. The harness rejects embedded NULs and
unbounded inputs before emulation. Native tests skip when private software is
absent; fingerprint mismatches are rejected.

## Static caller leads and remaining work

Direct call sites were found at `0x80023EBC`, `0x80023FBC`, `0x80024064` and
`0x80024078`. Some prepare title-ID strings before calling the builder; another
passes a caller-supplied string. Those observations do not establish the
ordinary Shop launch suffix or a complete browser navigation path.

The nine absolute `/startup` strings inspected earlier are manual-link
templates. The resource archive contains local support/error pages and browser
configuration, but its listed `opera.ini` does not supply a home URL. Therefore
neither those literals nor the builder alone prove the main storefront request.

Next is tracing the entry-mode selection, caller-provided suffix and consumer
of the published URL pointer, followed by a controlled runtime capture. No
network redirect, replacement page, TLS modification or channel patch is
implemented by this offline work. Derived disassembly remains private.
