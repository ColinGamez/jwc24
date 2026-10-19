# Demae-can phone checkout and Wii notice

## Current navigation decision

The backend now supports a selected-restaurant snapshot and a direct reviewed
Demae-can branch link. See [restaurant linking](restaurant_links.md) for its
single verified match, legacy database migration, test scope and deployment
status. Generic sessions retain their original homepage link. Neither variant
transfers a Wii basket or establishes restaurant delivery eligibility.

The home-button QR interception has been withdrawn at the user's request.
The default launcher now pins `HCHJ-native-flow-restored-v8.wad`, identical to
the local API build with the original executable navigation and stock UI.
`-PhoneOrdering` also uses that restored flow while checkout integration is
unfinished. The old standalone QR experiment is available only through the
explicit `-PhoneQrDiagnostic` option; it is not the ordering experience.

The required flow is native restaurant browsing, verified real menus, native
basket review, then a phone handoff at final checkout. Demo restaurants and
invented dishes are excluded by user preference. Restaurant/menu/basket routes
are not yet implemented in the running fixture service, so restoring the
button does not establish working browsing or checkout. The native telephone
validator remains unchanged and may still block the existing profile.

The rendered v7 QR has been visually verified as black, legible and centered.
That resource and the durable confirmation/mail service are retained for the
eventual checkout integration, not attached to the home button. The phone
service currently opens Demae-can without transferring basket items.

Read-only tracing found action24 (`webApi_order_done`) passed to the POST
wrapper `0x8002C6A8` at `0x800A1B04`. This is a request boundary lead, not a
reviewed checkout UI hook. No replacement success response or order-complete
state is synthesized. The final UI callback, return path and basket context
must be traced before applying a new native hook.

Verified menu research: Domino's Japan's official menu index
<https://www.dominos.jp/menu> was captured privately. A product detail request
returned HTTP403; no detail prices or local delivery availability were inferred.
Demae-can's [item API documentation](https://developer.demae-can.com/docs/integration-guide/shop/items)
describes shop-registered item/option retrieval, not an established public
consumer menu feed. Provider access and basket transfer remain unresolved.

The sections below describe the retained phone component and earlier research;
their prototype navigation notes do not describe the current default launcher.

The phone handoff opens the official https://demae-can.com/ website. Address,
restaurant selection, items, payment and final checkout happen there. It does
not transfer a Wii basket, submit orders or claim provider callback access.

After checkout the user returns to the handoff page and presses **I placed my
order**. That explicit confirmation persists a notice in the private outbox.
The notice identifies itself as a user confirmation, not a provider receipt.
Official acceptance, delivery time and status remain on Demae-can.

`jwc24.demae_handoff.HandoffStore` stores only a hash of the random QR token,
the paired Wii ID, timestamps and the persisted notice. Tokens expire after
24 hours. A reusable `/p/` entry creates a new expiring session per scan, so the
packaged native-screen QR itself does not expire. Entry tokens can be revoked
in the private pairing store. GET/scanning does not confirm or send mail. Repeated confirmation and
delivery retries reuse identical notice bytes, so the shared MailStore digest
prevents duplicate messages. No order/payment/address details are collected.

`tools/demae_phone_server.py` serves the phone page on port18086 and sends
confirmed notices through the existing loopback mail server on8081. A retry
worker drains the durable confirmed outbox every five seconds. Request URLs
and tokens are not logged; pages use no-referrer and no-store. Foreign Origin
confirmation requests and unexpected bodies are rejected.

`tools/create_demae_phone_qr.py` generates `private/demae/phone-handoff.png`
using a phone-reachable LAN origin and a registered Wii mail ID; `--stable-entry`
also writes the private entry URL for the native texture builder. The phone must
be able to reach the PC, typically on the same Wi-Fi. No firewall settings or
Dolphin save/controller/network settings are modified by these tools.

Implemented and tested: phone page → explicit confirmation → authenticated
shared mail queue → one pending notice, including repeated-button idempotence.
The phone component is running locally and a QR is generated. Remaining:
displaying that QR inside the native Demae channel, integrating the handoff into
its navigation, and verifying the notice appears on the actual Wii Message Board.
This is not yet an end-to-end native-channel completion claim.

The preferred native resource adds a hidden `JWC24_QR` group to the existing
animated dialog window, with a unique 224×224 lossless I8 QR texture and Japanese
instructions. The exported texture decodes to the exact stable private entry URL.
Original panes, materials and the other 55 archive files are preserved. A private
resource-only WAD has been built and checked; it has not been installed.

The native opener has been assembled and tested against idle, busy, pending-open
and missing-resource cases. Integration still requires the Title input pause,
last-drawn modal overlay and close-to-idle cleanup hooks. The entry is the existing
Demae button in the ordering scene, rather than a transition back through startup.
Passing offline checks does not establish that the native screen renders or that
its close behavior works in Dolphin.
