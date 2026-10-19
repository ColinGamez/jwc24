# Restaurant data sources for Demae

Checked October 13, 2026. The practical no-key starting point is a small,
explicitly refreshed OpenStreetMap restaurant-directory snapshot. A first live
Takasaki-area query produced 221 named restaurant/cafe/fast-food locations and
44 distinct explicitly tagged chain brands. This is directory data, not proof
that those stores deliver or accept an order through this project.

## Implemented no-key import

```powershell
.venv/Scripts/python.exe tools/import_osm_restaurants.py --bbox 36.28 138.94 36.38 139.08 --output private/demae/catalog/takasaki-osm.json
```

The importer limits query area and response size, rejects partial Overpass
results, deduplicates canonical OSM identifiers, and publishes atomically.
Use the cached file for local browsing work; do not query a public Overpass
server for every Wii interaction. The [operator's usage guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)
describes shared capacity and discourages relying on public instances as a
large public application's backend. Broader deployment needs a suitable hosted
service, self-hosted instance, or periodically imported data extracts.

The cache retains OpenStreetMap attribution and its
[license link](https://www.openstreetmap.org/copyright). Any future native
presentation must display the required attribution. Raw delivery tags are
preserved as source metadata; current delivery availability, orderable dishes,
minimum order price and ordering support are never inferred from them.

## Hot Pepper Gourmet

Recruit's [documented API](https://webservice.recruit.co.jp/doc/hotpepper/reference.html)
provides Japanese restaurant names, addresses, genres, photos, opening-hours
text and provider links. An API key is required and none was configured when
this pass started. Its directory/dinner-budget fields do not establish menu
prices or delivery eligibility. The provider's
[announcements](https://webservice.recruit.co.jp/) say food master APIs ended in
2018, so those discontinued endpoints must not be used as a menu feed.

The [usage guidelines](https://webservice.recruit.co.jp/doc/hotpepper/guideline.html)
require provider credit, additional image credit, and impose restrictions on
restaurant-funded sites and reselling the restaurant information itself.
Registration and any applicable provider terms remain the account owner's step.
No API key or credentials are stored in the public repository.

The read-only Hot Pepper adapter and private one-page importer are implemented
in `jwc24/hotpepper.py` and `tools/import_hotpepper_catalog.py`. Once the account
owner has configured `JWC24_HOTPEPPER_API_KEY` locally, an explicit keyword
import can refresh the cache. The adapter stores provider/image attribution,
keeps dinner budget as descriptive text, and sanitizes credential-bearing
network errors. It was tested with provider-shaped fixtures; no live fetch was
made without a key.

## Delivery and actual menus

[Delivery API findings](delivery_api_options.md) distinguish approved merchant
integrations from public consumer APIs. No free public Japan consumer ordering
API was verified. A directory listing must not be presented as a delivery quote,
current menu, available stock, or successful checkout. Native Demae XML mapping
and in-game acceptance are additional work; the new directory importer has not
restored HCHJ's startup or ordering flow.
