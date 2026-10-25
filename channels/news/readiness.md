# News Channel restoration gates

October 26, 2026. The Japanese HAGJ v7 application DOL is available as a
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

The next gates are the original first-run registration/caller arguments;
outer WC24 delivery and file framing; compression/integrity and article/category/
geographic records; licensed current Japanese news input with provenance; and
independent payload validation. Only then can one coordinated native check
exercise banner headlines, category selection, globe, article text/images,
dates, refresh and failure handling.

No arbitrary XML, JSON or successful empty response is served as news. No
first-run task was invented from the URL template. No emulator/profile, task
database, actual Wii backup or original source file was changed in this pass.
Current content acquisition and all native News UI checks remain unfinished.
