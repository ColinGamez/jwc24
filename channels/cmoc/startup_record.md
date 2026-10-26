# CMOC FD first-data record and state consumer

October 26, 2026. The Japanese HAPJ v512 investigation now goes beyond
[generic response framing](framing.md) to an actual first-data record consumed
by startup code. This is an independent offline codec and native RAM comparison,
not a running startup/authentication/menu service or a response to a real client.

## Evidence chain and fields

The pinned private main DOL remains SHA-256
`3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3`.
The original WAD and contents are unchanged. No original source, resources,
keys, cached user data or Mii submissions are included with this component.

The request path already attributed to `FD` is used by retrieval code at
`0x8006F6C4`; the startup state method at `0x80053A4C` obtains that result and
checks/converts it as FD data. The record constructor at `0x8005377C` zeros
twelve bytes, obtains tag `0x4644` from `0x800537D4`, and writes a declared
short size of twelve. That is a concrete original record layout.

| Record offset | Observed width and use |
| --- | --- |
| `0x00` | BE16 tag, `FD` (`0x4644`) in the typed constructor |
| `0x02` | BE16 short declared record size, twelve in the constructor |
| `0x04` | Opaque BE32 field copied with the generic record prefix |
| `0x08` | Byte copied into the first-data object and then synthetic singleton-state offset `0x14` by the native consumer |
| `0x09` | Byte copied through native setting accessors into the synthetic settings object's offset `0x1B` |
| `0x0A` | BE16 copied into synthetic singleton-state offset `0x1C` |

Those offsets and copies do not establish the fields' complete product meanings,
authorized server values or freshness. They are deliberately not named consent,
eligibility, country, version, unlock flags or authentication tokens. The zero
constructor is a layout observation, not a specification to serve all-zero data.

The native converter at `0x80053D5C`/`0x80053E40` accepts a declared short size
at most `0x60` and a tag of zero or FD. It does not require twelve declared or
available bytes before the subsequent fixed-field copy. The guarded synthetic
test traps an attempted read past an eight-byte backing record. That isolated
behavior does not establish what earlier authenticated parsing permits.

The independent decoder therefore requires an exact FD tag, 12–96 available
bytes and a matching short declared size. Additional bytes remain an opaque
extension. This explicit safe subset is stricter than that native type cast;
it must not be described as the native predicate having the same checks.

## Backend component

`jwc24/cmoc_startup.py` supplies:

- `decode_first_data_record`: bounded selected-field decoding, with private
  values and extension bytes excluded from object representation/metadata.
- `encode_first_data_record`: the observed twelve-byte form, requiring every
  wire value and a nonempty caller evidence reference. The reference requirement
  is not verification that its source is genuine. There are no invented field
  defaults, HTTP headers, successful empty responses or authentication envelopes.
- `inspect_first_data_response`: bounded outer framing, one unambiguous FD
  record and optional tag/word-4/word-8 request correlation. Other records remain
  explicitly undecoded. Duplicate FD records are rejected as local ambiguity
  policy; the original cache's duplicate selection behavior is not established.

The independent response check does not execute header-byte-2/3 negotiation,
HTTP status/`X-RESULT`, encryption or signature checks. Matching correlation
fields is not authenticated startup acceptance. No live `/first/...` handler,
submission, voting or cached response is generated or published by this work.

```powershell
.venv/Scripts/python.exe tools/inspect_cmoc_startup.py <private-framed-response>
.venv/Scripts/python.exe tools/inspect_cmoc_startup.py <private-FD-record> --record
.venv/Scripts/python.exe -m unittest tests.test_cmoc_startup
```

The CLI reads at most the configured framing limit plus one byte, or 97 bytes
in record mode, and prints only scope/counts. It does not print fields, input
paths, Miis or payload bytes. Original inputs are not modified.

## Native execution and limits

`tools/verify_cmoc_startup.py` executes the original record constructor and
`0x80053A4C` state method through return. Actual type checking, twelve-byte
prefix/field copy and observed setting updates execute unchanged. Inputs,
first-data object, settings manager, settings storage, singleton state and stack
are explicitly synthetic RAM. Three dependencies are intercepted:

- Cached FD lookup at `0x8006F6C4` returns the supplied synthetic record or none.
- Singleton lookup at `0x8001187C` returns synthetic state storage.
- The local UI transition request at `0x8027494C` is recorded without running UI.

The source fingerprint, instruction/code/read/write bounds and guards constrain
execution. Input records remain unchanged, writes are limited to the observed
copy/setting fields and stack, and copied bytes/state are checked against the
provided fixture. No SDK/network/authentication or persistence operation runs.

A present wrong-type record and a valid FD record both request local transition
value two in this method, although only valid converted data updates the fields.
A missing record requests no transition. Thus that transition value alone is
explicitly **not** evidence of accepted startup, restored menus or authentication.
Native generic tag-zero acceptance also remains separate from the strict FD codec.

Thirteen tests cover field widths/provenance requirements, framing/correlation,
missing/duplicate/opaque records, unsigned boundaries, metadata privacy, bounded
reads and selected native state behavior. Native tests require the private
original and Unicorn and otherwise skip. All 29 current CMOC tests passed in
this local pass, including the existing framing checks.

## Remaining requirements

Recover verified service values and full field meanings, cached-response lookup
and lifecycle, original HTTP result and header-version negotiation, signatures/
encryption, device/account prerequisites and complete startup state transitions.
Then connect an actual native request and record original first-run/menu behavior.
Discovery lists, creator/search, contests, submissions, voting and WC24 tasks
retain their separate unfinished contracts. This record component closes a
specific decoding/producer/state-copy gap without claiming those services exist.
