# Offline Shop preview preflight

The Shop's private packs can now be assembled and checked without starting a
server, opening Dolphin, or reading NAND/device credentials:

```powershell
.venv/Scripts/python.exe -m tools.preflight_wii_shop --progress
```

The server and this command use the same pack loader. Existing fingerprint,
catalog-association and source-pack checks run before pages are rendered. The
command then renders every catalog page, every retained title detail and each
available captured controller/More Details page. It resolves static image,
script and stylesheet references, inline CSS URLs, and transitive CSS URLs.
Repeated dependencies are read once. Count, byte and CSS-depth limits bound the
check; exceptions and reports do not echo private pack paths or page bodies.
Every pack path can be overridden with its corresponding command-line option.
The optional progress flag writes only route counts to stderr; the final JSON
report remains on stdout for a coordinated validation runner.

Exit status zero means these offline checks passed for the current experiment.
Missing routes/resources and external display dependencies produce a nonzero
exit status and counted failures. They are never filled with invented content.
Original capture gaps are reported separately because the existing experiment
still has documented fallback templates and blank artwork slots. A locally
available spacer image does not establish that the corresponding title artwork
was recovered.

This does not execute JavaScript or follow ordinary anchor links. Dynamically
selected resources, hover handlers, native keyboard/input, sounds, page trust,
HTTP/TLS, account startup, ownership and installation need separate checks.
The report always leaves complete original Japanese fidelity, native rendering
and commerce unverified. The [completion list](completion.md) remains controlling.

The [October 26 snapshot check](../../research/wii_shop_offline_preflight_20261026.json)
rendered all **2,605 HTML routes** and checked **3,374 static display dependencies**.
Every HTML route succeeded. Two local font references (`/font2.ttf` and
`/category/font2.ttf`) failed, and four display references point to the external
third-party host `wiishopchannel.neocities.org`. No request was sent to that host.
These occur in retained modified-template styles. No original Nintendo font or
replacement image was inferred or substituted. Earlier HTML/image/stylesheet
route checks did not inspect these inline style dependencies. The preflight
correctly remains failing; dependency recovery or verified original templates
are still needed.
