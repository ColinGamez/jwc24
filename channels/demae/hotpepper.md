# Hot Pepper directory provider

The read-only provider uses the documented Gourmet Search `/gourmet/v1/` API,
with UTF-8 keyword search, JSON output, one-based `start` and `count` from 1 to
100. This is separate from the store-name search API, whose page limit is 30.
An API key is required. See the [official reference](https://webservice.recruit.co.jp/doc/hotpepper/reference.html).

Set `JWC24_HOTPEPPER_API_KEY` locally, then explicitly import a cached page:

```powershell
.venv/Scripts/python.exe tools/import_hotpepper_catalog.py --keyword '高崎 和食' --count 100
```

No signup, key acquisition or live keyed fetch was performed. The key is read
from the environment and is not written into the catalog or printed in request
failures. Publication is atomic, private and only occurs after successful
response validation. Existing caches survive failed imports. Network responses
are bounded to 2 MiB; the CLI fetches one page per invocation rather than
requesting the provider during Wii interactions.

Normalized records contain stable source-prefixed IDs, name, address, genre,
coordinates, source-page URL, photograph URL and descriptive budget text. Budget
text is not a menu-item price or minimum order. Menu items and delivery
availability remain unknown; ordering is unsupported. No native Demae response
or server route is implemented by this importer.

The cached attribution metadata carries the required text/link credit and
photograph credit. Any future display must render those credits as specified
in the [official usage guideline](https://webservice.recruit.co.jp/doc/hotpepper/guideline.html).
Photos are referenced by URL, not downloaded by this importer.

Six offline tests verify UTF-8 query encoding, pagination limits, bounded
reading, stable duplicate handling, invalid coordinates and URLs, budget
semantics, safe failure messages and preservation/publication of cached data.
