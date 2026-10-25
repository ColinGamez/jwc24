# Digicam Print Channel Japan — HCDJ

First service-role audit, October 26, 2026. The owned package is title
`000100014843444A`, version 1024, requiring IOS56. All thirteen extracted contents
match their source TMD sizes and SHA-1 hashes. The Nintendo TMD signature has
not been independently verified. Original files remain private.

## Baseline classification

**Printing is a separate provider/fulfillment service, with WC24 messaging as
another boundary.** Restoring WC24 transport alone cannot supply real print
products, availability, prices, payment, acceptance or physical fulfillment.
None of those facts is fabricated here.

The real application is LZ11-compressed content index1, not the small boot DOL
at index12. Its SHA-256 is
`419c295d0745a5991df5468a4dd1dfc502fdf6c81f47898629f65fbd42e40f7e`.

The original controller at `0x80045ED4` chooses URL templates and uses formatter
`0x800B3EF4`. Synthetic native execution now runs that controller, TLS selector
`0x80046124` and formatter unchanged. Setting selector0 selects **HTTPS** and
constructs both original Fujifilm paths:

- Host `wch.fdinet.fujifilm.co.jp`, path `/wii_svr/WPOperationServlet`
- The same host, path `/wii_svr/WPFileOperationServlet`

These are historical client targets, not a claim of current service availability.
Selectors7 and255 leave both output buffers untouched in the bounded test.
Other selectors are outside this helper's exposed scope. No formatter, TLS
decision or endpoint string is substituted, and no HTTP request is sent.

Application evidence also includes the HCCJ personal-address file selector and
WC24 message-construction/attachment/commit API names. No personal address was
read. Those API references do not establish that an order was accepted, or that
the original print notice reached a Message Board. The shared `network.csv`
resource is localized UI text, not provider configuration. A developer-host
literal is not promoted into the production print service.

## Still required

- Recover actual request/response, session and image-upload contracts, product
  and pricing data, address use, consent and native error behavior.
- Establish an authorized real fulfillment integration before allowing a print
  order; preserve the original native flow and do not simulate acceptance.
- Trace and verify the independent native notice, attachment and receipt path.
- Verify photo/media/controller behavior, display and device integration in the
  coordinated native test pass.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_digicam_provider_urls
```

The native helper reads only a fingerprinted private executable and synthetic
settings. It changes no profile, source WAD, NAND, actual Wii backup, account
or provider setting. See the [native report](../../research/digicam_provider_url_native_20261026.json)
and [shared provenance](../../research/additional_channel_services_20261026.md).
