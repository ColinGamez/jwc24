# Preserved primary-source assets

These files are research references, not client-ready Wii assets. Keep them
unaltered so later reconstructions can be checked against the original source.

## Nintendo Online Magazine No.146

The five JPEGs under `nintendo_nom_146/` were recovered from Nintendo's
September 2010 Online Magazine capture in the Internet Archive. Page 2 covers
`みんなの間`; page 3 covers `プレゼントの間`.

Capture base:

`https://web.archive.org/web/20100905092455id_/http://www.nintendo.co.jp/nom/1009/`

| File | SHA-256 |
| --- | --- |
| `page2_img_main_img01.jpg` | `6DF07D8F15D5C067D770460B6FBBF513779C54D3A24A71580E449130565CD81A` |
| `page2_img_p2_img_01.jpg` | `9990C41C4817F2D674D1AEC31D02BCDD6587CFE94D005B72D7FEBF009F453F11` |
| `page2_img_p2_img_02.jpg` | `BB7744A61798C876047707F94291B5935A12905256C94A44BEAF3230716DAB61` |
| `page3_img_main_img01.jpg` | `2B646A6BC786CACBC94D8DD243B19E88AFDC6C1CB9975DF74EABA40E13D84B45` |
| `page3_img_p3_img_01.jpg` | `A82C6B8A1D88EA3A864E44611F54D277C746686556894CA7DDE5CDDD0C37F70D` |

## Nagatanien Ginger Club

`nagatanien/2009-12-18_shoga_room_release.pdf` is the original Nagatanien
release. It documents the dates, recipes, song, activity introduction,
sampling campaign, calendar tie-in, and two embedded Wii room screenshots.

Source: `https://www.nagatanien.co.jp/contents/news_release/63.pdf`

SHA-256:
`184FEC9DE88E6B9328982F6B3B28C31034D9E240F95B02654A3CA475B8C96238`

## Authenticity boundary

These are authentic publication images, but they are not extracted server
textures, room binaries, or Mii records. Generated JWC24 artwork and Miis must
remain labeled as recreations until byte-identical service assets are found.

## Confirmed archive gaps

The exact 2010-01-17 Wayback capture was queried for all 13 logo objects named
by the official room directory. None has a captured image response:

`logo_aeon.gif`, `logo_aflac.gif`, `logo_glico.gif`, `logo_honda.gif`,
`logo_jleague.gif`, `logo_lifenet.gif`, `logo_meikogijuku.gif`,
`logo_nagatanien.gif`, `logo_ongaku.gif`, `logo_pokemon.gif`,
`logo_unicef.gif`, `logo_warner.gif`, and `logo_yoshimoto.gif`.

Their filenames and page placement are authentic evidence, but the binaries
remain lost. The empty `official_directory_logos/` directory intentionally
records that this recovery pass was performed; no fabricated files belong in
it.
