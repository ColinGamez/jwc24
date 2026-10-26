# Payload provenance

Binary payloads are deliberately excluded from Git.

Run `tools/update_hbnj_daily.py` to collect current guide metadata and build
fresh `header.hdpk`, `epg.hdpk`, and `string.hdpk` files. The updater validates
the source schema and independently parses the finished native binaries before
publishing them under `channels/hbnj/generated/current`.

That default/`--legacy` mode preserves the existing experiment and replaces
files individually; whole-guide atomicity is unverified. The separate
[`--coherent` snapshot path](../publication.md) requires explicit source/age
evidence and manual runtime activation. It does not replace this legacy mode
or silently grant source redistribution permission.

Do not commit generated schedules, HDPK files, VFF contents, extracted WAD
content, WC24 keys, or private TLS material.
