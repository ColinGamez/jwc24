# Native Forecast clocks and missing measurements

October 26, 2026 read-only static trace of the privately retained original
Japanese HAFJ v7 application, 1,925,536 bytes, SHA-256
`ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5`.
This is the original application input, not the trust-patched working copy.
No original bytes, provider selectors, credentials or payloads are included.
No native UI or device execution was performed in this trace.

## Local clock fields are not provider-age receipts

Original function `0x8002054C..0x80020570` takes a weather-record pointer and:

1. Reads the 32-bit words at record offsets `+8` and `+4`.
2. Subtracts the `+8` word from the `+4` word.
3. Adds that difference to the current-minute global addressed by `r13-0x6B3C`.
4. Stores the adjusted value and passes it to `0x800364D8` for calendar conversion.

That converter produces year/month/day/hour/minute fields. For example, the
year is offset from 2000 at `0x80036600`, and minute/hour are stored at
`0x80036638`/`0x80036644`. Initialization `0x8000D6A8..0x8000D6C4` obtains
system time/calendar values, converts to minute representation and initializes
the same global. The called `0x800EE7A8` reads the hardware timebase. These
operations support a local/UTC **clock-anchor difference used for the location
calendar**. This bounded trace does not establish every use of either word,
forecast effective-date alignment or daylight-saving correctness.

The public builder independently writes normalized `local_unix_timestamp` as
the word at record `+4`, and `generated_unix_timestamp` as the word at `+8`.
Their difference therefore controls the native calendar offset in this path.
Forcing `+4 = provider_observation_time + zone_offset` while `+8` is build time
would also subtract the observation's age from the native clock. There is no
evidence justifying that equality.

The initial JWC24 source-receipt gate incorrectly required that equality. It
has been corrected: receipt times are explicit UTC values, source age is checked
independently, and rebuilding a native local clock does not change the asserted
source time. The receipt attestation is now `provider_times_retimed`, specifically
about replacing provider-time evidence, rather than normalizing native clocks.
The gate makes no native local-clock correctness claim.

Old weather can accompany valid new native clock and envelope fields. Therefore
those fields, file mtimes and retrieval time cannot establish current provider
observations or forecast issue dates. Conversely, assigning native clock fields
from a build clock is not alone proof that provider observations were fabricated.
The separately identified historical-weather substitutions and absent provider
time provenance remain unresolved acquisition problems.

## Missing values have native branches

The original application has explicit unavailable-value handling. These are
static instruction/branch observations, not a new complete binary validator or
proof of accepted UI/network behavior.

| Field / day-relative offset | Original evidence | Supported conclusion |
| --- | --- | --- |
| Precipitation probabilities `+0x12..+0x15` | Validation `0x8000D2B0..0x8000D30C` admits `0..100` or `0xFF`, otherwise marks error; display `0x80007CD0..0x80007D1C` routes `0xFF` to an existing missing-value string branch | Unknown precipitation can remain unavailable; changing it to zero would assert a measured probability. |
| Signed temperature bytes | `0x80007AB0..0x80007AC0` and formatter entries `0x8001D558`, `0x8001D61C` select existing missing-value handling for `-128` | Unavailable temperature need not be replaced by a real numeric temperature. |
| Wind direction `+0x16` | Display `0x8001E1D0..0x8001E1D8` skips the wind-rendering section for `0xFF`; speed is selected separately from `+0x17`/`+0x18` | Missing direction can suppress that wind display. Independent missing-speed behavior has not been established here. |

These paths do not authorize extrapolating a daily probability into all four
six-hour slots, copying current wind into a future forecast, assigning an
unsupported zero index, or replacing unknown weather from a historical file.
Any future provider adapter must preserve the fields actually supplied and
use verified native unavailable representations for fields it does not have.
Missingness does not solve source-age evidence: fresh authorized acquisition
and genuine provider observation/issue times are still required separately.

The regression suite checks the corrected receipt boundary with synthetic
data: fresh source evidence plus an independent rebuilt local clock passes;
stale source evidence still fails despite a current clock, retrieval and
normalized-document digest. It does not execute these original routines or
claim independently verified extraction of provider timestamps.
