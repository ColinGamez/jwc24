# Bounded Japanese localization evidence

Reviewed October 25, 2026. This audit distinguishes the installed v21 scripts,
collector-captured server files, selected Japanese asset variants, and JWC24
adaptation. Fingerprints establish exact bytes examined, not Nintendo signature
verification or an exact original Japanese captured-page experience.

## Original Japanese controller artwork

The collector's shared cache contains an original Japanese normal/hover pair:

| Resource beneath `/oss/oss/common/images/banner/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `controller_msg1_J_ja.gif` | 3,250 | `222f22d5bf910030891152f304ac3e22eff397c6f79aa22d9749b7a6b5b52aa8` |
| `controller_msg2_J_ja.gif` | 3,154 | `aad1e109ef4997d1aac52ce2e63c009bfdcfc474abbee99a828e42b217f7509b` |

Both GIFs have a 77×65 logical screen. Visual inspection confirms the Japanese
controller-link wording, rendered within the images. No pixels or replacement
text are reproduced in implementation code or tests.

The captured B05 for `000100015732434A`, SHA-256
`61887bc7e9894ac4797247778dc4f1916f2ab2673268ea409df5ae033e40e65c`, uses
`controller_msg1_E_en.gif` in `Image3control`; its original hover handler swaps
to `controller_msg2_E_en.gif`. Selecting the same-family Japanese pair preserves
the control's role and normal/hover distinction. It is an explicit selection of
recovered Japanese asset variants, not a claim that this captured B05 was a
Japanese-language page.

`jwc24.wii_shop_localization.controller_images(captured_scripts)` returns
`(normal_url, hover_url)` after verifying the exact bytes, sizes, MIME types,
GIF signatures, and dimensions. It uses the existing captured-resource reader
and leaves shared source data unchanged. Missing or altered images raise an
error; the component does not emit an English fallback or generated picture.
The renderer owns applying these URLs and preserving controller navigation.

## Source-backed common labels and their limits

The archive listing has eighteen explicit Japanese-language storefront requests,
including after one percent-decoding pass used only for classification. Ten are
W02/W02_1 news requests and eight are P01/P02/P17–P22 points/payment requests.
There are no corresponding Japanese-language category, keyword-search or catalog
requests in that filename inventory. Country=JP alone does not establish UI
language; the accepted Japanese game titles coexist with English UI captions.

The eighteen Japanese news/payment bodies decode strictly as UTF-8 without
replacement characters. The [metadata report](../../research/wii_shop_localization_validation_20261025.json)
records every examined page's basename, size and SHA-256, plus these limited
original labels and target-function associations:

| Label | Verified source context | Example source SHA-256 |
| --- | --- | --- |
| `もどる` | W02 footer returning to W01; P01 returning home; P17 returning to P01 | W02: `bd6f32653e169c2559fb612bef75640912bbb2e9346c8c868f7a01e5cbba6c2e` |
| `やめる` | P02/P18/P20 cancellation of points/payment input | P02: `3ce115df68a917045d8a91c8437dadfdc3808369df41769467bd86a4ec483dfa` |
| `もういちど` | P02 invalid-number retry | Same P02 fingerprint |
| `OK` | P02 input validation | Same P02 fingerprint |

These labels are evidence for those common-button meanings. The payment retry
does not establish a keyword-search-again control. This audit does not replace
the original category/search flow with a news or payment page or transplant
their behavior into unrelated controls.

The Japanese W02 page title is `おしらせ`; P01/P02 titles use
`Wiiショッピングチャンネル`. Those are narrow captured contexts rather than a
complete localization table. The eight additional points/payment captures remain
private in `private/wii_shop/localization-evidence-v1`; no script was executed.

## Installed resources and encoding

The installed `native-assets-v1` pack contains three pinned scripts. Their
contents are ASCII after removing the UTF-8 BOM on `common.js`. There is no
Japanese literal table in those scripts. The native Shop wrapper exposes
`title`, `menuBtn`, `retryBtn` and `connecting`; the properties' Japanese values
are supplied by the native client, not encoded in this private JavaScript pack.
In particular, native retry wording is not evidence for a search-again label.

The collector's 394 shared files match the common-file count in the archive
listing. Thirteen shared JavaScript files were reviewed for Japanese text;
the Japanese text found was keyboard-constant commentary rather than category
or list UI captions. The captured keyboard is CP932 and already served with
`charset=Shift_JIS`. The loaded legacy page artifacts decode strictly as UTF-8.
No runtime decoding bug was confirmed in this bounded review. English captions
are present in the source; changing their decoder cannot recover absent
Japanese labels.

Windows Python's default diagnostic encoding can make correctly decoded
Japanese appear garbled in tool output. Evidence collection explicitly used
UTF-8 output and checked source bytes rather than interpreting that display
artifact as damaged originals.

Image filenames alone also do not establish wording. `NEW_ja.gif` visibly says
`NEW`, and the five reviewed generic category/footer backgrounds and top symbol
contain no Japanese labels. Japanese category/search/list captions and the
complete original common-button flow remain recovery work.

Validation: `.venv/Scripts/python.exe -m unittest tests.test_wii_shop_localization -v`
passes five tests, including an optional byte check against the private original
pair. Synthetic fixtures contain only fake GIF headers and test marker bytes.
No Dolphin, NAND, device credentials, owner backup, or external service was used.
