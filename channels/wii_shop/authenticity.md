# Original Shop fidelity requirements

Updated October 25, 2026, following the owner's explicit requirement: original
assets and experience, no placeholders or invented replacements. This applies
across JWC24, with the Shop findings below documenting the current experiment.

JWC24's service implementation is new code. The target client experience is
the original Japanese channel: its layout, artwork, copy, sounds, animations,
control meanings and flows. Backend compatibility work must not be presented
as recovered original Nintendo server code. Authorized current provider data
can replace discontinued feeds without inventing facts about that data.

## Current preview does not meet the requirement

The loopback preview establishes browser connectivity and exercises a catalog.
It is not an authentic-complete Shop restoration. These concrete deviations
remain in `jwc24/wii_shop_artwork.py` and its adapter:

| Area | Current deviation | Required work |
| --- | --- | --- |
| Page source | Third-party archive includes later edits; the list template uses modern JavaScript and the home includes an added Easter egg | Recover and corroborate original Japanese storefront pages and behavior |
| Text | JWC24 translates labels, supplies category descriptions, and replaces decoding errors with another character | Recover original Japanese copy and correct source encoding |
| Controls | Publisher/genre functions are repurposed as list/demo filters; unsupported links lead to a custom explanation | Preserve the original meaning and implement the corresponding data and flow |
| Account/title fields | Unknown balance, price, release date and player fields become dashes; publisher is blank | Obtain verified values and implement native account state; do not fabricate values |
| Images | 23 title images are unavailable in the current fetch; missing resources use a transparent spacer | Recover the correct images and verify title association; do not count blank images as completion |
| Details | Download/ownership controls are hidden and a custom preparation message is inserted | Restore original controls and implement their actual behavior |
| Scripts | Original handlers are discarded and replaced with a JWC24 ES3 bridge | Verify original scripts and native behavior, limiting necessary adaptation to service compatibility |
| Navigation | Footer visibility, back labels and title line splitting are overridden | Recover the original page states, navigation and text handling |

Deleting those substitutions alone would not restore missing functions or
original material. Keep the experiment distinguishable from the finished
experience while recovering originals. Do not use another emulator launch as
proof that these fidelity gaps are solved.

## Evidence, not appearance

The [resource comparison](../../research/wii_shop_artwork_provenance_20261025.json)
compares every resource in the 71-file private web pack against the installed
Shop v21 resource archive, after checking all installed title contents against
their TMD. Exactly **2 resources match byte for byte**:

- `/oss/oss/common/images/spacer.gif`
- `/oss/oss/common/images/banner/under_banner_shadow.gif`

This comparison establishes byte equality to the local installation. The TMD's
Nintendo signature has not been verified. The other **69 resources are
unmatched**, which does not prove they are inauthentic: server-side assets need
not be bundled in the channel. Their provenance needs independent evidence.
The transparent spacer is an original resource, but using it in place of missing
title artwork is still a placeholder.

The cached archive's `W_03.html` has a modified doctype and a `clicker.html`
link. `B_04.html` uses `URLSearchParams`, template literals and a separate game
dataset. These are concrete signs that the cached pages are not an untouched
retail-era server snapshot. Source URLs and SHA-256 checks protect the local
cache against alteration; they do not establish historical authenticity.

The 821 downloaded title images retain source-reported title-ID associations.
Their successful decoding and route checks do not independently verify their
Nintendo provenance or association against original title metadata.

## Reproduce the read-only comparison

```powershell
python -m tools.audit_wii_shop_artwork '<original installed Dolphin Wii directory>' private/wii_shop/artwork-v2
python -m unittest tests.test_wii_shop_artwork_audit tests.test_wii_shop_client_audit
```

The comparison reads installed Shop contents and the private web cache. It does
not read device keys, tickets or account saves; it emits metadata only and
changes neither source. Use the original installed profile, not the patched
preview profile. Original bytes remain private and outside Git.
