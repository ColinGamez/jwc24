# Early Wii SDK PDF review for JWC24

Reviewed October 22, 2026. The user-provided folder contains **19 PDFs,
669 pages**, primarily the January-March 2006 RVL_EMU/NDEV SDK documentation.
This is useful platform documentation, not a complete specification for Wii
channels or their discontinued online services.

## Review scope and source handling

All PDFs were inventoried, fingerprinted, text-extracted and keyword-indexed.
Titles, contents and relevant technical sections were reviewed; this is not
a claim that every sentence on all 669 pages has been verified. Six selected
pages were rendered and visually checked, including the texture-tile and THP
container diagrams. Japanese extraction in Hio2If is unreliable, so its
protocol details remain unreviewed beyond the visually checked introduction.

The originals remain under the user's Nintendo workbench. Extracted text,
absolute source paths, SHA-256 identities and rendered pages are retained only
in ignored `private/sdk_pdf_review/`. No PDF, SDK implementation, sample code,
library, tool binary, NAND data or key is added to the public repository.
The notes below are paraphrased findings and proposed work, not copied SDK code.
Page references are one-based PDF pages; printed page labels can differ.

## Inventory

| PDF | Pages | JWC24 relevance and limit |
| --- | ---: | --- |
| RVL_EMU_QuickStart.en | 10 | Early development-board setup; RVL_EMU is not the modern Dolphin emulator |
| Hio2If | 33 | Development target-to-PC Host I/O; not a recovered Internet or WC24 protocol |
| AX | 12 | Audio processing, sample addressing and buffering; not mail attachment framing |
| AX_Applications | 32 | Audio mixing, sequencing and streaming application patterns |
| DSPADPCM | 10 | Standalone DSP audio header, byte order, samples and loop metadata |
| DSPTOOL_DLL | 14 | Historical host-side audio conversion API; not a required runtime dependency |
| SoundPipeline | 48 | Sound sample/table organization, alignment and audio asset management |
| G2D | 8 | Tile-layer graphics; its constraints must not be applied to every channel layout |
| GX | 230 | Highest-value graphics reference: texture packing, tiles, alignment and cache issues |
| MTX | 52 | Transform and projection context for native graphics traces |
| TPL | 4 | Texture descriptors, images and shared color lookup tables; not a full binary offset schema |
| VI | 32 | Framebuffer layout, display modes and video presentation |
| RVL-HardwareTransitionGuide | 10 | MEM1/MEM2, configuration and early-platform limits |
| DVD | 26 | Optical-disc I/O; not NAND, VFF or network-download behavior |
| OS | 62 | Allocation, threads, exceptions and cache control; some discussion is inherited from GameCube |
| PAD | 24 | GameCube controller API; not Wii Remote pointing or Balance Board behavior |
| RVL-BuildSystem | 18 | Historical build organization and debug/release context |
| RVL-SDK-RoadMap | 8 | Index to libraries, HTML API manuals and demonstrations |
| THP | 36 | THP movie container, decoding and synchronization; applicability requires identifying the actual client codec |

## Findings that affect implementation choices

### Graphics and textures

GX Appendix D, PDF pages 221-224, distinguishes pixel-component packing from
tile packing. Images are tiled, not ordinary linear pixel arrays. RGBA8 uses
separate AR and GB portions within each 4-by-4 tile; 8-bit texels occupy
8-by-4 tiles. PDF page 223's diagram resolves the orientation more clearly
than the prose's ambiguous 4-by-8 wording. Tile rows/columns are padded, and
image/mipmap alignment must be checked separately (pages 224-225).

TPL pages 3-4 explain descriptors referencing texture images and optional
CLUTs, including shared palettes. They do not specify all the on-disk fields
needed for an independent TPL parser. Those offsets still require a separate
verified format source or inspection of actual files.

Application: compare these rules with `tools/build_demae_qr_resource.py` and
the RGB565 modal resource builder. Existing I8 code already uses 8-by-4 tiles;
the PDF is corroboration, not evidence that a new encoder fix is necessary.
Future independent texture checks should verify packing, dimensions, format,
payload bounds and tile padding without needing an original Nintendo asset.

G2D page 7's power-of-two restrictions belong to that tile-layer API. They
are not a reason to resize every JPEG served to Wii no Ma or to assume every
channel uses G2D. JPEG allocation caps and client-specific image dimensions
remain governed by each channel's actual decoder.

### Native crashes and memory

OS page 12 describes 32-byte allocation alignment for its allocator. Pages
20-21 discuss exception context and cache behavior. A useful native crash
record should retain the instruction address, access address, DSISR and
register context where available. Those are investigation inputs, not a
diagnosis that every invalid write is an alignment or cache bug.

The transition guide pages 5-7 distinguish MEM1/MEM2 and restrict the graphics
FIFO to MEM1 in this SDK. Do not extend the existing MEM1-only Unicorn test
maps to arbitrary addresses just to make a consumer pass. First establish
which allocator, arena and mapped sections that particular client uses.

Application: improve reproducibility of Demae's invalid-write investigations
and future CMOC/Nintendo/Body Check consumer harnesses. Existing allocation
failure tests remain necessary; the manual cannot prove their target binary's
model sizes, ownership rules, allocation success or rendering behavior.

