# Full Shop restoration: remaining completion criteria

Updated October 25, 2026. **The Shop is not complete.** Restored historical
browsing and a working loopback browser do not establish the original Japanese
experience or a working acquisition service.

| Area | Verified progress | Still required |
| --- | --- | --- |
| Home/list/detail | Captured home and populated list layout; 776 original catalog title-line sets; 834 captured detail views | Remaining original states, 68 per-title list layouts and ten captured detail views |
| Controller information | 837 raw captures, 836 accepted pages; 834 detail/controller links; original vWii compatibility condition | Eight unavailable controller pages and native interaction/visual checks |
| Artwork | 776 list icons and 835 detail images with role-specific page references | 68 list icons, nine detail images and the missing CERO descriptor |
| Japanese interface | Home copy corroborated against Nintendo's screenshot; detail heading corroborated in its manual; captured product text retained | Remaining Japanese labels, original markup/flow and encoding verification |
| Category/search | Native keyboard wiring and exact publisher/platform/raw-description backend filters | Original publisher/category gateway/WiiWare pages, source-backed genre-code mapping, original empty/search-again states, verified popularity/new-release data |
| Native experience | Original v21 browser connects; original installed scripts and selected captured handlers are checked | Current home/list/detail/controller visuals, Japanese input, hover/sound behavior and complete interaction in Dolphin |
| Commerce | Client/library interfaces, installed contents and selected native paths audited | Account/session/device-status adapter, catalog/entitlement semantics, verified title/version/content selection, tickets/acquisition, storage/install behavior and error recovery |

The known collector backup lacks `B_17.jsp`, `B_23.jsp` and `B_27.jsp`. A fresh
exact-path check of the local Nintendo index found no `B_23.jsp`; its only
`wstrunk` filename remains the synthetic notes fixture. The installed Shop
resource archive has 58 files and contains neither those missing page names
nor the missing CERO descriptor. These are bounded source checks, not proof
that no other unindexed archive could contain them.

Nintendo's [December 2007 developer interview](https://www.nintendo.co.jp/wii/staff/shopping-channel/articles/index2.html)
describes the addition of publisher/genre/title search and a clickable search
result heading for searching again. Its linked [original search screenshot](https://www.nintendo.co.jp/wii/staff/shopping-channel/articles/movie/movie007.jpg)
provides a Japanese visual reference. The private image's SHA-256 is
`6a1b6c4b0ad7969740fef6783e79c154c825e15085899332a811b78defc36142`.
This is a 2007 reference, not evidence that its layout is the exact v21 target.
It does not supply the missing server templates, so no replacement heading or
picker layout is invented from that description.

The [authenticity audit](authenticity.md) remains the controlling fidelity list.
Unimplemented commerce is not replaced by simulated success, invented account
state or a catalog interpreted as ownership. Original software and device data
remain private; the owner's actual Wii backup is unchanged.
