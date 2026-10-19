# Hot Pepper directory to Demae-can branch handoff

Hot Pepper remains the restaurant directory. A separate, locally reviewed
mapping associates a Hot Pepper restaurant ID with the matching Demae-can
branch URL. Directory presence alone never enables ordering.

`tools/build_demae_restaurant_links.py` checks curated reviews against cached
catalogs and publishes the result privately. It requires matching branch name
and full address, with only Unicode/whitespace normalization and the equivalent
numeric `丁目` separator normalized. Chain name alone is insufficient. Reviews
must have timezone-aware timestamps no older than 30 days at build time.
Unknown restaurants, duplicate identities, conflicting branch mappings and
noncanonical/off-domain URLs are rejected. New sessions should be created from
freshly reviewed mappings; existing session contexts are immutable snapshots,
not ongoing availability checks.

The first reviewed match is Hot Pepper `J000662333`, 目利きの銀次 札幌北口駅前店,
to [Demae-can branch 3248195](https://demae-can.com/shop/menu/3248195).
The official page's name and address match the cached Hot Pepper identity
after the documented normalization. The Hot Pepper page is
<https://www.hotpepper.jp/strJ000662333/>. The private output currently has
**one reviewed link among 9,400 cached restaurant records**. This is not
nationwide match coverage. Delivery eligibility and current acceptance must
still be checked by Demae-can with the customer's destination.

## Session and mail behavior

The handoff store supports a public restaurant context containing ID, name and
the reviewed Demae-can URL. Each session stores its own JSON snapshot. Stable
entries can create separate sessions retaining the same selected branch;
confirming one session does not confirm another. Legacy generic sessions and
entries remain valid through an additive SQLite migration.

The phone page escapes restaurant text, displays the selected restaurant and
links directly to that branch. It still states that Wii basket items are not
transferred. The explicit user-confirmation notice includes the same selected
restaurant, retains its disclaimer that it is not a provider receipt, and
uses the existing durable outbox/idempotent mail path. Scanning/GET does not
confirm an order or send a notice.

These changes are implemented and tested in the backend. The running phone
process has not been restarted by this pass; no real-user session or notice
was created for the reviewed branch. Native restaurant/menu/basket serving and
the final checkout hook remain unfinished. The home-button QR interception
remains withdrawn.
