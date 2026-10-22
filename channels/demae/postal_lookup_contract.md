# Processed postal lookup contract

Verified October 22, 2026 against HCCJ v2 function `0x8002EBCC` in the private
executable with SHA-256
`640982489f7cc7924da52602130dcf3f100054dd8f907a467759356f1659fbfc`.

`jwc24.demae.lookup_processed_postal` accepts processed records and a postcode
integer from 0 through 9,999,999. It is an offline inspection helper. The
production postal route and public Japan Post lookup are unchanged.

Records contain a big-endian 32-bit postcode followed by three terminated
UTF-16BE strings. Source order matters:

- The first exact match returns `exact`, even if an alternative came first.
- Without an exact match, the last record matching `postcode // 100 * 100`
  returns `alternative`. Queries below 100 therefore use zero as the fallback.
- With neither match, the result is `not_found` with no record.

The helper validates the entire buffer, including data after an exact match,
and caps processed input at 256 KiB. Selected strings may contain at most
31, 31 and 63 UTF-16 code units. These are conservative safeguards: the native
consumer returns early on an exact match and truncates oversized selected text.
The helper rejects malformed framing, malformed UTF-16 and selected text that
would be truncated. It does not collapse duplicate records or claim delivery
eligibility from a postal match.

`tools.verify_demae_postal_lookup.verify` loads the fingerprinted executable
into Unicorn and executes the original lookup routine. Only memcpy and memset
are mocked. Synthetic fixtures compare return status, selected code, all three
zero-padded output fields, and unchanged output on a miss. Cases cover both
match orders, duplicate exact/fallback rows, zero, missing records, Japanese
text and surrogate pairs. The native fixture test skips when private source
software is unavailable; the independent helper tests remain runnable.

This verifies processed-record selection, not WC24 delivery, encrypted
download acceptance, the address save, native UI operation or restaurant
coverage. No historical address dataset, device identifier, real save or key
is needed for these checks.
