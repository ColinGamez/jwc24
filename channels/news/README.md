# News Channel (Japan)

The Japanese News Channel follows Forecast restoration and reuses JWC24's
native WC24 scheduling, delivery, and validation foundation.

## Installed client baseline

- Title ID: `00010002-4841474A` (`HAGJ`)
- Version: `7`
- Required IOS: `31`
- Region: `JPN`
- Installed in the active Dolphin NAND as a bundled system channel

The initial inventory found an empty data directory and no entries in
`nwc24dl.bin`; it did not establish completed first-run setup. That observation
is a snapshot, not a live check of a console or current profile.

## Direct executable evidence

The stock v7 executable contains this URL format:

```text
http://news.wapp.wii.com/v2/%d/%03d/news.bin
```

It also contains internal `TestData/news.bin.00` through `.23` paths. Native
execution now verifies a separate 24-buffer validator, including checksums,
table bounds and selected article references. This does not establish the
actual hourly URL/task mapping or network delivery.

## Offline payload inspection

The [bounded structural decoder and native comparisons](format.md) cover the
decompressed header, six table layouts, text/data spans and local references.
The metadata-only CLI accepts either a private envelope file or decompressed
input:

```powershell
.venv/Scripts/python.exe tools/inspect_news.py <private-news-file>
.venv/Scripts/python.exe tools/inspect_news.py <private-raw-file> --raw
```

Neither a structural pass nor native validator status zero establishes a
signature, current licensed news, accepted WC24 delivery or a rendered channel.
The [explicit bundle check](bundle_validation.md) resolves supplied cross-buffer
references. The [task-registration investigation](task_registration.md) verifies
one native job's 24-subtask intent, local filename construction and reader order;
it does not provision real tasks or turn that evidence into a generic manifest.

## Bring-up order

1. Capture the exact Japanese first-run WC24 task.
2. Extend the recovered structural subset through native envelope verification,
   decompression, cross-hour loading and banner/article rendering.
3. Define licensed/current Japanese-language news inputs with provenance.
4. Generate and independently validate replacement payloads.
5. Verify the banner headlines, globe, categories, and article UI.

No channel binary patch has been applied. Original trust and endpoint handling
remain separate unfinished restoration work.
