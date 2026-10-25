# Offline ECS GetECConfig codec

Reviewed October 25, 2026. `jwc24.wii_shop_ec_config` implements an offline,
bounded older-source request parser and explicit response-fixture serializer
targeting the verified retail-v21 response behavior. It does not
contact a service, select default endpoints, expose a server route, authenticate
a device, register an account or mark a connection successful.

The [validation report](../../research/wii_shop_ec_config_validation_20261025.json)
records three older client-library files checked against their private extraction
inventory. Those checks establish extraction consistency, not independent
Nintendo provenance or a complete retail-v21 match. Original source bodies
remain private. The [retail commerce audit](commerce_surface.md) corroborates
the action, ECVersion and five URL-field family; its static references alone do
not establish every request/common-response detail. Separate execution of the
fingerprinted retail common parser and configuration extractor against synthetic
XML supplies the response-status correction described below.

## Source-backed request subset

`ec_connect.cpp:59-63` constructs ECS `GetECConfig`, starts the common request,
adds `ECVersion` from `productVersion`, and ends the request. The service is ECS:
`urn:ecs.wsapi.broadon.com`, with SOAPAction
`urn:ecs.wsapi.broadon.com/GetECConfig`. It is not a CAS operation.

The common builder in `ec_soap.cpp:25-139` emits SOAP 1.1 and an ECS operation
with `xsi:type="ecs:GetECConfigRequestType"`. The constructor in
`ec_soap.h:219-239` sets protocol `Version` to `2.0`; this parser's version
restriction is based on that older source and is not a retail request-builder
claim. `ECVersion` is a separate opaque product-version string, not an inferred
protocol number or a default value supplied by JWC24.

| Fields | Codec behavior |
| --- | --- |
| Version, MessageId, Region, Country, Language, SerialNo | Structurally required common fields |
| DeviceId, DeviceToken, AccountId, ApplicationId, TIN | Optional opaque common fields; never authenticated |
| ECVersion | Required explicit nonblank string |
| Age | Rejected: the reviewed common builder emits it for CAS, not ECS |

`parse_get_ec_config_request(data, *, soap_action)` returns
`GetECConfigRequest(ec_version, common_fields)`. Both attributes are excluded
from repr. Callers must keep the returned raw fields private. A structurally
present empty SerialNo remains empty and establishes no identity.

Namespace prefixes may vary; quoted and unquoted exact SOAPAction are accepted.
An absent xsi:type is accepted by expanded-operation dispatch; a supplied type
must resolve to the ECS request type. Unknown fields, duplicate fields, wrong
namespaces/types/actions, multiple operations, SOAP headers, nested scalar
fields and mixed text are rejected. These are this component's boundaries,
not a recovered complete WSDL or acceptance promise for all native requests.

## Explicit response fixtures

`serialize_get_ec_config_response` requires explicit `urls`, `error_code` and
`status_source_ref`. Optional `timestamp` and `error_message` have no generated
values. Each successful fixture URL is an `EvidencedURL(value, source_ref)`;
both attributes are omitted from repr. References are caller assertions, not
independently validated provenance, and are never serialized.

The serializer uses lexical forms corroborated by the retail common parser:
XML declaration, `soapenv:Envelope`, `soapenv:Body`, and unprefixed
`GetECConfigResponse` with the sole default ECS xmlns attribute. It emits
optional TimeStamp, required ErrorCode, then optional ErrorMessage. It never
echoes MessageId, SerialNo, DeviceId, tokens or account values.

**The retail reader differs materially from the older source.** The old common
reader (`ec_soap.cpp:294-345`) treats a code different from the exact string `0`,
or a nonempty decoded ErrorMessage, as a reported error. Executing the retail-v21
common parser instead establishes that literal `0` with a nonempty ErrorMessage
returns common status zero and entity-decodes the informational message. With
all five URLs present, native extraction and URL installation succeed. Without
them, common parsing succeeds but field extraction returns `-4006`.

The response serializer follows that **verified retail** distinction. A code
different from literal `0` is a reported-error fixture and requires `urls=None`.
A literal zero requires all five explicit URLs whether ErrorMessage is absent,
empty or nonempty. Codes `00` and `000` yield native reported-error status
`-4015`; the codec's narrower canonical-status policy rejects those spellings.
The five fields retain the corroborated extraction order
(`ec_connect.cpp:73-89`):

