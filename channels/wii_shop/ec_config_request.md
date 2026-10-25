# Original v21 GetECConfig request construction

Verified October 25, 2026. `tools/verify_wii_shop_ec_config_request.py` executes
the original inline Soap constructor, common XML builder, ECVersion element,
closing XML and header construction with synthetic RAM/state. The native default
**Version 2.0** now has execution evidence. Transport is intercepted before
`getWsResponse`; no HTTP method, TLS exchange, authentication or connection is
claimed. Existing runtime adapters and account state are unchanged.

The [metadata report](../../research/wii_shop_ec_config_request_native_20261025.json)
records native slice hashes, five canonical cases, field order/lengths, build
metadata and stub counts. It contains no identity values or generated wire.
Original files and derived disassembly stay private. The original DOL must match
SHA-256 `aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898`.

## Executed scope and substitutions

Execution begins at `0x80088968`, inside the established GetECConfig flow,
using a synthetic caller frame and environment wrapper. It executes the original
inline constructor/default pointers, `Soap::start` at `0x8007C950`, ECVersion
addition and `Soap::end`. Formatting, XML escaping, strings, stream insertion
and header-container helpers execute unchanged. The completed caller invokes
`getResp` at `0x8007DAB0`; the harness stops at its call to the service-response
wrapper **`0x800A74A0`**, before that wrapper executes.

The default Version pointer is observed after the original constructor writes
it: Soap offset 0x8C points to original constant `2.0` at `0x8031F5CC`. It is
never seeded from the older recovered source or from a fixture. This does not
execute the entire public EC_Connect entry or its prerequisites.

Original product-version global `0x80322658` points to `0x803225E0`, containing
build metadata `ECSHOP 4.8.0 Jul 27 2012 16:52:03`. The common message-ID prefix
global `0x80322654` points to `ECSHOP`. The harness verifies the original product
pointer/value, then explicitly substitutes synthetic product/prefix pointers
**in emulated RAM**. ECVersion consumes that substituted global through the
original native instruction; it is not an original caller parameter/API.
The embedded initial service URL is likewise replaced in emulated RAM with a
synthetic `.invalid` endpoint before the native environment assignment runs.
No actual endpoint is contacted or emitted in a generated request.

## Verified wire and headers

The native common request uses SOAP 1.1 with literal `SOAP-ENV:Envelope/Body`,
`xmlns:ecs="urn:ecs.wsapi.broadon.com"`, operation `ecs:GetECConfig` and
`xsi:type="ecs:GetECConfigRequestType"`. The base field order is:

`Version`, `MessageId`, `Region`, `Country`, `Language`, `SerialNo`, `ECVersion`.

The common Version is `2.0`; ECVersion is the separate product-version string.
Native message-ID composition includes the substituted prefix, the synthetic
device-ID string and a stubbed tick value, even if DeviceId is omitted as an XML
field. No real identity or clock state is read.

| Field / structure | Observed native condition and position |
| --- | --- |
| DeviceId | After MessageId when synthetic environment flag 0x1A8 is true |
| DeviceToken | After DeviceId when raw-token slot 0xCC is nonempty; default GetECConfig reads the weak-prefixed slot 0xF0 |
| AccountId | After DeviceToken when its slot is nonempty |
| ApplicationId, TIN | Before Region, each conditional on its own nonempty string |
| Region, Country, Language | Always emitted, including empty values in tested fixtures |
| Attributes/Name/Value | Single optional postal structure after Language and before SerialNo; details below |
| SerialNo | Always emitted for ECS, including an empty value |
| ECVersion | Added by the GetECConfig caller after the common fields, including an empty product string |

The original GetECConfig constructor initializes the strong-token flag false.
Supplying different synthetic strong/weak-prefixed strings proves the weak slot
is selected; an empty raw-token trigger omits DeviceToken even with a nonempty
prefixed slot. This does not verify token generation, validity, prefix creation
or any key-pair confirmation. The alternate strong-token branch is not forced.
No Age is emitted by this ECS request.

The native header container contains exactly these four entries in tested cases:

| Name | Value |
| --- | --- |
| Accept | application/xml |
| Accept-Charset | UTF-8 |
| Content-type | text/xml; charset=utf-8 |
| SOAPAction | urn:ecs.wsapi.broadon.com/GetECConfig |

The vector SOAPAction value is unquoted; the separate native header-text stream
contains `SOAPAction: "urn:ecs.wsapi.broadon.com/GetECConfig"` followed by CRLF.
Header/body production and the wrapper call are verified. Actual HTTP POST,
TLS/origin handling, signing or transmission are outside this boundary.

## Retail postal attribute and escaping distinction

At `0x8007CD80`, the original common builder checks environment string 0x260.
When empty, no Attributes element appears. A nonempty synthetic value produces
exactly one ECS-namespaced structure in this order:

```xml
<ecs:Attributes>
  <ecs:Name>PostalCode</ecs:Name>
  <ecs:Value><!-- caller's opaque synthetic scalar --></ecs:Value>
</ecs:Attributes>
```

This diagram identifies the native element names and nesting; the XML comment
is explanatory and is not emitted by the native builder. It is not a generic
license to invent other attribute names, repeat the structure, obtain a user's
address or infer account location. Postal input remains an opaque private
optional field in the independently tested replacement request parser.

The common fields, including this postal value, use **raw stream insertion**.
A synthetic ampersand remains raw and yields non-well-formed XML. In contrast,
ECVersion goes through the native addElement escape helper, which converts
ampersand and angle brackets into XML entities. The harness preserves this
distinction; it does not silently repair the original wire or assume every
synthetic string is valid native XML.

## API, containment and validation

`verify_ec_config_request(source, *, environment=SyntheticRequestEnvironment(),
product_version='...')` returns `request_bytes`, `soap_action`, header entries/
text, the synthetic handoff endpoint and explicit execution/stub metadata.
The environment carries only caller-provided synthetic strings and a synthetic
key-pair flag; it loads no console/account files. Private identity-shaped fields
are excluded from its repr. API outputs echo fixtures and must not be treated
as redacted real-capture logs.

Every input string is limited to 96 UTF-8 bytes; NULs, invalid surrogate text,
wrong field types and non-boolean flags fail before emulation. Synthetic heap
capacity is 4 MiB with allocation guards; object/string pointers, inline capacity
and output lengths are checked. Native writes are confined to synthetic RAM and
the native 128-byte message scratch buffer in emulated RAM. Environment/wrapper
guards cover the entire run; Soap guards are established after constructor
temporaries finish using its preceding bytes. All guards are checked at exit.
Fixed native execution ranges and a three-million-instruction limit reject
unreviewed paths. Floating-point capability is enabled only in emulated MSR so
original formatter/memory-copy helpers can execute.

Explicit stubs are heap allocation/free, logging, a synthetic tick lookup and
environment unlock. The service-response wrapper is a stop boundary, not a fake
successful network response. No XML construction/formatting, ECVersion addition,
header construction or default-version setup is mocked.

Ten focused native tests pass: constructor/version/header shape, message-ID
composition, postal nesting/order, optional fields/token selection, empty values,
native escaping differences, repr privacy and bounds. Parent-owned tests feed
the resulting actual native wire to the independent request parser.

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m unittest tests.test_wii_shop_ec_config_request_native -v
```

Device registration, key/signature generation, account authentication, full
connection, HTTP/TLS transmission and native browsing remain unfinished work.
No actual keys, tickets, credentials, account state or NAND were read or changed;
no browser, Dolphin or network operation occurred.
