# Installed Wii Shop client audit — October 24, 2026

## Concrete comparison target

The shared Dolphin profile contains Shop title `0001000248414241`, version
**21**, requiring **IOS 56**, with boot content index **17**. The audit reads
only its TMD, referenced content files and shared-content map. It does not
read tickets, certificates from the NAND identity store, Shop account/save
files or personal configuration. Nothing was launched, installed or modified.

All **18 referenced contents**, including **11 shared contents**, match their
TMD sizes and SHA-1 digests. The [metadata report](wii_shop_client_audit_20261024.json)
records their SHA-256 fingerprints and the TMD fingerprint. Matching content
hashes establishes consistency with this installed TMD; the audit does not
verify Nintendo's TMD signature or independently establish installation origin.

`tools/audit_wii_shop_client.py` reproduces the report from an explicitly
supplied NAND root. It resolves shared contents through `shared1/content.map`
and rejects missing mappings, content mismatches and paths outside that root.
No title key is needed because installed content is already decrypted.

## Executable and resource findings

| Content index | Finding | Interpretation |
| --- | --- | --- |
| 1 | DOL structure; all six selected commerce/registration markers present | Main executable comparison target |
| 2 | U8 resources containing local HTML, JavaScript and browser configuration | Bundled support pages, not proof of a complete storefront |
| 17 | Boot DOL with a physical MEM1 entry alias | TMD-selected loader; distinct from the main commerce executable |
| Other indices | Resource archives, including shared contents | Inventory only in this pass |

The main executable contains `ECommerceInterface`, `ECProgress`, `GetECConfig`,
`CheckDeviceStatus`, `CheckRegistration` and `SyncRegistration`. This corroborates
the recovered library's interface family. It does **not** prove that version
21 uses that exact source revision or identical request/response parsing.

The index-2 archive includes `common.js`, `shop.js`, `sound.js`, `opera.ini`,
`input.ini`, `myfilter.ini` and local pages including `internet.html`,
`eula.html`, `eulacomp.html`, `error.html`, `corrupt.html`, `nwc24error.html`
and `nwc24fullerror.html`. Names are listed in the metadata report; original
page bodies and artwork remain private. No server-rendered catalog pages were
established by this resource inventory.

## Static startup/service candidates

The main executable contains these URL literals, with query strings,
fragments and userinfo excluded from the report:

| Scheme / host | Path | Lead |
| --- | --- | --- |
| HTTPS / `oss-auth.shop.wii.com` | `/startup` | Original storefront startup candidate |
| HTTPS / `oss-auth.shop.wii.com` | `/oss/getLog` | Additional service-path candidate; behavior untraced |
| HTTPS / `oss-auth.shop.wii.com` | Empty | Host/origin candidate |
| HTTPS / `ecs.shop.wii.com` | `/ecs/services/ECommerceSOAP` | Commerce SOAP candidate |

These are static executable strings. The audit does not prove which requests
occur first, their methods/bodies/headers, redirects, region/language selection,
TLS trust behavior or whether a particular literal is exercised. URL scanning
is restricted to DOL candidates so embedded resource certificates are not
misreported as application routes. The route list is not exhaustive.

## Next runtime boundary

This resolves the earlier lack of a concrete installed comparison target.
The next step is a controlled startup capture for this fingerprinted version,
using an isolated profile and redacted logging. It should establish the first
page request and the native bridge/service sequence before building responses.
Origin access and TLS behavior must be observed rather than inferred from
the old library. No redirect or certificate bypass was configured here.

Read-only startup/catalog remains the first restoration milestone. Ticket,
entitlement, content validation and installation are separate boundaries.

Eight focused source/client audit tests pass. They cover provenance drift,
content size/hash mismatches, invalid shared-map records, URL query/userinfo
redaction, path containment and bounded DOL entry detection. The installed
18-content audit was separately run successfully and its metadata recorded.

## Static follow-up: manual-link distinction

The nine absolute `/startup` literals inspected in the main DOL are manual-link
templates with `initpage=showManual` and an appended title-ID field. Their
presence does not establish the main storefront entry request. Relative strings
also reference title/help variants. The earlier route table deliberately omits
query values, so this distinction requires the fuller private string review.

A candidate immediate-address reference at `0x8008893C` loads the ECS URL at
`0x80322020` inside the function beginning `0x80088920`. That function also
forms the nearby `GetECConfig` pointer at `0x80322054`, consistent with the
reviewed connection-library flow. This is a static comparison lead, not an
executed request or an exact source/binary match. Derived disassembly stays
under `private/wii_shop/`. No runtime capture was performed in this follow-up.

## Native URL-builder follow-up

The host pointer's consumer leads to builder `0x8002BC10`. Its native
formatter now passes synthetic Unicorn checks for base selection, concatenation,
truncation, pointer publication and output guards. This narrows the gap from
raw URL literals to an executed builder contract. The selected main launch
suffix and subsequent browser request are still open. See the
[startup contract](../channels/wii_shop/startup_contract.md) for fingerprints,
caller leads and exact verification limits.
