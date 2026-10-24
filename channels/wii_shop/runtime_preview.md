# Local Shop browsing checkpoint

Updated October 24, 2026. The original v21 Shop browser has reached JWC24's
loopback HTTPS service in Dolphin. The initial connectivity screen rendered at
608 × 456 and reported successful native Shop/sound initialization; the user
also confirmed it visually. That handmade screen has been removed. The current
renderer binds the catalog into archived Shop layouts and artwork.

This is a read-only browsing experiment in a privately patched Dolphin profile.
It is not the clean-WAD restoration milestone, an acquisition service or a
working replacement for Shop accounts, points, tickets or installation.

## Pages and original artwork

The local pack contains 67 resources from the
[Shop website archive](https://wiishopchannel.net/): `W_03.html`, `B_04.html`,
`B_05.html`, shared CSS, button graphics, shadows and other page artwork.
The three-panel home, catalog-card and detail-page layouts come from those
files. The archive contains later edits; this is not a claim of an untouched
Nintendo server snapshot. Two shared images, `spacer.gif` and
`under_banner_shadow.gif`, also match the installed original channel byte-for-byte.

Archived scripts and event handlers are discarded. A small ES3 adapter handles
native Shop/sound/keyboard objects, hover changes and local navigation. Catalog
names and links are escaped before insertion. Japanese labels and read-only
status messages replace unavailable server values. Unknown points, publishers,
dates and player counts are not invented. Title-specific pictures are not yet
imported; unavailable images use the original transparent spacer. The Wii
Channels panel currently leads to the scope explanation because this snapshot
only contains mapped Japan WiiWare/Virtual Console candidates.

Original HTML, CSS, images and software remain under `private/`. Git contains
the importer, bindings and tests. Each cached resource has a source URL, length
and SHA-256; altered resources are rejected before serving. The archived layout
update still needs an in-channel visual check. The earlier native boot proof
belongs to the initial connectivity screen, not to this later artwork update.

## Profile and credentials

`tools.prepare_wii_shop_preview` copies Config/Wii into a new private profile.
It audits the source Shop's 18 contents, replaces 20 Shop URL fields with
`https://127.0.0.1:18443`, and changes the copied Opera URL filter and CA store.
Only content indices 1 and 2 are modified. Their sizes/hashes are updated in
the copied TMD and all referenced contents are rechecked. The patched TMD's
Nintendo signature is not valid or verified; this is a Dolphin-only experiment.
The source title is checked again to confirm it was not changed.

Dolphin initially refused to boot without owner-supplied device credentials.
With the user's authorization, `tools.prepare_vwii_credentials` mapped the Wii
banks of their **Wii U OTP** into the BootMii structure Dolphin reads. It writes
only a new `Wii/keys.bin` inside the marked private preview profile, rejects
existing outputs/default or empty fields, and verifies the source is unchanged.
No raw NAND image was imported, no actual Wii backup was used, and no key or
console-ID values are printed. Real account authentication remains untested.

Format references: [Dolphin IOSC](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/IOSC.cpp),
[ShowMiiVWiiKeys](https://github.com/CuriousTommy/ShowMiiVWiiKeys).

## Transport finding

Forcing `Connection: close` on each HTTPS response produced five repeated Opera
GETs and a blank screen, followed by watchdog error 209601. Keeping HTTP/1.1
connections open with accurate `Content-Length` headers allowed CSS, JavaScript
and the native-ready beacon to load. The persistent-connection behavior is now
covered by a live-listener regression test.

The listener binds only IPv4 loopback. Its private development CA is trusted
only by the copied Opera resources. Certificate verification stays enabled;
TLS 1.0 and legacy ciphers are enabled on this local listener for compatibility.
No system trust store or real-console settings are changed. Request diagnostics
retain route categories, method, status, byte count, TLS version and an agent
family, excluding query strings, identifiers, headers and bodies.

The native page adapter retains `shop.connecting` in a variable to cancel the
page timer. See the [Open Shop Channel bridge documentation](https://docs.oscwii.org/wii-shop-channel/js/shop).
The Opera CA-store format follows
[WSC-Patcher](https://github.com/OpenShopChannel/WSC-Patcher/blob/main/modify_arc.go);
its MIT notice is retained in [third_party](../../third_party/wsc-patcher.LICENSE).

## Reproduction

Tested with libWiiPy 0.6.0, PyCryptodome 3.23.0, OpenSSL and the existing v21
installation. Close Dolphin before making the initial profile copy.

```powershell
python -m tools.import_wii_shop_artwork
python -m tools.prepare_wii_shop_preview
python -m tools.prepare_vwii_credentials --otp '<your Wii U backup>\otp.bin'+powershell -File tools/start_wii_shop_preview.ps1
```

The import/preparation tools refuse existing destination packs/profiles or
credential files. Do not rerun them over a working profile. For subsequent
launches, run only the launcher. `-ServerOnly` updates service availability
without opening or closing Dolphin. Existing Dolphin instances are never
stopped by the launcher.

Browse categories, scroll the catalog, open a title and return to the list.
Acquisition/account controls lead to the scope explanation or remain unavailable;
they do not contact payment or account services.

Validation: 60 Shop tests pass. All 85 catalog pages and 844 title pages were
rendered against the real snapshot; title links cover all 844 grouped IDs once.
See [the measured report](../../research/wii_shop_preview_validation_20261024.json).
