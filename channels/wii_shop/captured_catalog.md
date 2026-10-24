# Captured catalog layout and navigation

October 25, 2026. Populated catalog lists now use the reviewed historical
`B_04.jsp` template and captured shared CSS/images. They no longer depend on
the modified interactive archive's JavaScript row template. The previous
renderer remains available for its existing empty-result and explanation pages;
those original states have not yet been recovered.

## What is preserved

The adapter retains the captured scroll frame, card geometry, title containers,
backgrounds and paging controls. For **776 of the 844 preview IDs**, catalog
panels are associated through matching detail links and image title IDs.
Their original catalog title text, line breaks, publisher and platform text are
preserved. A catalog title may differ from its detail-page title, for example
in trademark marks; it is no longer split arbitrarily from the detail name.

The other **68 titles** use the captured card prototype with available metadata
or source listing names. Their original per-title typography remains unknown,
and a long unmatched name may clip in the original single-line container.
Missing icons remain the [separate image-role gaps](image_roles.md).

The original keyboard/remote handler is extracted unchanged from the pinned
page and served as a separate 488-byte script. It scrolls by the captured step
for up/down keys and clicks the page controls for left/right keys. The captured
frame-focus behavior and first/last-page wrap are restored. JWC24 generates
the local destinations and preserves filters through paging, details and back.

Captured gift, loyalty/discount and update branches are not visitor account
state. Those branches are excluded from the copied cards, and captured account
scripts are not enabled. Historical points come from the previously accepted
metadata, with unknown amounts remaining unknown. No purchase/ownership claim
or commerce operation is introduced.

## Source and limits

The loader checks the private catalog-capture manifest, each source payload's
size/hash and the known layout fingerprint. All 90 files are checked; the
bounded individual catalog pages supply the indexed panels. The large all-title
duplicate adds no matching IDs, as recorded in the [earlier image review](image_roles.md).
Original bodies stay private. Runtime cards are parsed copies with local URLs,
not byte-identical whole-page responses or recovered Nintendo server code.

The template's captured caption is English even though the request region is
Japan. It is retained as captured; this is **not** a recovered Japanese interface
localization. Footer/back handling and unavailable account fields are still
adapted. Original Japanese strings, empty-result behavior, category/detail
templates, acquisition/account services and native visual checks remain work.

## Validation and reproduction

The [validation report](../../research/wii_shop_captured_catalog_validation_20261025.json)
records all 85 catalog pages over certificate-verified loopback HTTPS, 844 unique
title links, 776 preserved title-line sets, 799 dependency routes, 835 captured
name searches and three filter/detail/back paths. JavaScript VM checks exercise
the original navigation handler with synthetic DOM objects. There are 102 Shop
tests and two credential tests. These checks do not establish native visual
fidelity; Dolphin remains closed.

The existing [catalog capture import](image_roles.md#reproduce-privately) produces
`private/wii_shop/frontend-japan-catalog-v2`. No additional import is required.
The default service loads it with `--catalog-capture`; the launcher compares
the running manifest digest and waits for startup before its TLS health check.
The former modified templates stay private for unfinished experimental states.
