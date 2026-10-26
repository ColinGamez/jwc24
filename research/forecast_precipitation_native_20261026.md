# Original Forecast precipitation block comparison

October 26, 2026: a bounded, read-only original-code comparison supplements
the public daily-probability guards. It does not execute a whole channel.

Input is the privately retained original Japanese HAFJ v7 application,
1,925,536 bytes, SHA-256
`ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5`.
The verifier refuses other images before importing the optional emulator.
No application bytes or original material are included in Git.

`tools/verify_forecast_precipitation.py` extracts only the text block from
`0x8000D2B0` to the exclusive exit `0x8000D310` into isolated Unicorn PPC32
big-endian memory. It supplies a synthetic day record through `r6` and an
incoming zero in `r0`. Four offsets `+0x12..+0x15` are tested independently:
each slot receives every byte value while the other three remain zero.
Each execution has a 32-instruction and 100-ms limit and must reach the exact
block exit. There are no hooks, imported service responses or service mocks.
The original input on disk is only read.
Code pages are read/execute and the synthetic record page is read-only during
native execution. Each case checks the exact record and surrounding guards;
the original instruction bytes are also checked unchanged afterward. These
checks do not claim that every surrounding caller's read ranges are verified.

All 1,024 cases matched the explicit oracle:

- Values `0..100` and `255` preserve incoming `r0` in 408 cases.
- Values `101..254` set `r0` to `-1` in 616 cases.

This confirms the isolated native byte-admissibility branch and the distinct
`255` marker. The public builder/validator guards were implemented separately;
this verifier runs actual pinned original instructions rather than a copied
Python implementation of those guards. It does not exercise the surrounding
condition dictionary, full validator, return-value propagation, data delivery,
calendar alignment, precipitation display or native UI. Existing static display
branch observations remain in
[native_clock_and_missingness.md](../channels/forecast/native_clock_and_missingness.md).
No temperature or wind interpretation is newly proved here.

```powershell
.venv/Scripts/python.exe tools/verify_forecast_precipitation.py PRIVATE_ORIGINAL_HAFJ_APP
.venv/Scripts/python.exe -m unittest tests.test_forecast_precipitation_native
```

The two tests passed with the private original and local Unicorn available.
Without the optional emulator, the original-code case explicitly skips and the
identity-refusal case still passes; without the private original it also skips.
`JWC24_FORECAST_ORIGINAL` can select an explicitly supplied private original,
but its pinned identity cannot be overridden. No payload, provider acquisition,
profile, scheduler or device was changed.
