# Additional channel scope and evidence boundaries

The October 26 project-wide restoration request includes channels beyond the
existing adapters. A read-only TMD inventory of the current `Stock WADs`
directory establishes these additional identities:

| Local package | TMD identity | Version / IOS | Restoration boundary |
| --- | --- | --- | --- |
| Today and Tomorrow Channel | `000100014841564A` / HAVJ | 512 / 35 | Japanese fortune-channel package available; service/runtime behavior not audited |
| Digicam Print Channel | `000100014843444A` / HCDJ | 1024 / 56 | Package available; print/order provider and native contracts not audited |
| Wii Speak Channel | `000100014843464A` / HCFJ | 512 / 56 | Package available; peer/service prerequisites not audited |
| Internet Channel | `000100014841444A` / HADJ | 1024 / 55 | Browser package available; not evidence of a WC24 replacement service |
| Region Select | `0001000848414C4A` / HALJ | 2 / 31 | System-helper package available; not evidence of a separate hosted channel |

These identities were parsed from package metadata, not inferred from a
filename. This inventory does not verify all content hashes, extract private
material, install titles, or prove which network features each client uses.
The user's real NTSC-U hardware changed to Japan is not automatically equivalent
to a clean Japanese system; actual settings, installed versions and native
service behavior require a later read-only profile/hardware readiness review.

Everybody Votes has no visible package in this bounded stock directory.
Literal path searches in the existing private Nintendo index for `vote`
returned two unrelated JavaScript icon files; `Fortune` returned no rows.
These are scoped search results, not proof that the full collection lacks
either client or supporting material. No placeholder title ID, manifest or
service endpoint is created for an unidentified client.

Existing baseline: [News](../channels/news/readiness.md) and
[Nintendo Channel](../channels/nintendo/readiness.md) still require their
actual payload contracts. [CMOC framing](../channels/cmoc/framing.md) now has
native interop for its bounded structural subset; startup/authentication and
all online Mii/contest semantics remain separate unfinished work.

The SDK/WC24 manuals indexed in the
[collection review](nintendo_collection_index_20261022.md) supply versioned
platform guidance. They do not replace the missing channel-specific contracts.
Private source files, derived disassembly and device credentials stay outside
Git. No original copy/assets, data format, price, content offer, vote result,
submission receipt or provider order was invented for this inventory.