### Video and audio

THP pages 23-26 describe its identification, component ordering, per-frame
size links and padding; page 25 specifies frame alignment and audio sample
constraints. The diagram on page 26 is poorly extracted as text and was
checked visually. Any future THP inspector must distinguish container
versions before interpreting component fields.

This does **not** replace `tools/import_theater_movie.py`: the current Wii
no Ma theater pipeline identifies MOC5 and uses a Mobiclip encoder/decoder.
THP and Mobiclip are different formats. Nintendo Channel's video paths also
need client-specific codec identification before choosing a generator.

DSPADPCM pages 7-8 describe a standalone big-endian audio header and its
sample/loop state. AX page 12 adds buffer-addressing constraints. Neither
establishes the complete formats of BRSTM, BRSAR, THP audio, Mobiclip audio
or Wii Mail attachments. Trace the actual wrapper before applying a header.

### Networking and input limits

The transition guide page 8, section 10, explicitly says networking is not
supported in that initial NDEV SDK release. Hio2If's introduction describes
Host I/O between the development target and PC. Neither is a specification
for WC24, HTTP/TLS, account registration or a commercial channel's backend.

PAD is specifically the GameCube controller guide. Its button and analog
state must not be treated as a Wii Remote IR/pointing, WiiConnect24 standby
input, DSi transfer or Balance Board specification.

The SDK Roadmap pages 5-7 point to HTML API manuals, including NAND, MEM and
SC material, beyond this PDF collection. These are follow-up leads, not
proof that the necessary later service APIs exist in this early SDK.

## Mapping to services and channels

These are evidence-based next steps, not claims that the PDFs restore a
feature or that a live channel was tested during this review.

| JWC24 area | What the PDFs can help with | What remains independent |
| --- | --- | --- |
| Shared WC24 scheduling/delivery | Native memory/debug context | Task registration, encrypted delivery, compression, integrity and VFF contracts |
| Wii Mail/accounts/friends | Buffer and diagnostic context | Registration, friend authorization, mailbox/attachment framing, scheduler and native receipt checks |
| TV no Tomo / HBNJ | Rendering diagnostics if a UI fault appears | Guide tables, CGI behavior, regional records and native WC24 acceptance |
| Forecast | Graphics/VI context for visual failures | Native weather dictionaries, locations, task payloads and Wii no Ma integration |
| News | Possible texture/rendering context after payload loading | First-run task capture, news container/record recovery, current sources and article UI |
| Demae | Texture layout checks and native memory/crash analysis | Verified branch variants, XML consumers, native item/basket UI and provider checkout handoff |
| Wii no Ma | Native artwork constraints, audio/video identification discipline | MOC5 media, bootstrap/service XML, interactions, shop functionality and DSi transfer |
| Check Mii Out / CMOC | Thumbnail/rendering and native consumer diagnostics | FD record meanings, authentication, list/search/contest/vote and submission contracts |
| Nintendo Channel | Asset identification and subsequent native video diagnostics | CSData/WC24 framing, catalog semantics, actual movie codec, reviews and downloads |
| Wii Fit Body Check | Native memory/configuration investigation | Legitimate Wii Fit saves/profiles, encrypted dataset semantics, health data and mail |
| Other original channels/services | General platform context only | A verified title/version, endpoint map, payload consumers and native acceptance evidence for each |

Current implementation context was checked against `jwc24/`, the channel
notes, the Demae native harnesses and the media/artwork tools. Several channel
investigations are local uncommitted work; this review does not promote their
status to working services or commit those unrelated changes.

## Prioritized follow-up

1. **Shared diagnostics and asset validation.** Record crash context where
   available and independently validate synthetic I8/RGB565 texture fixtures.
   Preserve original files and use fingerprinted private binaries for native
   execution checks. No new client patch follows merely from reading a manual.
2. **Finish Demae's native item path.** Obtain verified variant evidence and
   execute the actual size-list/item consumer/model paths. Graphics docs help
   investigate display failures only after parsing/storage is established.
3. **Advance each downloaded-data consumer independently.** News needs task
   and container recovery; Nintendo needs CSData recovery; CMOC needs startup
   record/auth semantics; Body Check needs its legitimate save prerequisites
   and decrypted dataset validation. Do not substitute generic SDK structures.
4. **Keep Wii no Ma on its verified media path.** Preserve MOC5 full-stream
   decode checks and original image budgets. Investigate THP only for clients
   whose actual assets/executable establish THP use.
5. **Locate later, service-specific references.** Search separate manuals or
   captures for NWC24, VFF, NAND/IPC, HTTP/TLS and the individual channel APIs.
   The broader workbench has non-PDF research artifacts. The subsequent
   [collection-wide index](nintendo_collection_index_20261022.md) locates those
   leads and catalogs; it does not replace individual protocol verification.

## Result and validation

All 19 documents were indexed; page counts total 669. Selected graphics,
container and exception diagrams were visually checked. This is a research
and implementation-priority update only: no production route, payload,
emulator profile, title, save, order or mail queue was changed. No test suite
was rerun because this pass changes documentation only.
