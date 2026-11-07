# News Channel restoration gates

Updated November 7, 2026; the initial baseline was October 26. The Japanese
HAGJ v7 application DOL is available as a
read-only private input. Its SHA-256 is
`8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852`.
The original channel's news service has not been restored.

The actual initializer at `0x800081D4` passes its two integer arguments to
the URL formatter at `0x8000825C` in reversed register order: caller argument
five becomes the first `%d`; caller argument four becomes the second `%03d`.
The stored template is the historical `news.wapp.wii.com/v2/.../news.bin`
reference recorded in the [baseline](README.md). This static check does not
identify those arguments as region/language or establish valid values, task
registration, download acceptance or a response container.

Likewise, the internal `news.bin.00` through `.23` strings remain filename
references. Their relationship to live data, task rotation or test data is
unverified. They must not be treated as 24 required task registrations.

The [structural decoder and guarded native comparisons](format.md) now verify
the decompressed header, CRC, table layout and selected article-reference path.
They deliberately leave signatures, native decompression, cross-hour completeness
and UI use unverified. Subsequent [explicit record generation](record_builder.md),
[signed publication/delivery](publication.md), [task caller/slot checks](task_registration.md)
and [headline consumer comparisons](headline_model.md) add independent components,
not a completed native flow. Public restoration material supplied separately attributed
leads, rather than being treated as original Nintendo source.

The next gates are the original first-run registration/caller arguments;
outer WC24 delivery/trust and native envelope/decompression acceptance;
cross-hour loading and UI consumption; and licensed current Japanese news input
with provenance. The [complete Global Voices Japanese adapter](globalvoices_source.md)
preserves actual article structure, separate contributor roles and source dates.
It is supplemental feature coverage; third-party media/quotations and native
attribution/rendering remain pending, so it cannot publish a native News payload.
The [original article-text check](article_text_contract.md) now verifies exact
wire-derived body/source-credit pointers, three native text handoffs and bounded
UTF-16 unit handling. Actual font/layout/rendering and working links remain
unverified. Only then can one coordinated native check
exercise banner headlines, category selection, globe, article text/images,
dates, refresh and failure handling.

No arbitrary XML, JSON or successful empty response is served as news. No
first-run task was invented from the URL template. No emulator/profile, task
database, actual Wii backup or original source file was changed in this pass.
Current content acquisition and all native News UI checks remain unfinished.
