# Demae Wii Message Board notice: evidence and limits

Read-only review on 2026-10-15. No mail was sent and no personal mailbox content
was read. Sources are the locally inspected HCHJ v512 resources, local RevoEX
SDK source, and the current Dolphin mail receiver source.

## Plain notice that the current receiver supports

Use standard MIME fields: `From`, `To`, `Date`, `Message-ID`, `Subject`,
`MIME-Version`, `Content-Type`, and `Content-Transfer-Encoding`, with CRLF
line endings. A public sender address with an ASCII display name such as
`JWC24 Demae` can identify the replacement service without claiming to be a
Wii friend or the original ordering provider.

The RevoEX charset table in `NWC24Parser.c` explicitly includes `utf-8`,
`utf-16be`, `shift_jis`, and `iso-2022-jp`; its encoding table includes
`base64` and `quoted-printable`. UTF-8 text with base64 transfer encoding is
therefore a supported vocabulary for a Japanese body. Header encoded-word
rendering and Japanese display names still need native verification; an ASCII
sender/subject avoids that additional uncertainty for the first notice.

A notice must state the confirmed event precisely. A user clicking “completed”
after visiting the provider can support a **user-confirmed completion** notice;
it does not establish provider acceptance, payment settlement, or delivery status.

## App ID header: avoid an unsupported association

The existing Dolphin receiver's `PopulateEntryMetadata` recognizes the real
header `X-Wii-AppId` in the format decimal destination, eight hexadecimal app-ID
digits, and four hexadecimal group digits. This is observed parser behavior,
not a proposal for a new header.

The same receiver identifies a public sender when the `From` address does not
contain a Wii friend address. Such mail defaults to app ID zero. Its source
comment explains that a nonzero public-mail app ID whose upper 24 bits differ
from the running title can be rejected by RevoEX. Setting an HCHJ app ID on a
plain public Message Board notice could consequently make it unavailable to the
Wii Menu. Keep the current public notice unscoped unless native handling is
verified. No speculative `X-Wii-*` branding fields are warranted.

`X-Wii-Cmd: 80010001` is a friend-registration command handled separately by
the existing mail server. It must not be copied into checkout notices.

## Original artwork and channel-jump evidence

HCHJ's bundled `NWC24.arc` contains `thumbnail_LZ.bin`, `letter_LZ.bin`, and
`chjump.bin`. The last is a 34-byte `ChJp` object with one block and target title
`000100014843484A` (HCHJ). Its block is at offset 32 with length 2. This proves
that the channel packages a native channel-jump object; it does not establish
the MIME attachment arrangement or how a replacement notice should reference it.

The SDK's MIME vocabulary includes `application/x-wii-msgboard`,
`application/x-wii-minidata`, `image/x-wii-picture`, and multipart types. Custom
letter artwork, thumbnail rendering, and channel launch buttons therefore need
the native attachment formats and their association contract. An email sender
name or an invented header is insufficient evidence of original icon behavior.

Copyrighted artwork and the extracted jump object remain private. Original
artwork was not copied into a replacement notice during this review.

## Remaining native checks

- Japanese body rendering and header encoded words.
- Message Board presentation of an unscoped public notice.
- Actual HCHJ multipart/message-board attachment serialization and bounds.
- Jump-button behavior, including installed-title prerequisites.

These checks are separate from a successful queue insertion or HTTP mail download.
No authentic HCHJ-branded icon or native jump button is claimed yet.
