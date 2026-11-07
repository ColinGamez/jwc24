# JWC24 weather source attribution

For JMA-derived data, the sources are the Japan Meteorological Agency's
[published forecasts](https://www.jma.go.jp/bosai/forecast/) and
[AMeDAS observations](https://www.jma.go.jp/bosai/amedas/).
JWC24 parses those records and converts their measurements for the replacement
service. JWC24 is responsible for its processing; JMA did not create or endorse
the resulting channel payloads.

出典：気象庁ホームページ
（[天気予報](https://www.jma.go.jp/bosai/forecast/)・
[アメダス](https://www.jma.go.jp/bosai/amedas/)）。
気象庁の公開データをもとに、JWC24が解析・単位換算等を行っています。
加工内容の責任はJWC24にあります。

JMA's [source terms](https://www.jma.go.jp/jma/kishou/info/coment.html),
[Public Data License 1.0](https://www.digital.go.jp/resources/open_data/public_data_license_v1.0)
and [reuse guidance](https://www.data.jma.go.jp/developer/ryuui.pdf) are the
reviewed references. Source credit and the identity of the processor must
accompany reuse; published forecast areas and values must be preserved.
Terms were rechecked on November 7, 2026.

This credit accompanies the public source tools. Their source-record export
also contains provider URLs and a processing notice. A future native publisher
must carry these notices through its service setup/distribution and provenance
records. No native weather publication has been activated by adding this file.

The preserved original channel manual describes the original service's provider.
It does not identify the source of replacement JWC24 weather. A checked binary
message offset interrupts normal forecast loading and is not a verified inline
credit field. No original manual, resource or screen is rewritten here; actual
distribution of the replacement service still needs its accompanying credit
path verified. See [source integration](jma_source.md).
