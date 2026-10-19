# Historical Demae Wii web leads

Checked 2026-10-14. The requested Wayback wildcard page could not be retrieved;
an independent CDX request for demae-can.com/wii/* timed out after 20 seconds.
No archived snapshot, API body or asset was recovered from those attempts.

## Primary sources

- Operator launch announcement, 2009-05-26:
  https://corporate.demae-can.com/news_release/press/20090526.pdf
  Search-indexed PDF text identifies the original Wii promotional page as
  http://demae-can.com/wii/index.html and Nintendo's feature as
  http://wii.com/jp/articles/demae-channel/ . Direct PDF retrieval failed in the
  browsing tool; these are confirmed historical URL leads, not retrieved pages.
- Nintendo's surviving Wii channel overview:
  https://www.nintendo.co.jp/wii/features/wii_channel.html#demae
  Confirms registered-home-address delivery filtering, genre → shop → menu
  ordering and cash paid directly to the delivery person. Distinguishes software
  distribution ending 2017-02-22 09:59 from service ending 2017-03-31.
  Original screenshot remains linked:
  https://www.nintendo.co.jp/wii/features/img/wii_channel/channel_17_pic.jpg

## Contemporary interface evidence

- Launch-day hands-on order report with 33-photo gallery:
  https://s.inside-games.jp/article/2009/05/26/35414.html
  First-person report describes prefecture/municipality/chome selection,
  unavailable shops, waiting estimates, minimum prices, hours, selectable item
  options, requested delivery times, history and Wii Message Board confirmation.
  Treat as interface behavior evidence, not the original server schema.
- Launch-day illustrated walkthrough:
  https://gigazine.net/news/20090526_wii_delivery_service/
  Provides screens of genre/shop/menu/options/comparison/time/history/roulette
  and confirmation mail. Example confirmation screenshot:
  https://i.gzn.jp/img/2009/05/26/wii_delivery_service/Snap17.jpg

## Restoration implications and limits

The original cash-payment restriction agrees with the native parser's supported
payment gate, but it does not establish cash support at today's provider shops.
The Message Board confirmation is a useful integration target for the shared
JWC24 mail service after a genuine order protocol is available. Screenshots can
guide UI validation; they cannot establish API field names, original area IDs,
response encoding, merchant eligibility or modern ordering authorization.

Next archive targets: both HTTP and HTTPS variants of /wii/index.html, its
linked assets, wii.com/jp/articles/demae-channel/, nwapi.demae-can.com and
nwpic.demae-can.com. Their archive coverage remains unverified.
