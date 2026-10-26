# Current Japanese News source follow-up

Checked October 26, 2026. Public primary provider/product/policy pages only;
no publisher article bodies or images were acquired, no subscription or account
was created, and no production News buffer was built, signed or published.
The separate [original-supplier investigation](news_original_provider_options_20261026.md)
covers Mainichi and NTV, with NTV the strongest authenticity candidate; this
follow-up checks practical alternatives and the tempting free-feed paths.

**The strongest alternate technical fit found is a licensed Japanese Reuters
Ready feed. Jiji offers a real Japanese syndication contact route, but its
public XML signage product does not establish full-article rights. Neither
Wikinews nor old Nordot curator/API documentation supplies a verified current,
free Japanese fulltext feed for JWC24.** No provider is selected by this report.

## Suitability and access gates

| Candidate | Verified official offering | JWC24 decision / missing permission |
| --- | --- | --- |
| Reuters Ready Japanese | Japanese ready-to-publish multimedia articles; topics include domestic/world, business, entertainment, technology, sport and lifestyle | Best alternative product fit, conditional on a subscription expressly covering JWC24 console delivery, caching and images. Not a free public feed. |
| Jiji digital-media syndication | Current corporate pages offer news to digital media and a homepage/intranet information-provision contact category | A viable licensing inquiry, not a documented public fulltext API or an existing permission. Ask for full Japanese text/stills and machine-readable delivery. |
| Jiji FITS BOARD | XML data or JPEG file push, short flashes and photo-news | Documented ingestion method, but the 41-character flash product cannot substitute for the original article-reading flow. Fulltext and consumer-console use are not established. |
| Nordot / NEWSjp | Old authenticated API documentation survives; service structure and rights have changed | Do not build against it as a free curator feed. New enrollment, fulltext redistribution and offline-console rights need current written terms. |
| Japanese Wikinews | Read-only historical archive after the all-language closure in May 2026 | Potential explicitly dated archive material under each item's license, not current news. Never advance article dates or present it as live. |
| Other Wikimedia content | Free-license encyclopedic text/media and public APIs with conditions | Does not establish a current Japanese newswire. An encyclopedia/current-events index is not full news-article supply. |

