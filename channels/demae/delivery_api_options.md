# Official Japan delivery API options

Checked on **2026-10-13** using provider documentation and announcements.
No account was created, provider contacted, integration installed, delivery
requested, or payment made.

**Finding:** among the four providers below, this pass did not verify a free,
public consumer API that can search arbitrary Japanese restaurants, retrieve
their orderable menus, and place an order from a replacement Demae frontend.
Merchant integrations exist, but their access and purpose differ from that
consumer use case. This is a bounded research finding, not proof that no such
agreement could ever be negotiated.

| Provider | Official API/access evidence | Cost evidence | Fit for this project now |
| --- | --- | --- | --- |
| Demae-can / 出前館 | Published API terms describe merchant-system and aggregator integration, with advance registration. They are not public consumer ordering documentation. | Integration/development costs are borne by the merchant/aggregator; API access fees and a free tier were not established. | No verified self-service consumer catalogue or order API. |
| Uber Eats Marketplace | Store/menu synchronization and incoming-order fulfillment for partners. Production scopes require Uber approval; non-fulfillment use cases require an aligned business agreement. | API access pricing/free tier was not established in the inspected docs. Food and fulfillment costs are separate. | No verified public consumer search/order interface suitable for immediate integration. |
| Wolt Marketplace | Partner/merchant API documentation exists, with contract and onboarding before access. | Official FAQ says APIs are free. This does not mean unrestricted access or free deliveries. | Japan service ended in March 2026, so it is not a current Japan delivery option. |
| menu | Merchant terms discuss external order-management integrations; no public consumer API or signup flow was verified. | API pricing/access terms remain unknown. | Official company notice says service ended September 30, 2026. |

## Primary sources

- **Demae-can:** [official membership/API terms](https://corporate.demae-can.com/terms/membership_terms.pdf), API terms beginning on PDF printed page 26. The API-user and aggregator definitions, advance registration, merchant integration, and development-cost clauses establish the restricted integration model. No API specification was obtained.
- **Uber Eats:** [getting started](https://developer.uber.com/docs/eats/guides/getting-started) and [authentication/scopes](https://developer.uber.com/docs/eats/guides/authentication). These describe store/menu/order management and approved production access, rather than an open consumer marketplace browser.
- **Wolt:** [API FAQ](https://developer.wolt.com/docs/faq), [marketplace introduction](https://developer.wolt.com/docs), and [Japan shutdown announcement](https://press.wolt.com/ja-JP/262095-wolt/). The February 25 announcement gives March 4, 2026 as the last date of normal Japan service. Global API documentation remaining online does not establish current Japan availability.
- **menu:** [company shutdown notice](https://corp.menu.jp/), [merchant site notice](https://store.menu.jp/index.html), and [merchant terms](https://store.menu.jp/shopterms/). The company notice gives September 30, 2026 as the service end date; the older integration terms should not be treated as current availability.

## Courier APIs are a separate capability

Uber Direct can dispatch a courier for an existing merchant's goods. It does
not provide a replacement consumer restaurant marketplace or make a restaurant
prepare an arbitrary order. The [official overview](https://developer.uber.com/docs/deliveries/overview)
distinguishes Direct from Eats Marketplace. The [Direct setup guide](https://developer.uber.com/docs/deliveries/get-started)
requires production approval and billing, and its quote endpoint returns a
delivery fee. Japan self-service eligibility and the project's applicable
commercial pricing remain unverified. It is not a free delivery alternative.

## Practical source boundary

Use a documented restaurant-directory source for browse/search while keeping
delivery eligibility, orderable dishes, stock, exact prices, and checkout
disabled until a provider contract supports them. Recruit's
[Hot Pepper Gourmet API reference](https://webservice.recruit.co.jp/doc/hotpepper/reference.html)
documents keyed restaurant search by location/name and listing fields. It does
not document consumer delivery-order placement. A restaurant listing or dinner
budget is not an orderable menu or a delivery quote.

No official, free consumer ordering API for an individual Japanese restaurant
chain was verified in this four-provider pass. Chain partnerships or a
merchant-owned ordering system may support a later integration, but this
research does not establish their access, price, or compatibility. No unofficial
mobile endpoints or scraping are proposed.

## Domino's published read-only API lead

A follow-up examined the [Postman public workspace](https://www.postman.com/dpg-dpd/public-apis/overview)
and its read-only menu collection. The publisher profile identifies itself as
**Domino's Pizza Group Ltd**, not Domino's Pizza Enterprises. It explicitly
requires prior approval from the Domino's UK team to use the exposed APIs.
See [the publisher's access statement](https://www.postman.com/dpg-dpd).
The profile is publisher-provided evidence; a separate corporate-site link
verifying ownership of this Postman account was not located in this pass.
The [Pizza Group corporate description](https://corporate.dominos.co.uk/about-us/how-we-work)
identifies its franchise territory as the UK and Ireland. That independently
supports the regional distinction, without proving Japan API compatibility.

The [complete-menu request](https://www.postman.com/dpg-dpd/public-apis/request/nccl5ez/get-the-complete-menu-for-a-store)
documents `GET https://{{baseUrl}}/api/menus/v1/menus/complete-menu/{{storeId}}`.
The retrieved page leaves the host and store ID as variables and supplies no
selected environment. Actual base URL, authentication/key requirements, access
fees, quotas, licensing, and Japan coverage remain **unverified**. Publicly
viewable documentation does not establish free or approved API use.

Companion requests are explicitly UK-oriented: [image definitions](https://www.postman.com/dpg-dpd/public-apis/request/oaeim01/get-all-image-definitions-uk)
use a UK content path, and [store details](https://www.postman.com/dpg-dpd/public-apis/request/kma62jx/get-a-store-details-using-customer-latitude-and-longitude)
show a `UK-PC` location token. This supports a UK integration lead, not proof of
Japan exclusion or inclusion. No checkout contract was established from the
read-only collection. No live menu/store endpoint was called; no address or
order was supplied. Keep this lead on the list, but do not select it as an
available free Japan menu/ordering provider without further provider evidence.
