# Nintendo Channel (Japan): initial native investigation

Inspected October 13, 2026. The supplied stock WAD is HATJ,
`000100014841544A`, version 1792, requiring IOS55. All 13 contents were
decrypted and verified against the title metadata by the existing private
extraction tool. The original WAD was not changed.

## Direct evidence

The TMD selects boot index 12, a NAND boot executable with content-file loading
diagnostics. Content index 1 is a plain application DOL with entry point
`0x80004050`. Contents 2 through 11 are U8 archives. Their build-date resource
records December 3, 2010. The title's resource archives
contain search, ranking, software details, video lists, review submission,
download, and history layouts. These names establish intended client features,
not working replacement services.

The main executable contains these original service references:

| Reference | Observed role or limit on interpretation |
| --- | --- |
| `http://entd.wapp.wii.com/wc24data.LZ` | Referenced alongside native WC24 task setup |
| `http://entd.wapp.wii.com/message1` and `message2` | Additional configured service URLs; payload contracts not yet recovered |
| `CSData.bin`, `csdata.LZ`, `wc24dl.vff` | Catalog/download cache names; compression and binary validation need tracing |
| `http://entj.wapp.wii.com/` and its `/0/`, `/3/` roots | Japanese service roots; exact appended catalog paths need tracing |
| Akamai roots pointing to `entjs.wapp.wii.com` and `entjsm.wapp.wii.com` | Separate download roots; do not imply that the media can be replaced with arbitrary MP4 files |
| `https://entjp.wapp.wii.com/`, `https://entjc.wapp.wii.com/` | Additional HTTPS service roots |
| `config.cgi`, `review.cgi`, `getreview.cgi`, `delreview.cgi`, `bookmark.cgi`, `accomplishment.cgi` | Embedded CGI names; methods, fields, and response validation remain unverified |

Private resource indexes record the original archive paths, including
`layout/softInfo.arc`, `layout/movieList.arc`, `layout/moviePanel.arc`, and
`message/promotion_message_J.bmg`. No original assets or private keys are
included in this repository.

## First implementation gate

Trace the native `CSData` load and validation path, WC24 task registration,
and direct catalog download before constructing a replacement payload. Recover
the binary header, size bounds, integrity checks, and software/media references;
then implement an independent decoder and a minimal validated catalog.
Determine the title's boot-stub transfer before interpreting a launch failure.

Review/bookmark/usage submission is a separate task from serving a catalog.
This pass did not install or launch the title, contact original service hosts,
submit user data, or claim that any Nintendo Channel endpoint is restored.
