# Additional Japanese channel service roles

October 26, 2026. This first audit covers the owner's Today and Tomorrow, Wii
Speak and Digicam Print stock packages. **It is classification and selected
native/controller evidence, not a claim that the channels are restored.**

| Channel | Evidence-backed work track | Remaining boundary |
| --- | --- | --- |
| [Today and Tomorrow HAVJ](../channels/today_and_tomorrow/README.md) | Local application core: bundled affinity resource, local save and a concrete resource-table consumer | Native date/Mii/prediction/save checks; no hosted core-feed contract identified |
| [Wii Speak HCFJ](../channels/wii_speak/README.md) | Online communication plus a separately referenced encrypted/version download | Exact WFC/voice/account path, version delivery/crypto/callbacks, hardware/audio and native validation |
| [Digicam Print HCDJ](../channels/digicam_print/README.md) | Separate print provider/fulfillment, with WC24 messaging evidence | Actual provider contracts and real fulfillment; native notice delivery and original UI verification |

This prevents treating every Wii channel as a missing WC24 payload generator.
In particular, a local fortune resource is not a downloaded prediction feed;
a version-file endpoint is not a proven voice broker; and mail delivery cannot
stand in for an accepted physical print order.

## Package provenance

The [metadata report](additional_channel_provenance_20261026.json) records WAD,
TMD and application hashes. Existing independent extraction decrypted all
**34 contents** with TMD SHA-1 verification enabled. The new read-only auditor
then rechecked every extracted content's size/SHA-1 against the source WAD TMD,
its private extraction-manifest SHA-256, and ticket/TMD title identity.

| Title | Version | IOS | Contents | Boot index | Real application |
| --- | ---: | ---: | ---: | ---: | --- |
| `000100014841564A` HAVJ | 512 | 35 | 12 | 11 | LZ11 content index1 |
| `000100014843464A` HCFJ | 512 | 56 | 9 | 8 | LZ11 content index1 |
| `000100014843444A` HCDJ | 1024 | 56 | 13 | 12 | LZ11 content index1 |

These hashes establish consistency with the owned packages. The Nintendo TMD
signatures were not independently verified. Extracted software, archive data,
derived disassembly, crypto resources and exact local paths remain under ignored
`private/channel_coverage_20261026/`. Nothing was installed or launched. Original
WADs were not modified; no actual Wii backup or device credentials were read.

The private Nintendo index supplied additional bounded leads. No HAVJ/HCFJ
literal-path rows were found in that snapshot. HCDJ has repair-application
sample-save catalog entries, which are not recovered print-service code.
Voice-chat demo/library catalog entries are development references, not proof
of the shipping HCFJ service or a compatible server. No Nintendo host tool,
installer or build script ran, and no internal host or provider was contacted.
The bounded original-instruction experiment is described separately below.

## Verification and limits

The auditor verifies a stored HAVJ resource-table entry selecting archive6's
20,580-byte `etc/affinity.bin`, and records the HCFJ version-descriptor slice.
Those are static consumer relationships; neither native prediction nor a real
version download was executed. Generic SDK/network strings and filename
matches remain leads rather than positive service-restoration evidence.

The [Digicam native report](digicam_provider_url_native_20261026.json) separately
records actual original URL-controller/TLS-selector/formatter execution with
synthetic configuration. Both known production URLs match, unhandled selectors
preserve buffers, and memory/instruction guards pass. There is no network,
account, payment, voice, address, upload, print-order or mail operation.

Six focused tests cover synthetic decompression/path/hash guards, all 34 owned
content checks, native production URL construction, unhandled selectors and
source/settings rejection. Private-fixture tests skip when originals are absent.

```powershell
.venv/Scripts/python.exe -m tools.audit_additional_channel_services
.venv/Scripts/python.exe -m unittest tests.test_additional_channel_services tests.test_digicam_provider_urls
```

The auditor reads the private extraction produced by the existing independent
`tools.extract_wad_contents` tool. It never follows the extraction manifest's
recorded source path, imports a NAND or emits original resource bodies.
Install the optional `reverse-engineering` dependencies for the tested WAD SDK
API. The extraction metadata now encodes the ticket's eight identifier bytes as
sixteen hexadecimal digits and rejects a ticket/TMD identity mismatch. This
fixes an older text-decoding path that could write control characters into the
manifest instead of the title ID. It does not verify Nintendo signatures.