The table's Reuters product facts come from
[Reuters Ready](https://reutersagency.com/content/content-types/reuters-ready/).
Jiji's digital-media scope is stated in its
[company description](https://www.jiji.co.jp/company/aboutus) and
[current services directory](https://www.jiji.co.jp/service/).

## Reuters: actual licensed content delivery, not a scraper

Reuters' [delivery methods](https://reutersagency.com/content-delivery-platforms/content-delivery)
advertise a GraphQL/JSON integration with technical support, plus XML FTP push.
The [Connect product](https://reutersagency.com/content-delivery-platforms/reuters-connect/)
describes subscriptions, flexible commercial models, usage reports and ongoing
support. The public [licensing form](https://reutersagency.com/license-reuters-content/)
requires contact, organization, country, website and content requirements. No
public price or JWC24-specific entitlement was verified. The official developer
documentation URL was inaccessible in this research environment; third-party
OpenAPI catalogs were not treated as a verified current API schema.

The ready-to-publish product's broad marketing language is not a blanket
permission for unsigned visitors to redistribute its website. Obtain the
actual product agreement, Japanese feed coverage and delivery specification.
Confirm consumer consoles/emulators, territories, audience, local VFF retention,
server retention, correction/removal timing, image resize/re-encoding, and use
of the original channel's source-credit display before implementing ingestion.
These are JWC24 requirements to negotiate, not terms this report found granted.

The official [brand attribution rules](https://reutersagency.com/brand-attribution-guidelines/)
are part of the customer's agreement: preserve supplied rights notices and
source/individual credits, preserve dateline/byline for substantially reproduced
text, and prominently credit credited pictures. They also prohibit distorting
editorial meaning and require an indication when the customer translates.
Consequently, automatic omission of a byline, arbitrary truncation or an image
without its photographer credit is not an acceptable default adapter policy.
The exact agreed credit rendering must fit the original native fields; no
replacement screen or invented Reuters logo is authorized here.

## Jiji: separate fulltext syndication from signage and subscriptions

The official [contact form](https://www.jiji.co.jp/contact?type=13) specifically
offers article/photo/video usage inquiries and a homepage/intranet information
service category. It has corporate and individual contract choices but also
requires organization/name/address/phone/email information; that does not prove
a hobby project is eligible for a particular syndication product. No contact
was sent. Fulltext scope, pricing, credentials, quotas, credit format, cache
retention and machine-readable schema remain matters for the provider.

[FITS BOARD](https://www.jiji.co.jp/service/fitsboard) is more concretely documented:
the customer chooses XML data or JPEG output, prepares a receiving server/IP,
and Jiji uploads files. It advertises roughly 100 short flashes daily, each no
more than 41 characters, and 30–40 photo-news stories daily across several
genres. This proves an actual data-delivery business, but not a general fulltext
feed/API nor permission to repackage signage material into public consumer
downloads. The embedded JPEG layouts would also replace the native text/article
experience. Ask about a separate full Japanese text-and-still syndication
agreement instead of buying the wrong product.

Jiji's news website was blocked by robots in the research tool; no alternate
host, proxy or scraper was used to acquire its articles. Its readable corporate
sales pages were sufficient to identify the legitimate inquiry route.

## Nordot: current corporate changes invalidate old free-curator assumptions

Nordot's [official February 28, 2024 notice](https://nordot.jp/news/20240228.html)
scheduled the general curation service to stop at the end of March 2025. Only
selected existing traffic-producing curators, already notified, were offered
continued service; publisher-side distribution continued. Its
[October 1, 2026 announcement](https://nordot.jp/news/20261001.html) says the
Nordot-business rights and obligations transferred to Kyodo Digital. This does
not establish that JWC24 can newly join an old free curator program.

The still-readable [API overview](https://developer.nordot.jp/ja/overview)
documents CMS-issued unit-scoped bearer tokens, HTTPS, JSON responses with an
`ok` flag even on HTTP 200, and a 60-calls/minute limit. Documentation availability
does not establish active new-client access or content rights. No token was
requested and no article API call was made.

Current [NEWSjp reader terms](https://legal.nordot.jp/terms_newsjp/) dated
July 1, 2025 prohibit reusing the service or its data. The
[publisher agreement](https://legal.nordot.jp/content_agreement_newsjp/) licenses
full articles for the described NEWSjp/nordot.app service, while its external
headline package comprises a headline, the first 50 body characters and the
first picture. The [named partner appendix](https://legal.nordot.jp/content_agreement_newsjp_appendix/)
is not an open fulltext redistribution grant. A publisher uploading its own
content and a new console service consuming other publishers' content are
different roles. Do not use content-holder API body fields as a route around
the curator/public-site limits. Ask the current operator explicitly about a
JWC24 fulltext/still-image agreement, caching, attribution and withdrawals if
this option remains desirable.

## Wikimedia: archives are reusable under conditions, but no current Wikinews

The [Japanese Wikinews main page](https://ja.wikinews.org/wiki/メインページ)
states all language editions closed May 4, 2026. The
[Wikimedia Board's archived announcement](https://meta.wikimedia.org/wiki/Wikimedia_Foundation_Board_noticeboard/Archives/2026)
independently confirms the read-only transition and continued archive/dump
access. Search results for future/month index pages are not evidence of new
published reporting. No archive article was downloaded in this pass.

The Japanese site's current footer identifies most post-September-25-2005
text as CC BY 4.0, with exceptions. That must be checked for each selected
revision; do not automatically substitute Wikipedia's license or assume all
media uses the article's text license. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
permits redistribution/adaptation subject to credit, the license link,
change indications and no extra legal/technical restrictions. The
[Commons reuse guide](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)
requires checking each file's actual author/license and warns that not all
Wikimedia-hosted images have interchangeable terms. Native image credit and
caption fields could carry approved attribution; their rendered adequacy still
needs verification. Only explicitly labeled historical use is suitable here.

For any later authorized Wikimedia ingestion, the
[official access policy](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy)
requires an identifying User-Agent/contact and applicable reuse terms. Current
[2026 rate-limit guidance](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)
says use no more than three concurrent requests and respect `Retry-After`;
limits can change. No account or API traffic was needed for this conclusion.

## Mapping a future licensed feed into the recovered native records

This is JWC24 integration analysis, not a claim about any provider's unpublished
schema. The [native format evidence](../channels/news/format.md) already
separates article title/body, source name/copyright, image credit/caption,
publication/change times, topics and location records.

| Provider input that must be supplied | Native destination / policy |
| --- | --- |
| Stable article identity and revision/correction identity | Stable record identity plus coherent topic references; never derive new editorial history from a fetch time. |
| Full Japanese headline/body, byline and dateline | UTF-16BE native text fields, preserving supplied wording and required credits. A provider-approved shorter story is needed if the native body bound is exceeded; do not silently rewrite or summarize. |
| Source name and copyright/required attribution | Existing source records, with logo only when explicitly supplied/licensed. Private permission references are not a substitute for reader-visible attribution. |
| Licensed still image, credit and caption | Original image records with approved conversion; test actual native decoder/capacity separately. No placeholder art or stripped photographer credits. |
| Publication/update/expiry and withdrawal state | Preserve factual article dates; enforce permission retention/corrections. Publication-window validity alone does not prove current news. |
| Provider taxonomy / verified geographic metadata | Reviewed mapping to recovered original categories and globe/location meanings. Never invent coordinates or populate every category with unrelated content. |

Best next step: compare the original-supplier Mainichi/NTV routes already under
investigation with one narrowly scoped Reuters/Jiji licensing specification.
If a no-cost feed is mandatory, this research has **not** established an active
fulltext Japanese source with sufficient redistribution rights. Do not fill
the gap with RSS excerpts, an AI-generated digest, an old archive presented as
current, a copied public article, or a search/database subscription.

The next actionable provider artifact is an authorized delivery specification
and sample, with text/image rights, native credit rendering and offline-cache
terms documented. Only then should an ingestion adapter and independent native
record builder be implemented and exercised through the existing coherent
24-slot publication gate. Provider permission does not by itself resolve the
remaining native trust, image-decoder, capacity and original-UI verification.
