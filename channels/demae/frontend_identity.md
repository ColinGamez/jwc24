# Demae ordering frontend and address-settings helper

The ordering frontend is **HCHJ**, title ID **`000100014843484A`**, Japanese
version **512**. The local HCCJ personal-data application must not be treated as
the ordering frontend merely because the local NUS database labels it a food
service channel.

The supplied local helper identifies as **`000100084843434A`**, version **2**;
the ordering title differs in both its title category (`00010001`) and its
four-byte ID (`HCHJ`). The local helper's packaged build label is
`setpersonaldata.0906231905`, and its save path ends in
`/title/00010008/4843434a/data/nocopy/pd.dat`. These local findings are detailed
in [the stock-content inspection](research.md).

## Primary developer evidence

WiiLink's patcher metadata lists the Japanese standard Demae Channel with
`latest_version: 512` and `title_id: 000100014843484a`. This is a direct title
definition for the software being patched, rather than a search-result label.
See [the pinned channel definition](https://github.com/WiiLink24/WiiLink-Patcher-GUI/blob/2f2753344d8378daa3a1a64c419943fc4ec1208f/src/WiiLinkPatcherGUI/data/patches.json#L786-L804).

The same patcher handles SPD through a separate download helper, identifies its
output as WiiLink Address Settings, and gives it a separate WAD filename. See
[the pinned SPD helper](https://github.com/WiiLink24/WiiLink-Patcher-GUI/blob/2f2753344d8378daa3a1a64c419943fc4ec1208f/src/WiiLinkPatcherGUI/setup/download.py#L191-L211).
This metadata distinguishes their roles; it does not establish the title ID of
every third-party SPD build.

The address-settings developer repository independently describes its purpose
as interfacing with regional `pd.dat` used by Japanese channels. Its exit handler
has a Demae destination and launches title `000100014843484A`, confirming that
address setup and the ordering application are separate components. See
[the helper's README](https://github.com/WiiLink24/set-personal-data/blob/18fa5a7d696dfb0f8c7fcdcd2fc5613f2c41dabf/README.md)
and [its Demae launch target](https://github.com/WiiLink24/set-personal-data/blob/18fa5a7d696dfb0f8c7fcdcd2fc5613f2c41dabf/source/channel/main.cpp#L30-L40).

## Scope for local work

The existing local HCCJ findings concern personal-data handling. Those findings
can inform the address-settings integration but cannot establish Demae's
restaurant, menu, cart, or ordering request contracts. Recovering those contracts
requires inspecting the actual HCHJ frontend supplied locally, verifying its
title/version, and tracing its native network requests.

This pass inspected public developer metadata and helper source only. It did not
download a WAD, install or patch a title, launch either application, collect an
address, or place an order. It did not copy a server implementation. The cited
commit hashes make the identity evidence reproducible even if upstream metadata
changes later.
