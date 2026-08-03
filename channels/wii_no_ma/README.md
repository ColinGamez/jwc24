# Wii no Ma / Dokodemo Wii no Ma

This adapter targets the final Japanese Wii no Ma channel and its Nintendo DSi
companion as the first JWC24 service after HBNJ.

## Preserved inputs

- Wii: `Stock WADs/Wii no Ma (Japan) (v1025) (Channel).wad`
  - Title ID: `00010001-4843494A` (`HCIJ`)
  - Version: `1025`
  - Required IOS: `56`
- DSi: `NusDownloader/titles/000300044B44474A/256`
  - Title ID: `00030004-4B44474A` (`KDGJ`)
  - Version: `256`

These files are immutable research inputs. Extracted or patched copies and all
Nintendo content must remain outside the public repository.

## Bring-up order

1. Record the Wii channel's HTTP hosts, paths, request bodies, and response
   expectations from an isolated working copy.
2. Verify the channel's Forecast Channel integration and provide current
   weather for the Wii's configured Japanese area.
3. Implement the minimum registration/bootstrap responses needed to reach the
   room UI using the unmodified v1025 channel.
4. Add catalog and video metadata independently of the original service.
5. Document and reproduce the Wii-to-DSi discovery and transfer protocol with
   KDGJ in an isolated test environment.
6. Add end-to-end validators before exposing either client to real hardware.

The independently verified `/conf/first.bin` route is now declared in the
channel manifest. Later service routes remain outside it until runtime capture.

See `ENDPOINTS.md` for the current evidence map and confidence levels.

## Rakuten Ichiba shop

JWC24 can import the current Rakuten Ichiba Item Search API into Wii no Ma's
paid/theater catalog. Credentials are read only from these environment
variables and must never be committed:

- `JWC24_RAKUTEN_APPLICATION_ID`
- `JWC24_RAKUTEN_ACCESS_KEY`
- `JWC24_RAKUTEN_AFFILIATE_ID` (optional)

Example refresh:

```powershell
.venv\Scripts\python.exe tools\import_rakuten_catalog.py "Wii" `
  --output private\wii_no_ma\shop\rakuten.json --pages 2
```

Rakuten returns at most 30 products per request. `--pages` imports additional
pages sequentially with a delay that respects the one-request-per-second app
limit. Wii-facing lists remain capped at 64 entries; category pagination is
used when exposing larger cached catalogs.

The channel displays the cached catalog through its existing shop/theater
screens. Purchasing remains an external Rakuten HTTPS handoff; JWC24 does not
collect customer credentials, addresses, or payment data.
