# Original category controls and backend filters

October 25, 2026. A further 95 navigation/setup captures provide evidence about
the original control meanings. The captured Virtual Console menu routes its
category choice through `B_23.jsp`; the system and genre pickers are `B_03.jsp`
and `B_16.jsp`. Nintendo's [original Shop instructions](https://en-americas-support.nintendo.com/app/answers/detail/a_id/2829/~/how-to-download-wii-shop-channel-items)
also identify system, publisher, genre and title searches. The [captured VC menu](captured_navigation.md)
now preserves its original controls and search input; its unsupported ranking and
gateway targets no longer become all-title/demo filters. WiiWare's adapted
bindings and the complete original category flows remain unfinished.

The service now supports exact filters backed by accepted historical fields:
77 publishers, ten platform descriptions and 210 nonempty genre descriptions.
Publisher/platform data covers 835 titles; genre descriptions cover 826. Unknown
titles stay outside named groups. These filters preserve category/search/demo
context through pagination, detail links and back navigation.

The recovered system picker contains ten system codes. Known codes are paired
with their captured platform descriptions, including `FC/NES`, `SFC/SNES` and
`VCA`. This capture is from the US region and has no MSX row; it does not supply
the complete Japanese picker or its labels.

The genre picker contains 21 codes, including service classifications as well
as genres. Those codes are **not** equivalent to the 210 freeform descriptions.
The research filter is therefore named `display_genre`; canonical `genre=ACTION`
requests are rejected until a source-backed mapping exists. No guessed mapping
or replacement picker screen has been added.

`B_17.jsp` (publisher), `B_23.jsp` (category gateway) and `B_27.jsp` (WiiWare menu)
are absent from this collector backup. The modified interactive archive has a
WiiWare menu, but it does not resolve the missing original Japanese captures.
Recovering those pages, Japanese strings and native interactions remains work.

The later [all-region audit](../../research/wii_shop_navigation_recovery_20261025.md)
found a genuine generic no-results view. Nonblank name queries with zero total
matches now reuse its captured markup and English notice. It was recorded from
title-ID selectors, so this does not establish the exact Japanese keyword or
search-again flow. Out-of-range pages and blank queries retain their existing
experimental behavior rather than being labeled as zero-match searches.

The [contract report](../../research/wii_shop_category_contract_validation_20261025.json)
records group coverage, all-group pagination checks and three live HTTPS
filter/detail/back checks. It explicitly leaves the original picker UI, genre
code mapping and native visual verification unverified.

The offline query tool accepts `--title-metadata`, `--publisher`, `--platform`,
`--display-genre` and `--facets`. These inspect accepted data without claiming
that the native category flow is restored:

```powershell
python -m tools.query_wii_shop_catalog private/wii_shop/mariocube-catalog-ids.json --title-metadata private/wii_shop/title-metadata-v2/metadata.json --facets publisher
```
