# Payload provenance

Binary payloads are deliberately excluded from Git.

Run `tools/update_hbnj_daily.py` to collect current guide metadata and build
fresh `header.hdpk`, `epg.hdpk`, and `string.hdpk` files. The updater validates
the source schema and independently parses the finished native binaries before
publishing them under `channels/hbnj/generated/current`.

Do not commit generated schedules, HDPK files, VFF contents, extracted WAD
content, WC24 keys, or private TLS material.
