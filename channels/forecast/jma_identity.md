# Explicit JMA area membership and experimental catalog pins

`jwc24.jma_identity` checks the source memberships that can be established from
retained data while preserving the identity gaps that remain. It does not
choose a native city, match names, find a nearest station, publish weather,
change a profile or establish Nintendo provenance.

## Published provider hierarchy

The official public JMA client uses
`https://www.jma.go.jp/bosai/common/const/area.json` for its area hierarchy.
The typed parser binds its exact bytes, URL and retrieval metadata through a
`SourceReceipt`, then checks both directions of every parent/children edge:

```text
class20 municipality -> class15 group -> class10 forecast area -> office -> center
```

Class names form part of identity. A class15 and class10 may have the same
numeric code without being the same node. Names, published IDs and raw node
metadata are retained. The explicit class20 lookup follows these checked
provider relationships. It does **not** establish that an experimental native
catalog row is the municipality supplied by the caller. The captured metadata
does not supply a native-city crosswalk or station-to-municipality geometry.

The October 28, 2026 capture has 2,391 nodes: 11 centers, 58 offices, 142
class10 areas, 375 class15 groups and 1,805 class20 municipalities. All 2,380
parent/children edges pass reciprocal checks. This is historical metadata
verification, not a current nationwide weather refresh or coverage claim.

## Exact catalog pinning

The experimental catalog reader preserves numeric native keys, labels,
coordinates, zoom values and raw JSON row metadata. Existing blank region or
country labels remain blank. A row pin contains the **whole catalog digest**,
row ordinal, full numeric key and canonical row digest. A pin fails against
another catalog, a reordered/changed row, a changed key or modified metadata.
No coordinate is changed or used as a containment test.

The caller must retain a source classification and origin/evidence references.
Accepted classifications describe third-party catalogs, historical native-format
downloads, unverified recovered originals, or synthetic fixtures. They are
supplied provenance claims; a digest checks supplied bytes, not the truth of
those claims. The validator never upgrades a classification to verified
Nintendo origin.

The existing private 283-row Japanese experimental catalog comes from the
retained WiiLink24/ForecastChannel `weather.xml` checkout and JWC24's importer.
It is a third-party catalog. A retained WiiLink native-format response contains
653 globe locations, including 281 Japanese rows. It is not independent
Nintendo provenance merely because the native parser accepts its format.
Their keys differ: Tokyo is `(1, 1, 1)` in the current experimental Japanese
catalog and `(1, 2, 1)` in the retained response. The private replay exercises
that real mismatch and rejects an old pin. Reusing only a numeric key would
silently bind the wrong catalog.

A bounded read-only check of the retained post-first-run August 2, 2026 VFF
snapshot found no Forecast downloads, only an empty `MB` entry. A separate
retained decoded `vff-audit-3.BIN` contains the 653/281 catalog family; its
original Nintendo source is unestablished. No genuine historical Nintendo
location catalog emerged from these exact retained inputs. This does not
prove that no other archive can contain one. Original files stay private.

## Separate assessment statuses

An assessment requires an explicit catalog row pin, a provider class20 ID and
an explicit forecast temperature-point ID. It joins that point only through
the exact published office/class10 association. Its observation-catalog
membership and, when supplied, the exact station metadata remain separate.
Station metadata must use the same source catalog receipt and point ID.

| Checked or unresolved fact | Result |
| --- | --- |
| Catalog row digest/key/labels/coordinates | Validated against supplied exact catalog |
| JMA class20-to-office hierarchy | Validated reciprocal provider membership |
| Point in the published office/class10 temperature association | Validated source association |
| Experimental native city is the caller-supplied municipality | Unresolved external identity evidence |
| Station measurement represents that native city | Unresolved station-to-native-city identity |
| Catalog is an original Nintendo catalog | Unverified by this validator |
| Native publication ready | False |

Even identical city/station names and coordinates do not upgrade these
unresolved statuses. This boundary must gain actual external identity evidence
before native city publication can be authorized; successful source parsing or
human-entered IDs alone are insufficient.

## Actual representative case: Takasaki

The experimental row `(1, 11, 2)` retains the label `高崎市`. An explicitly
supplied JMA municipality `1020200` follows the published chain:

```text
1020200 高崎市
  -> 100013 高崎・藤岡地域
  -> 100010 南部
  -> 100000 群馬県
```

The source association for that southern Gunma forecast area uses temperature
point `42251`. The captured station metadata identifies it as **前橋**, Maebashi.
The assessment retains the Takasaki label, regional forecast scope, point ID,
Maebashi station identity and all their receipts separately. It remains pending
for city measurement/publication; it does not call a Maebashi observation a
Takasaki measurement. The native-city-to-municipality crosswalk itself is also
unproved by these inputs.

## Evidence, verification and limits

The actual replay checks separately receipted common-area, association and
station metadata, the exact private experimental JSON, and the retained
third-party native-format response. Synthetic tests cover changed catalogs,
key/index/label/coordinate drift, malformed JSON, false provenance claims,
non-reciprocal hierarchy, explicit point membership and unpromoted identity
statuses. No test sends network requests or accesses a live profile.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_identity
```

The three retained JMA forecast bodies in the bounded source-audit/live/replay
directories are identical captures: both reports have
`2026-10-27T17:00:00+09:00`. They add no actual 05/11 or before-05 response
shape evidence. The synthetic selector/date checks documented in
[jma_source.md](jma_source.md) remain explicitly synthetic for those buckets.

Native payload location binding, original catalog recovery, source age policy,
credit boundary, icons, full rendering and hardware verification remain
separate requirements. Results and capture digests are recorded in
[`jma_identity_validation_20261107.json`](../../research/jma_identity_validation_20261107.json).
