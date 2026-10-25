# EC configuration bootstrap boundary — October 25, 2026

**A parsed GetECConfig response is service discovery, not an original Shop
startup flow or connected account.** The recovered shared scripts do not expose
or call a GetECConfig JavaScript entry point. The older native source starts
that request inside `EC_Connect`, with prerequisites and subsequent account/
device-status work. A new browser route cannot be inferred from codec success.

The [metadata report](wii_shop_ec_bootstrap_20261025.json) records ten
inventory-verified source files, three hash-checked captured scripts, the
captured index page and seven installed-v21 support pages. Original source,
page bodies and request selectors remain private. This was a read-only audit:
no original commerce instructions/scripts ran, no network or account/key data
was accessed, and no NAND/runtime/code integration changed. The sibling native
parser harness is a separate execution experiment.

## Entry and callback evidence

| Layer | Verified evidence | Boundary |
| --- | --- | --- |
| Captured `ec.js` | Constants; no function definitions or GetECConfig/`ec.connect` call | Loading this file does not initialize or connect commerce |
| Captured `oss.js:12` | Constructs `ECommerceInterface` | This is the native wrapper, not a replacement service handshake |
| Captured `oss.js:1421-1527` | `checkProgress` polls `ec.getProgress`; `finishOp` selects polling or the supplied completion callback | General asynchronous operation handling, not a dedicated GetECConfig callback |
| Captured `title_manager.js` | Uses `ec.getDeviceInfo`/`ec.getTitleInfo` for title/storage information; no configuration entry | Owned-title/device state must not be replaced with imported catalog data |
| Captured `index.jsp:623,665` | `initPage` enters `showCheckRegistered`; obtains native interface/device/title information | No recovered `ec.connect` or GetECConfig request here |
| Older `ec_api.cpp:38-51`, `ec_wshop.cpp:134-160` | `EC_Init` enters platform initialization and registers the JavaScript plugin through host callbacks | Initialization is separate from connection |
| Older `ec_js.cpp:5308-5328` | `initECommerceJSObject` receives current-URL/plugin-registration callbacks and installs global access callbacks | It initializes the generic `requestCallback` to null; this is not a SOAP tunnel |
| Older `ec_connect.cpp:227-243` | Native `EC_Connect` requires an initialized operation environment and a confirmed device key pair | A positive operation ID is asynchronous work, not connection success |

The older `getter_ECInterface` has no `connect` or `getECConfig` getter. Its
`connect` string at `ec_js.cpp:60` belongs to a diagnostic operation-name table.
That distinction prevents inventing a JavaScript call from a string hit. The
exact complete retail-v21 getter revision has not been established by this
audit.

The captured generic poller distinguishes `EC_ERROR_NOT_BUSY`,
`EC_ERROR_NOT_DONE` and `EC_ERROR_CANCEL_FAILED`; other completion branches use
the supplied callback. It checks progress size/phase and can request cancellation
after a timeout. Neither its callback mechanism nor merely obtaining an
`ECProgress` object supplies account authorization or acquisition success.

## Where GetECConfig fits

The older connection worker performs its EULA check before `getNetConfig`
(`ec_connect.cpp:128-143`). `getNetConfig` builds ECS `GetECConfig`, adds
`ECVersion` from `productVersion`, sends the request, checks common response
status, extracts the five URL fields and installs service/content URLs
(`:45-109`). The connection worker then has account, registration-sync and
device-status branches; its connected flag is only assigned later (`:146-201`).
Configuration extraction therefore precedes completion of the connection flow.
This audit neither executes nor bypasses those prerequisites.

The source request has two distinct version concepts: common `Version` defaults
to **2.0** in `ec_soap.h:233`, while `ECVersion` carries the library product
version (`ec_api.cpp:32`, `ec_connect.cpp:62`). The offline codec preserves that
distinction and treats the product string as opaque. The actual retail request
version/body remains unverified; matched response parsing does not establish
what the retail request builder emits.

