# Original v21 GetECConfig response execution

Verified October 25, 2026. `tools/verify_wii_shop_ec_config.py` executes the
fingerprinted original v21 common SOAP/XML reader, five-field extraction and
URL setters against synthetic bytes and RAM. **XML lookup and URL storage are
not mocked.** This establishes a bounded response contract; it does not connect
an account, contact a service or execute the request builder/full connection.

The [metadata-only report](../../research/wii_shop_ec_config_native_20261025.json)
records cases, status/count/size results, native slices and stub boundaries.
Original executable/data/disassembly remain private. The required original DOL
SHA-256 is `aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898`.

## Executed instructions and state

The harness calls common parser `0x8007DD20`. Original getOpeningTag
`0x8007E100`, getOptional `0x8007E420`, getSimple `0x8007E470`, getComplex
`0x8007E740`, string find/substr/copy and error-message entity decoding execute.
On common status zero, it runs `0x80088BFC..0x80088D8C` from the original
GetECConfig flow. The five original lookups and setters `0x800766D0` and
`0x80076810` execute. Execution stops before destruction and subsequent
registration/account/device-status work.

| Response field | Temporary output offset in synthetic frame | Stored offset in synthetic environment |
| --- | --- | --- |
| ContentPrefixURL | 0x20 | 0x34 |
| UncachedContentPrefixURL | 0x2C | 0x40 |
| EcsURL | 0x38 | 0x10 |
| IasURL | 0x44 | 0x1C |
| CasURL | 0x50 | 0x28 |

The synthetic environment starts empty. A timestamp fixture also executes the
native decimal conversion and stores its numeric value at environment 0x58/0x5C.
Its tick lookup is a stub; no real time/configuration/account state is read.

Stub boundaries are heap allocation/free (`0x8007C5E0`, `0x8007C710`,
`0x8007C5F0`), logging (`0x80078610`), tick lookup (`0x80073380`) and mutex
operations (`0x80073090`, `0x80073110`). Allocation uses a bounded synthetic
bump heap; logging does not emit original strings or fixture values. Error
record conversion/storage executes on a synthetic operation object, with only
its mutex callbacks intercepted. No XML search, substring, namespace comparison,
error-status decision, URL lookup or URL setter is replaced by fixture lookup.

## Observed contract and retail quirks

The verified normal form uses an XML declaration, literal `soapenv:Envelope`
and `soapenv:Body`, then unprefixed `GetECConfigResponse` with sole attribute
`xmlns="urn:ecs.wsapi.broadon.com"`. Optional TimeStamp precedes ErrorCode;
the five URL fields follow in the order above. The offline serializer emits
this form. Changed SOAP prefixes or an absent declaration returned **-4034**
in the tested fixtures. Missing ErrorCode also returned -4034.

**Namespace mismatch is a silent-zero error path, not successful validation.**
The harness observes the actual comparison at `0x8007DE98` and independently
checks the native expected text is exactly the ECS default-xmlns attribute.
A CAS namespace or single-quoted attribute compares false. The native branch
logs the mismatch without changing zero error state and skips TimeStamp,
ErrorCode and ErrorMessage extraction. Consequently a wrong-namespace fixture
can still reach URL extraction, with empty recorded ErrorCode, and install five
URLs even when its unread body contains a nonzero ErrorCode. This matches the
older source's mismatch branch; it must not be reproduced as a replacement
service feature or described as a validated response. Always emit the correct
ECS namespace and check the comparison separately when reviewing harness output.

On the correct namespace path:

- ErrorCode `0` permits URL extraction. A nonempty ErrorMessage remains
  informational: native entity decoding executes and common status stays zero.
  This **differs from the recovered older source's OR-message error rule**.
- ErrorCode `42`, `00` and `000` return **-4015**, with no URL lookup or store.
  The zero decision is lexical, not a generic numeric comparison.
- ErrorCode zero plus an informational message and no URL fields passes common
  parsing, then fails first-field extraction with **-4006**.
- Missing any required URL stops at that field with -4006. Earlier temporary
  strings remain decoded, but neither environment URL setter runs. Reordering
  CasURL before the other fields similarly fails its later sequential lookup.
- No response Version field is requested. A synthetic Version value before
  ErrorCode is ignored in the tested response. This verifies no request-side
  version contract: request construction and its Version 2.0 initialization
  remain outside the executed scope.

URL values are **raw substrings**. A literal `&amp;` remains `&amp;` through both
native extraction and environment assignment. ErrorMessage entity decoding is
a separate path and does not apply to URLs. The original setters accepted an
empty value and a 1,034-character non-URI unchanged in the tested fixtures.
Those results do not establish a global URL-size limit. HTTP(S)-only, canonical
status and raw-ampersand restrictions in the replacement codec are local fixture
policy, not native URL validation or automatic encoding behavior.

## Containment, API and validation

`verify_ec_config_response(source: bytes, response: bytes)` requires the exact
original executable and a nonempty synthetic response of at most 16 KiB without
NUL. It returns status/common_status, timestamp/error strings, urls,
extracted_urls, field attempts, namespace comparison and verification metadata.
**Returned strings echo synthetic input and are not a redacted real-capture API.**
Public reports retain sizes/counts/booleans rather than those strings.

The harness maps emulated MEM1 only. Fixed native instruction ranges and a
two-million-instruction limit per phase reject escapes or non-returning runs.
Writes are confined to synthetic objects, stack, heap and a native numeric
conversion errno slot in emulated RAM. Soap/environment/operation objects and
every allocation have checked guards. Long-string pointers must lie within
synthetic allocations; inline payloads plus terminators must fit their 12-byte
synthetic string objects. No corrupted string pointer can export original DOL
contents through the response API.

Thirteen focused native tests and six separately owned codec interoperability
tests pass (19 together). Cases cover correct common/XML/five-field stores,
timestamps, reported and informational messages, missing/reordered fields,
namespace/status quirks, raw entities, long/empty values, guards and input bounds.

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m unittest tests.test_wii_shop_ec_config_native tests.test_wii_shop_ec_config_interop -v
```

Full request construction, HTTP/TLS, origin access, real allocator/threading,
live service policy, account/device authentication, entitlement and complete
connection behavior remain unverified. No routes, runtime module, NAND data,
credentials, tickets or keys were changed or accessed by this harness.
