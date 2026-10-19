# Nationwide offline address directory

`tools/import_japan_post.py` imports Japan Post's official UTF-8 CSV into the
ignored `private/demae/postal/postal.sqlite` database. It verifies archive size,
CSV structure, prefecture coverage and minimum nationwide record count before
publishing the database. `--archive` accepts an already downloaded official ZIP
when the local Python certificate store cannot validate the download.

`jwc24.japan_post.lookup` preserves all candidates for a seven-digit postcode,
including leading zeroes. It never chooses a house number or resolves an
ambiguous postcode automatically. Municipality default rows remain marked as
`municipality_default` rather than being treated as a named town.

`areas` navigates prefectures, municipalities and postal towns with public JIS
identifiers. These identifiers have not been established as the original Demae
API's area codes. Database readers close their handles explicitly so Windows
does not retain a lock that prevents subsequent publication.

Offline inspection:

```powershell
.venv/Scripts/python.exe tools/inspect_postal_directory.py
.venv/Scripts/python.exe tools/inspect_postal_directory.py --parent JP-10
.venv/Scripts/python.exe tools/inspect_postal_directory.py --postal 3770813
```

The directory is not yet connected to the native HCCJ encrypted postal download
format or HCHJ address-selection flow. Postal coverage does not establish
restaurant delivery coverage, payment support, menus or ordering capability.

`tools/build_demae_municipality_fixtures.py` builds all 47 prefecture municipality
responses for offline inspection. Each uses nonempty CDATA scalars, an exact
allocation count and synthetic `TEST-M-xxxxx` identifiers within the traced
15-byte area-code capacity. The complete batch is validated before writing.
The fixture harness now supports these responses when started with
`--postal-database private/demae/postal/postal.sqlite`. The shared-profile
launcher enables this option when that database exists. It validates all 47
responses and holds a memory snapshot before listening; request handling never
queries the database or an upstream provider. Native acceptance is unverified.
Town-selection requests remain unsupported. The imported snapshot contains
1,892 distinct municipality records;
this includes postal administrative distinctions rather than claiming that
Japan has that many independent municipalities.

Source: https://www.post.japanpost.jp/service/search/zipcode/download/utf-zip.html

`tools/audit_demae_towns.py` writes a private, lossless candidate registry for
town selection. Experimental identifiers include municipality, postcode and
full town name in their digest, preventing shared postcodes from collapsing
distinct towns. Identifier collisions abort the audit. Names longer than the
traced 31 UTF-16-unit final label capacity and municipality-default records are
flagged for review, never silently shortened. This conservative eligibility
check does not establish native encoding or delivery-area compatibility; town
responses are still not served.

`tools.build_demae_town_fixture.build_towns` now produces inspected terminal
town rows (`isNextArea=0`) for offline checks. It returns excluded candidates in
a separate report, preserving full source records. These terminal semantics
still require native completion tracing before enabling the HTTP route.

The fixture server accepts every well-formed seven-ASCII-digit postal query
and returns the traced status-13 manual-selection fallback. It does not claim a
successful postal match or fabricate `selectedArea`. Duplicate parameters,
wrong lengths and non-ASCII digits remain rejected; postal values are never
logged. This removes the prior HTTP-400 failure for real postcodes while lookup
integration remains unfinished.

Further native tracing established that address confirmation converts the
selected area code as a base-10 number before local personal-data validation.
The experimental `T-...` identifiers must therefore remain offline-only.
Candidate `label_eligible` describes display capacity alone; `native_selectable`
is explicitly false for every candidate until decimal area-code mapping and
the subsequent validation contract are recovered. Town HTTP routing remains
disabled.
