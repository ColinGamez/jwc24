# Online multiplayer integration

Status: planned; no JWC24 game patcher, provider selector or multiplayer test
has been implemented. The owner authorized using an existing online-game
service alongside JWC24 on 2026-10-25.

JWC24 will initially recommend Wiimmfi for supported Nintendo Wi-Fi Connection
games and offer WiiLink WFC as an optional alternative. This is a project
default, not a claim that one provider supports every game or region. Users
must be able to retain their existing provider and play with their chosen
community. This does not imply affiliation with either service.

## Integration boundary

JWC24 supplies its channel services and Wii Mail. The chosen WFC provider
supplies the game's supported online functions. Setting up JWC24 alone does
not patch a game or make its online mode work. Online play belongs in external
setup tooling; preserve the original Japanese game and channel controls.

Use the provider's maintained patching method for the exact game, region and
platform. Disc-image, retail-disc and WiiWare methods are distinct. Some
games require servers beyond WFC, so a WFC patch is not proof that every
network feature works. Recheck provider instructions when implementing setup;
do not pin a DNS address or an old patcher version from this research note.

For coexistence, route only JWC24's explicitly supported service endpoints to
JWC24. Game traffic must reach the selected provider. Do not introduce a
blanket Nintendo-domain redirect or overwrite console-wide DNS as a side
effect of choosing an online provider. Inspect existing settings first.

Selecting a provider must not rewrite saves, friend codes or account/device
identities. Check the provider's current migration requirements and explain
any required save change before offering it. Do not silently switch providers
when a connection fails. Return the actual game/provider error for diagnosis.

Original inputs stay intact. Where a provider requires a modified game image,
produce a separate private copy with recorded input/output hashes; never
redistribute games, WADs, NAND data or device credentials. The owner's actual
Wii backup stays untouched. Dolphin testing may use only the authorized
isolated vWii profile, subject to the selected provider's current requirements;
Shop-profile success does not establish WFC compatibility.

## Implementation and verification remaining

- Add an optional provider choice to future setup tooling, without changing
  the existing mail launcher or native channel screens.
- Record the game ID, region, platform, provider, patcher source/version and
  compatibility evidence. An untested title remains unverified.
- Verify one owned Japanese game through login, matchmaking/friend joining,
  a complete session and reconnect. Test Wii/vWii and Dolphin separately.
- Confirm JWC24 channel requests and mail still work with that network setup.
- Check WiiWare separately before claiming support for Shop-acquired titles.

## Research sources

Reviewed 2026-10-25. These document upstream capabilities, not a completed
JWC24 integration. No game files, NAND, DNS settings or runtime configuration
were changed for this review.

- [Wiimmfi patching documentation](https://wiiki.wii-homebrew.com/Wiimmfi_%28en%29/Patcher)
  distinguishes patching methods and warns that not every game is supported.
- [Wiimmfi game compatibility documentation](https://wiiki.wii-homebrew.com/Wiimmfi_%28en%29/Game)
  points to per-game status and notes that some titles do not use WFC.
- [WiiWare Patcher source](https://github.com/KcrPL/WiiWare-Patcher) documents
  a separate Wiimmfi patching workflow for WiiWare.
- [WiiLink WFC](https://wfc.wiilink24.com/) supplies compatibility lookup and
  separate installation entries for Wii/vWii and Dolphin.
- [WiiLink WFC server source](https://github.com/WiiLink24/wfc-server)
  identifies its server implementation as a Nintendo WFC replacement.

Wiimmfi's live site and direct wiki fetches returned HTTP 403 during this
review; indexed maintainer documentation was available. No live compatibility
table or player-count comparison was verified. Current per-title status and
patcher requirements must be checked before implementation or play testing.
