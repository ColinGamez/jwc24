# News source investigation: original Japanese suppliers

Checked October 26, 2026 after the owner requested investigation of a suitable
Japanese source. This records published offerings and access gaps. It is not a
feed license, a signed agreement, proof of current enrollment, or an enabled
production source. No accounts, purchases, contacts or publisher-article imports
were made.

## Closest historical match: Nippon TV

Nintendo's February 15, 2007 developer interview explicitly identifies Mainichi,
Nippon TV and overseas reporting organizations as content suppliers, with
provider-specific formats normalized on the server. That corroborates provider
identity; it does not authorize JWC24 reuse.
[Original Nintendo interview](https://www.nintendo.co.jp/wii/staff/news-channel/articles/index.html).

Nippon TV's own January 26, 2007 announcement separately confirms that it supplied
article text and still pictures to the Japanese Wii News Channel.
[Original NTV announcement](https://www.ntv.co.jp/info/news/341.pdf).

The official NTV syndication page is accessible and describes a feed of roughly
60 stories per day across society, politics, economics, international, culture/
entertainment and sports. It lists titles up to 20 characters, summaries up to 120
and bodies up to 3000, plus requested video/still formats. Pricing is by
consultation. The page is undated; current enrollment, exact delivery schema and
these limits must be confirmed with the supplier rather than assumed from its
continued availability.
[Official NTV syndication description](https://www.ntv.co.jp/news24/contact/).

The current public NTV news-site terms, available in the official indexed page,
prohibit automated collection without advance permission and restrict copying/
redistribution beyond personal enjoyment. Direct retrieval of that terms page
was blocked by robots; the restriction was not bypassed. A consumer webpage is
therefore not our proposed ingest interface.
[Official public-site terms](https://news.ntv.co.jp/pages/kiyaku).

**Assessment:** NTV is the strongest authenticity-first licensing candidate.
This is a project inference from historical participation and the published
text/still/general-news offering, not a claim that NTV has approved JWC24 or
provides a free public API. No machine-feed endpoint or credentials are known.

## Mainichi: authentic candidate, technical interface unverified

Mainichi's official rights guide directs reuse through an application/permission
process, with charges and conditions where applicable. It links corporate news
delivery separately from consumer subscriptions and clipping. The corporate
feed link could not be opened in this research tool; no delivery schema or
access entitlement was obtained.
[Mainichi official reuse guide](https://www.mainichi.co.jp/database/usage_guide.html).

**Assessment:** historically appropriate, but a general digital subscription or
RSS reader access should not be treated as JWC24 distribution permission.
Pricing for the actual console/service use is unknown.

## Evidence needed before an adapter

A suitable agreement and actual sample would need to settle article/image
redistribution to a custom Wii service, background download and console-side
caching, expiry/withdrawals/corrections, attribution and provider identification,
image conversion/resizing, territory/audience and authentication/rate limits.
No messages have been sent to either supplier. Obtaining a quotation or account
is outside this read-only investigation.

The adapter should preserve supplied IDs, publication/update dates, titles,
article text, credits and image associations. Category mapping requires explicit
comparison with native Japanese genre IDs; published vendor genre names do not
establish those numeric IDs. Globe coordinates must come from evidence, with
native behavior for absent locations recovered before using a fallback.

The existing code builds signed native files from explicit supplied buffers;
it does not yet turn an arbitrary vendor article feed into complete native
records/images. Access to a feed is therefore an input requirement, not proof
that the channel is already restored.

See [the alternative-source review](news_source_followup_20261026.md) for
current Reuters/Jiji offerings and why historical open/community options do not
automatically provide a usable current Japanese fulltext source.
