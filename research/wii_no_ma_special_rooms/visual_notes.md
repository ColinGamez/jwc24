# Recovered visual evidence

## Nintendo Online Magazine No.146

The archived HTML and imagery are presented at 16:9 Wii capture dimensions
(the individual screenshots are generally 300x168 in the article).

### `みんなの間`

Source images:

- `page2/img/p2_img_01.jpg`
- `page2/img/p2_img_02.jpg`
- `page2/img/main_img01.jpg`

Observed structure:

- The normal movement overlay contains four large square buttons arranged 2x2:
  `シアターの間`, `いろんな間`, a dated `Wiiの間カレンダー`, and
  `Wiiの間テレビ`.
- The room is a bright, largely white gallery rather than the normal living
  room.
- A horizontal carousel of submitted photographs occupies the upper portion.
- A selected/hosting Mii stands within the gallery while several visitor Miis
  face the display from below.
- The `みんなの間` identity/placard is visible at lower right with a row of
  colorful person-like marks.
- Article artwork preserves the faces/names of the top three creators for the
  first `顔に見える写真` contest. These are evidence of entrants, not proof
  of the later Grand Prix host Mii binary.

### `プレゼントの間`

Source images:

- `page3/img/p3_img_01.jpg`
- `page3/img/main_img01.jpg`

Observed structure:

- Minimal white room with a round white table and the user's/viewpoint Mii in
  the foreground.
- Two guide Miis stand opposite the viewer. The wife has medium brown hair,
  glasses, and a green top. The husband is balding with dark side hair,
  moustache/facial hair, and a black top.
- A pink rectangular action button at right reads `今週のプレゼントの間`.
- The screenshot's dialogue welcomes the user and says the products change
  weekly.
- This is strong face/clothing reference material, but no original 76-byte Mii
  records have been recovered.

The same page identifies the planned products and providers:

- Salad spinner — OXO
- Kiri & Stick — Bel Japon
- Tagine pot — Le Creuset
- Lekue silicone steam case — Column Japan
- French-press coffee maker — Bodum
- Mini food processor — Cuisinart
- GABAN dressing assortment
- Tickets to the Van Gogh exhibition marking 120 years after his death

### `永谷園生姜部の間`

Source: Nagatanien press release page 1.

Observed structure:

- The room view uses a branded multi-tile menu rather than only a dialogue
  scene. The page appears to include separate tiles for recipes, the song,
  activity information, and the product-sampling/application campaign.
- Two orange-clad host Miis stand along the bottom of the menu view.
- A separate entrance view reads `Welcome to 永谷園生姜部` beneath the
  Nagatanien/Ginger Club branding, with the same two host Miis below.
- The available PDF embeds these screenshots at publication size. They are
  sufficient for layout reference but not a source of authentic Mii binaries
  or pristine Wii assets.

## Reconstruction implications

- A historical room template must support at least three distinct layouts:
  carousel/gallery, guide-dialogue campaign, and branded feature grid.
- Parade Mii, in-room host Mii, and user/visitor Miis are separate roles.
- Room-specific action buttons and identity panels must be data-driven.
- Recreated Miis should cite the visual reference and remain labeled
  `visual recreation` until an original binary or service capture is found.

## Official January 2010 room directory

Archived page:

`https://web.archive.org/web/20100117195321/http://www.wiinoma.co.jp/variety/ironnama.html`

The official Wii no Ma site preserved a 13-room alphabetical directory:

1. アフラックダックの間
2. イオンの間
3. 音楽の間
4. グリコの間
5. Jリーグの間
6. 永谷園生姜部の間
7. ポケモンの間
8. Hondaの間
9. 明光義塾の間
10. ユニセフの間
11. ライフネット生命の間
12. よしもとの間
13. ワーナーの間

The page references an original logo image for every entry under
`/variety/images/ironnama/logo_*.gif`. This proves the room roster and gives us
canonical logo filenames, but these website logos must not automatically be
treated as the exact placard textures used by the Wii client.

Room descriptions additionally establish:

- Honda had a newly added cute ASIMO animation.
- Pokémon distributed a room-exclusive coupon for a Pokémon Center present.
- J.League presented its organizational理念/mission.
- Lifenet featured `目からウロコの保険塾`.
- Yoshimoto included original performer projects, live comedy, anime,
  Yoshimoto Shinkigeki, and films.
- UNICEF introduced the lives of children around the world.

### Yoshimoto concierge lead

A preserved three-image dialogue sequence identifies the visiting concierge as
`矢部浩之99` (Hiroyuki Yabe of Ninety-nine). He says he brought an entertaining
Yoshimoto program and explicitly tells the user that `よしもとの間` is by the
houseplant. The source is retrospective and does not yet supply an original Mii
binary, but it is useful facial/dialogue evidence for an authentic recreation.

## Interaction patterns recovered from official archives

- **Coupon:** Pokémon Center present coupon distributed from Pokémon Room.
- **First-come sample:** illume offered product samples to the first 50,000
  users.
- **Quiz drawing:** Tanaka Precious Metals offered 100g of pure gold.
- **Video tutorial/promotion:** Hyper Yo-Yo presented trick footage.
- **Challenge-support giveaway:** `新しいこと はじめよう！の間` offered
  items intended to help users begin a new activity and refreshed its prize set.
- **Recurring weekly campaign:** `今週のプレゼントの間` changed products
  weekly and used a persistent guide-Mii scene.
- **Franchise hub:** Kirby combined free episodes, game videos, reference
  material, and merchandise drawings.
- **Mii-centered service:** Mii Room combined games, goods, software promotion,
  and curated Mii showcases.

The server schema therefore needs distinct action semantics for coupon,
first-come claim, lottery application, quiz-gated lottery, video, gallery,
download/transfer, and informational tiles.
