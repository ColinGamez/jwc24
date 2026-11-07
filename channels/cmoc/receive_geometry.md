# Configured receive storage and rounded input

`jwc24.cmoc_receive` composes the existing request-setup projection with the
original embedded storage boundary. It checks an explicit resolved `+0xC8`
span, retained wire-prefix length, advertised capacity and actual supplied
backing extent. It does not load resources, configure cryptography, receive
SDK data, change the client or publish a response.

## Original storage and arithmetic

The pinned Japanese HAPJ v512 executable has separate size-prefixed buffers:

| Worker field | Payload start | Payload bytes |
| --- | --- | --- |
| Wire input `+0x294` | `+0x298` | `0x440` |
| Intermediate `+0x6D8` | `+0x6DC` | `0x400` |
| Decoded output `+0xADC` | `+0xAE0` | `0x30000` (separate raw path) |

The complete original reset functions `0x8007F3C0` and `0x8007F3A8` execute with
their original memory-fill helper. Synthetic sentinel bytes before and after
each entire field establish the exact wire/intermediate clear spans; the
neighboring field is preserved. No original reset or fill helper is stubbed.
The decoded buffer is outside the scope of this new reset comparison.

The configured constructor fragment `0x8007F1B4..0x8007F1F4` passes a wire
pointer and capacity to the SDK:

```text
input offset = resolved +0xC8 word + retained wire-prefix length
advertised capacity = input offset + 0x400
```

It contains no check that this capacity fits the `0x440`-byte wire storage.
Consequently, a locally accepted configuration must have a combined offset
at most `0x40`. This conclusion follows from the actual embedded layout, not
from guessing a key or digest length. The earlier setup API still projects
the original arithmetic, including capacities outside that storage; this new
composition check rejects them rather than silently changing that projection.

For all 4,225 combinations of the existing locally supported 0..64 resolved
span and 0..64 retained prefix, the original fragment agrees with the projected
capacity: 2,145 fit and 2,080 exceed storage. These are synthetic combinations;
this is **not** evidence that genuine loaded resources use an excessive size,
or that every combination can arise in a real request.

## Rounded transform backing

The original body fragment `0x8007F49C..0x8007F4D8` subtracts that input offset
from the descriptor's received endpoint and rounds the result upward to a
multiple of 16. The configured callback then supplies that rounded size to
hash/cipher processing. Later callbacks reuse the input offset with a `0x400`
descriptor capacity. SDK delivery/chunking and initialization guarantees remain
unproved; a partial final block may read beyond the received endpoint.

`check_transform_extent` requires that every rounded byte already exists in
explicit initialized backing, and that the endpoint fits the checked capacity.
It never appends zeros, guesses cipher padding or treats unread input as
available. An endpoint before the input offset rejects. Actual native arithmetic
on synthetic partial-header endpoints can produce zero or a large unsigned
rounded count; neither outcome establishes a valid received block.

The native comparison covers 29,575 ordinary rounding cases and 16,490
partial-header cases. No hash/cipher/decompressor/SDK boundary is executed by
this verifier. Public tests compose each endpoint from 0 through 1,024 payload
bytes with the existing callback projection under five boundary layouts.

## Verification and remaining requirements

```powershell
.venv/Scripts/python.exe -m unittest tests.test_cmoc_receive
```

Five tests pass with the private original and optional native dependencies
available. The native class skips explicitly without them. The verifier pins
the unchanged original executable, bounds control flow/instructions and
reads/writes, verifies immutable arithmetic inputs and object/stack guards,
and returns only counts and geometry. No original resource or secret is read.

Real resource sizes, hash/cipher setup and final comparison semantics, SDK
chunking/partial-delivery guarantees, complete decoded-output bounds, response
lifetime, trust and authenticated original channel flows remain separate gates.
A successful geometry check proves none of them and does not activate a service.
