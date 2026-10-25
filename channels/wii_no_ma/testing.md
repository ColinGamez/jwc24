# Public tests and retained private integration fixtures

The Wii no Ma tests include independent XML/compression unit tests and checks of
the developer's retained local catalogs, Miis, historical-room experiments and
movie files. Those private inputs are not distributed by this repository. Their
absence in a clean checkout must be an explicit skipped integration check,
rather than an unexplained test failure or invented replacement data.

Nine retained-fixture cases use a test-only gate with these primary inputs:

| Check | Required retained input |
| --- | --- |
| Bandwidth movie framing | Private `c8/2-H.mov` movie |
| Paid event/posters | Private Rakuten catalog |
| Normal theater and poster wall | Private theater catalog |
| Concierge Mii | Private theater catalog and Mii roster |
| Special Mii batch/parade room | Private theater catalog, Mii roster and room catalog |
| Historical rotations | Private Mii roster and room catalog |
| Historical menu and labeled-revival experiments | Private room catalog |

Only missing primary inputs cause skips. When present, the original assertions
still run: corrupt catalogs, wrong CRCs, changed expected values and missing
asserted secondary binary/artwork files remain failures. Relevant catalog
environment variables are temporarily pinned to the same checked inputs and
restored after each test, avoiding accidental use of a different local catalog.

The generic XML-shape test uses explicitly synthetic in-memory movie/product
records, so it can run without private catalogs. Those records exist only during
the test. They are not published, offered as products or media, or treated as
original Nintendo data. Private fixture checks likewise do not establish
authentic assets, original commerce behavior or native rendering.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_wii_no_ma tests.test_wii_no_ma_private_gates
```

Test output must retain the skipped count. A green public run with skipped
private checks is not an equivalent claim to running those integrations with
their retained inputs, and neither is proof that the channel is complete.
