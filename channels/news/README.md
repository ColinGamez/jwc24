# News Channel (Japan)

The Japanese News Channel follows Forecast restoration and reuses JWC24's
native WC24 scheduling, delivery, and validation foundation.

## Installed client baseline

- Title ID: `00010002-4841474A` (`HAGJ`)
- Version: `7`
- Required IOS: `31`
- Region: `JPN`
- Installed in the active Dolphin NAND as a bundled system channel

The title currently has an empty data directory and no entries in
`nwc24dl.bin`, indicating that it has not completed its first-run setup in this
NAND.

## Direct executable evidence

The stock v7 executable contains this URL format:

```text
http://news.wapp.wii.com/v2/%d/%03d/news.bin
```

It also contains internal references for `news.bin.00` through `news.bin.23`,
which suggests a multi-part or rotating test corpus. Runtime task capture and
format validation are required before implementing delivery.

## Bring-up order

1. Capture the exact Japanese first-run WC24 task.
2. Recover the `news.bin` container, compression, and record formats.
3. Define licensed/current Japanese-language news inputs with provenance.
4. Generate and independently validate replacement payloads.
5. Verify the banner headlines, globe, categories, and article UI.

No channel binary patch is planned for the initial restoration.
