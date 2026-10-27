# Nintendo Channel callback buffering and asynchronous HTTP state

October 28, 2026. This continues the [language/install lifecycle](load_lifecycle.md)
through the intervening callback buffer, virtual poll/restart and manager result
normalizer. `jwc24.nintendo_http` projects explicit supplied state and underlying manager outcomes
into those observed rules, then can hand retained bytes to the existing language
and ListData inspector. It is not a live HTTP client or restored channel service.

The original Japanese HATJ v1792 executable remains private and unchanged:
4,194,944 bytes, SHA-256
`aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264`.
Its vtable identifies the selected class as `prmnet::AsyncHTTPLoader`. The
[validation report](../../research/nintendo_http_validation_20261028.json)
records numeric regions, hashes and aggregate comparisons without software,
catalog content, request references, callback data or private identifiers.

## Actual paths and state representation

| Original boundary | Observed role |
| --- | --- |
| `0x800287E0..0x80028910` | Complete callback chunk copy and state/error/retry updates |
| `0x8002BD80` | Manager invokes its original virtual poll, then normalizes the result |
| `0x800285E0..0x80028728` | Complete selected poll branches and retry dispatch |
| `0x80028490..0x8002857C` | Original restart wrapper and buffer/counter setup |
| `0x8002BE20..0x8002BEE8` | Complete manager result normalization |
| `0x80004364` | Original chunk copy, including its PPC floating-point instructions |

The offline state keeps native words by offset: `word_04`, `word_08`, `word_0c`,
`error_word_1c`, `error_word_20`, and the outer manager's error words. Their
additional meanings are not guessed as HTTP status, content length, region,
account validity or permission. The separately identified `copied_bytes` is the
counter at loader `+0x2834`; output pointer and capacity are at `+0x2830/+0x2838`.
The shared retry word is the signed value at `r13-0x7BA8`.

The API requires an explicit buffer, counter, all state/error words, retry word
and local skipped-input history. It creates neither an empty catalog nor native
initial state on the caller's behalf. The buffer and opaque values are excluded
from dataclass representations and metadata.

## Received chunks can be skipped without a native error

The callback copies nonempty input only if the existing copied count plus its
length fits the supplied output capacity. The byte counter and word `+0x0C`
update after that copy. An oversized chunk is skipped without independently
assigning an error. The later state branch can still take its non-error path.
Thus that path does not establish that all received body bytes were retained.

Callback word `+8 == 2` bypasses the later state/error handling. Otherwise:

- Word `+0x10 == 0` sets state word `+8` to three and copies callback word
  `+0x0C`; the shared retry word changes from `-1` to zero when applicable.
- A nonzero word `+0x10`, detail `0x3FD22..0x3FD24` or `0x3FD28`, and prior retry
  word `-1` set the retry word to one, state word `+4` to two and word `+8` to
  seven. These numeric details are not given invented service meanings.
- Other nonzero cases retain the supplied error/detail words and set word `+8`
  to six.

The independent projection additionally tracks skipped input for the current
attempt. This is a local completeness safeguard, not a recovered native field.
Its allocation and chunk limits prevent unsigned addition wrap; corrupted native
counters and wraparound behavior remain outside the safe backend subset.

## Polling and normalized results are different observations

The original poll accepts word `+4` equal to two or three. The separately
provided timer predicate is checked before the phase branches. In the tested
expiry path it assigns error `-109` and detail `0x41E4C`. It does not verify
independently how elapsed time or timeouts were produced.

| Word `+8`, with accepted word `+4` and no expiry | Observed raw poll result |
| --- | --- |
| Two | One |
| Four | Invoke underlying manager boundary `0x80027140`; zero changes word `+8` to five and returns zero, other outcomes return one |
| Three | Invoke underlying manager boundary `0x800271D0`, ignore its return and return zero |
| Five | Zero |
| Six | `-109` |
| Seven | Set word `+4` to one and run the original start wrapper; a zero wrapper result becomes poll result one |
| Other phase or rejected word `+4` | `-300` |

The start wrapper requires the shared request-manager pointer. When present it
resets the copied counter and word `+0x0C` **before** its request boundary at
`0x80026C80`. Previous output bytes remain allocated, but no longer belong to
the new attempt's retained count. A negative request outcome assigns `-109` and
the separately supplied underlying manager error word. A nonnegative outcome sets both state
words `+4/+8` to two. The local skipped-input marker resets with this new attempt.

The outer manager's normalizer is not a simple return passthrough. For its
recognized negative poll results it copies the loader's stored error/detail
words and returns the signed first stored word. In explicit fixtures this can
return zero or a positive value while the raw poll is negative. The new result
therefore retains both `raw_poll_result` and `manager_result`; neither alone is
reported as a loaded or authenticated catalog.

`inspect_http_list_download()` requires the modeled data phase (three/five), zero
raw and manager results, a nonempty retained body and no skipped input. It slices
only the copied count, preserving the distinction between exact raw/compressed
body and unused allocation tail, and invokes the existing language/record
inspector. It rejects the dropped-chunk path even if the native state branch
and normalized number otherwise look complete. Its input state and underlying manager outcomes
remain caller assertions, not verified network history or origin.

## Independent original execution

`tools/verify_nintendo_http.py` runs the complete callback or the manager's actual
virtual poll, restart wrapper and normalizer. Original copying, branches,
vtable calls and stores execute unchanged. The harness intercepts only:

- Timer reset/start/update/predicate functions; it supplies the explicit expired
  predicate without claiming actual clock behavior.
- Underlying manager status boundaries `0x80027140/0x800271D0` and request boundary
  `0x80026C80`, with exact observed arguments checked in restart cases.
- The diagnostic boundary, which records no real request or text.

`0x80026C80` is an original application request-manager wrapper, including
configuration/header/request calls beneath the selected slice. It is not a
proved SDK leaf. Those inner operations remain intercepted and unfinished;
the claim that the restart wrapper executes does not extend through them.

The 157 comparisons cover 52 callback cases and 105 poll cases: empty/exact-fit/
overflow copies; callback phase bypass; retry/error limits; accepted/rejected
outer states; every phase from zero through eight; timeout precedence; raw versus
normalized errors; underlying manager outcomes; unavailable request storage and restart reset.
Each execution is instruction bounded, constrains code/read/write ranges, and
checks exact buffer/state and immutable input/stack guards. Original input is
only read; no emulator application, profile, provider or device is operated.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_nintendo_http
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_nintendo*.py'
```

Public synthetic tests exercise the stricter handoff with actual raw/LZ10 bytes.
The native class skips honestly without the pinned private executable or
optional Capstone/Unicorn. All 60 Nintendo-specific tests passed in 15.322 seconds,
including the eight new targeted tests. An independent empty-working-directory
run passed all six public tests and explicitly skipped the unavailable-private
native class. The actual socket/HTTP parser, request/header construction,
underlying manager callbacks and timer implementation, full asynchronous worker/heap/lifetime,
genuine catalog/media, trust/freshness, original UI and submissions remain
unfinished. A synthetic projected state or matching native slice is not a live
download, successful service response or full Nintendo Channel restoration.