1. ContentPrefixURL
2. UncachedContentPrefixURL
3. EcsURL
4. IasURL
5. CasURL

No URL is inferred from a catalog, device, historical server, environment
variable or an absent mapping key. A zero-status XML fixture represents only
that fixture's service-config data; it grants no connected/account state.

```python
from jwc24.wii_shop_ec_config import (
    URL_FIELDS, EvidencedURL, serialize_get_ec_config_response,
)

# Invented offline endpoints, not historical or operational service defaults.
synthetic_urls = {
    name: EvidencedURL("https://" + name.lower() + ".invalid/synthetic",
                      "synthetic:" + name)
    for name in URL_FIELDS
}
xml = serialize_get_ec_config_response(
    urls=synthetic_urls, error_code="0", status_source_ref="synthetic:status"
)
```

## Lexical URL handling and local containment

The older `getSimple` implementation (`ec_soap.cpp:467-502`) takes a raw XML
substring without XML-unescaping. GetECConfig forwards those strings to the
environment. XML-escaping a raw ampersand would therefore configure a different
string containing `&amp;`. This codec rejects raw ampersands in fixture URLs.
If a source actually supports a percent-encoded form, the caller must provide
that evidenced form explicitly; the serializer never silently rewrites URLs.
ErrorMessage is different: its source reader explicitly XML-unescapes it.

The following are **new JWC24 policies**, not recovered native limits or URL
validation rules:

- Input/output XML is at most 64 KiB. Input is strict UTF-8; DTD/entity
  declarations are rejected before parsing.
- Scalars have at most 4,096 characters; input has at most 64 elements, depth
  four and 32 namespace declarations.
- Fixture error status uses canonical nonnegative decimal uint32 notation.
  Leading zeros such as `00` are rejected by this narrower policy even though
  the retail parser accepts them as reported errors using lexical comparison.
- Timestamp, when supplied, is a one-to-twenty-digit decimal string. No current
  clock value is generated.
- Fixture URLs must be absolute HTTP(S) URLs with a host, without credentials,
  query/fragment delimiters, whitespace, controls or unsafe raw XML/URI
  punctuation. Port zero and invalid/out-of-range ports are rejected. The
  reviewed native extractor may admit or truncate strings this policy rejects.

Each response line is validated, escaped where applicable and encoded to UTF-8
before its byte length is checked. The bounded buffer grows only after that
check. A synthetic multibyte-URL case proves that an oversized response stops
before later URLs are processed. Codec exceptions contain fixed diagnostic text,
never supplied URI, common-field, evidence or status values. A fixture's XML
ErrorMessage is separately and explicitly caller supplied.

## Integration remains separate

The older EC_Connect API still requires an initialized environment and confirmed
device key pair (`ec_connect.cpp:227-243`), followed by EULA/account/device-status
branches. XML parsing does not satisfy those conditions. No account or device
success, redirect, endpoint override, native connect callback, ticket operation
or installation flow is implemented here.

The matched retail response check does not prove request-version/field
completeness, bootstrap caller/origin policy, complete URL storage/admission
behavior or authorized identity handling. These remain integration gates before
any route can use this component. The request parser remains explicitly the
older `Version=2.0` subset; native response execution does not prove that request
builder value. Keep older-source findings distinct from actual original native
instruction execution against synthetic input.

The [native verifier](../../tools/verify_wii_shop_ec_config.py) executes the
fingerprinted original response-reader/configuration instructions with synthetic
memory and explicit heap/logging boundaries. Its XML lookup helpers and URL
setters run as native instructions; no browser, network, account or device state
is present. The [serializer interoperability tests](../../tests/test_wii_shop_ec_config_interop.py)
exercise this separate boundary. They do not establish a live connection or
retail request-builder version.

The [native execution report](ec_config_native.md) details the observed v21
behavior and its limits. The [batch integration report](../../research/wii_shop_ec_config_integration_20261025.json)
records six serializer-to-native cases and the full regression result.

Validation: `.venv/Scripts/python.exe -m unittest tests.test_wii_shop_ec_config -v`
passes fifteen synthetic tests covering ECS/CAS separation, opaque field privacy,
XML and URI bounds, no defaults, lexical response shape, required five URLs,
retail zero-code/informational-message behavior, common errors and incremental
output containment. No captured account data,
owner credentials, NAND, Dolphin, external service or original source execution
is used by these tests.
