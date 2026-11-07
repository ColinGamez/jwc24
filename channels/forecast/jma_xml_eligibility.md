# Normal VPFD51 report and issue-age checks

`jwc24.jma_xml_eligibility.check_xml_eligibility` binds one supplied document's
bytes to its receipt, parses it again and checks an explicit office, clock and
maximum issue age. It does not accept a caller-edited parsed object in place of
the original bytes. This is a prerequisite for source use, not source activation
or an accepted complete Forecast publication.

Local policy `jwc24-vpfd51-normal-announcement-age-v1` accepts only the exact
status/type/version tuple reviewed in both retained morning reports:
`通常`, `発表`, `1.0_1`. Training, test, correction, cancellation and unfamiliar
versions reject. This narrow supported subset is not a claim that other JMA
reports are invalid. Correction/supersession/cancellation history requires a
separate lifecycle implementation; a single passing report cannot prove that no
later notice exists. The official [technical materials](https://xml.kishou.go.jp/tec_material.html)
keep the control/header schema distinct from product-specific semantics.

The caller must provide an integer age limit between one second and seven days;
there is no default cadence or assertion that JMA recommends that limit. Expiry
is the original `ReportDateTime` plus the supplied limit, and the exact expiry
instant rejects. Transmission, target and retrieval times remain distinct.
Actual transmissions precede their displayed announcements, so the gate does
not impose the reverse ordering. Future retrieval intervals reject. Fetching an
old report again cannot make its original issue time current.

Seven focused tests passed, including both actual private 05:00/11:00 reports
at their historical capture clocks and their rejection at a later clock. Tests
also check training/cancellation/version drift, exact expiry, a newly fetched
old issue, changed bytes with an unchanged receipt, office mismatch and target
time preservation. They perform no network requests. The actual-source test
skips explicitly when private captures are absent.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_jma_xml_eligibility -v
```

Receipt/body agreement is not independent source authentication. A later
publisher must establish latest-report history, every source dependency,
city/station identity, complete field availability, native validity and source
attribution. It must cap validity by the earliest applicable source expiry.
This check assigns no native city or clock, supplies no missing low/high value,
constructs/signs no payload and changes no profile or publication.