The ECS common builder emits `SerialNo`; `Age` is a separate CAS-only field.
The source request envelope uses namespace declarations rather than a separate
`encodingStyle` attribute. The reviewed codec's structural rejection of
unexpected root attributes therefore does not reject that source form.

The common response reader (`ec_soap.cpp:294-345`) requires the reviewed literal
envelope/body/response forms, optional `TimeStamp`, and `ErrorCode`. Its zero
test is the literal string `0`; a nonempty `ErrorMessage` independently reports
failure. It can retain server error detail in native progress state. The five
configuration values are `ContentPrefixURL`, `UncachedContentPrefixURL`,
`EcsURL`, `IasURL` and `CasURL`; they are not account/session/entitlement fields.

The sibling [retail response verification](../channels/wii_shop/ec_config.md)
found a material difference: v21 accepts literal code `0` with a nonempty
informational `ErrorMessage` and continues extracting the five URLs. The older
source's message-as-failure rule must not be applied to v21. The serializer was
updated to follow that matched retail result while retaining the explicitly
older-source request subset. This audit reviewed that correction without
executing the original parser itself.

## Origin and missing startup work

The older `allowJavaScriptAccess` reference checks the `.shop.wii.com` hostname
suffix (`ec_chkDownload_bw.cpp:187-218`). Its JavaScript bridge also tracks
HTTPS/trusted-page state, treats `/ext/` paths as untrusted, and restricts
globals/methods accordingly (`ec_js.cpp:926-1054`). These are source references,
not authorization for an arbitrary replacement origin or a proven exact-v21
origin guard. The original v21 executable contains ten NUL-terminated instances
of the suffix, which corroborates a string family without proving its caller,
comparison rules or accepted origin/port combination.

The hash-checked installed v21 resource archive's seven support HTML pages have
no `EC_Connect`, `GetECConfig` or `ec.connect` marker. They provide error/EULA/
manual-transition UI, not a recovered configuration-bootstrap page. The existing
[startup contract](../channels/wii_shop/startup_contract.md) still leaves its
initialization calls at `0x8002F560` and `0x8002F680` stubbed. The actual launch
arguments, full initialization order, connection caller and first real browser
request remain missing evidence. Nothing here promotes a static `/startup`
literal, the captured index, or a generic callback into that missing flow.

## Independent component review

The new offline codec's source/field split, namespace/action isolation,
source-backed response lexical shape, private request representations and
bounded XML/output handling match the reviewed scope. No material shape or
provenance mismatch was found. Its URI policy, canonical uint32 fixture-status
policy and other defensive bounds are local restrictions; they are not native
protocol acceptance claims. Endpoint/evidence values remain caller supplied,
with no defaults or live-success handler.

The native harness requires the original main fingerprint, bounded synthetic
response bytes, a bounded synthetic heap, instruction caps and selected control
flow. Its returned URL/error fields echo the supplied response, so that output
is suitable only for explicitly synthetic fixtures; it must not be described as
generally redacted output for real account/service responses. The harness and
parent interop tests use synthetic data and have no browser/network/IOS access.
Independent review additionally requested output-string pointer containment:
before exporting a native string, check both its length and that its decoded
storage stays inside synthetic heap/object regions. A length check alone could
read other mapped original-program memory if a native string were corrupted or
misdecoded. This finding was sent to the harness owner for correction; its final
status is recorded in the metadata report. Parent integration review confirmed
that synthetic allocation bounds and the inline object-capacity check are now
enforced. This audit inspected their code without running original instructions. Native
parser results and remaining limitations belong to their separate report.

Before a live route, recover the actual retail caller/request and original
origin/transport behavior, then establish authorized identity/session/error
semantics. Keep service discovery, connection, original storefront navigation
and acquisition as distinct evidence boundaries; do not simulate their success.
