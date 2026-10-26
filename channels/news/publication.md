# Explicit News build, publication and HTTP delivery

The News track now has a runnable binary-service component. It accepts **24
explicitly supplied native buffers**, verifies their coherent article/image
graph, and serves their exact signed bytes on the subtask routes recovered in
the [task investigation](task_registration.md). It does not select a publisher,
download articles, generate fake articles/media, change dates, install trust
material or create IOS tasks. No provider has been selected for this path.

## Inputs and provenance

`tools/news_service.py` accepts a private JSON configuration with exactly these
top-level fields:

| Field | Requirement |
| --- | --- |
| `schema_version` | `1` |
| `route_prefix` | Explicit `/v2/<language>/<three-digit-country>` prefix matching the native files' locale fields |
| `rights_ref` | Nonempty reference to the owner's source/permission review covering these inputs |
| `inputs` | Exactly 24 objects in slot order 0 through 23 |

Each input object contains only `slot`, `path` and `source_ref`. Paths are
resolved relative to the configuration file. Source references and the rights
reference are retained in the private generation manifest, never HTTP output
or public command reports. Recording a reference is **not** independent proof
of the rights or accuracy of an article, image or publisher attribution.

The configuration must describe the real files supplied for every slot. The
tool does not fill missing slots, make up a publisher logo, rename an article,
copy another hour automatically or manufacture history by updating timestamps.
The graph validator permits explicitly identical snapshots while keeping hourly
coverage unverified; repetition does not establish a real 24-hour publication.

## Build or publish

For already-decompressed native inputs, explicitly provide a matching private
signing key and public verification key:

```powershell
.venv/Scripts/python.exe tools/news_service.py build `
  --config private/news/input.json `
  --private-key private/news/signing-private.pem `
  --public-key private/news/signing-public.pem `
  --output private/news/published
```

This validates the raw graph first, compresses the unchanged native bytes with
JWC24's LZ10 encoder, constructs the separately corroborated 64-byte-prefix plus
256-byte RSA/SHA-1 envelope, and verifies the result against the supplied public
key. Existing content and timestamps stay unchanged. The key pair must be
provided deliberately; this command does not generate one, reuse another
channel's key silently, export a key or patch channel trust.

When the configuration instead names existing envelope files, use `publish`
with `--public-key` and omit `--private-key`. Every distinct envelope must verify
against that explicit public key. Zero-filled synthetic signatures accepted by
the offline structural inspector are rejected by publication.

Temporary signing-key copies use a private temporary directory and owner-only
creation mode on POSIX. Windows temporary-directory ACLs remain controlling.
Copies are removed when signing completes or fails. Key bytes, paths, source
selectors and article text are excluded from reports and subprocess diagnostics.

## Publication validation and atomicity

The publication gate checks:

- All 24 buffers and both encoded/advertised decoded aggregate byte bounds.
- The strict single-buffer structures and complete explicit-set topic/image
  reference graph, including conflicting snapshot definitions and mixed locales.
- Exact agreement between the explicit route prefix and file locale fields.
- Signatures against the supplied public key.
- Every buffer's publication window against the supplied/current clock. The
  close boundary is inclusive; a future update or expired window is rejected.

These are explicit local publication policies. Checking header windows does
not establish article age, editorial accuracy, native clock behavior or real
hour-to-slot coverage. The observed native VF request size is not a verified
filesystem-capacity calculation; VFF overhead and real storage acceptance remain
unverified. The 32 MiB aggregate tooling limit must not be described as a native
storage guarantee.

Only a fully prepared immutable snapshot may be written or served. Publication
writes all 24 files and a manifest into a new generation, then atomically replaces
`current.json`. It locks the explicit output root. Failed staging or pointer
replacement preserves the previous pointer. Temporary staging is removed only
after its resolved absolute path is checked within that root. A complete orphan
generation may remain after pointer failure; existing generations are retained.

Reload checks the pointer, contained paths, ordered slots, file sizes/checksums,
public-key fingerprint, signatures and coherent graph again. No original
software, task database, NAND, save or device credentials are read or modified.

## Serve exact subtask responses

```powershell
.venv/Scripts/python.exe tools/news_service.py serve `
  --root private/news/published `
  --public-key private/news/signing-public.pem `
  --bind 127.0.0.1 --port 8082
```

The explicit listener serves only `<route_prefix>/news.bin.00` through `.23`.
Successful requests receive the stored envelope bytes, `application/octet-stream`
and the exact `Content-Length` over HTTP/1.1. There is no replacement channel
screen, arbitrary file route, selected-publisher frontend or unsuffixed fallback.
Unknown routes return 404. If the current snapshot expires while running, its
data stops serving with 503; timestamps are never refreshed to conceal expiry.

The adapter retains one coherent generation in memory. After publishing a new
generation, restart/recreate it from `load_news_publication`; automatic refresh
scheduling and provider acquisition are not yet implemented. The library
`NewsApplication.get(target)` returns the normal status/MIME/bytes tuple for
later shared-server integration. The shared server has not been edited here.

## Verification and remaining native gates

```powershell
.venv/Scripts/python.exe -m unittest tests.test_news_publication
```

Fifteen tests use generated temporary RSA keys, explicitly synthetic native
buffers and loopback HTTP only. They cover all 24 exact signed responses on one
persistent connection, byte lengths, key/signature failures, rights/source input
requirements, graph failures, input-stream rejection, temporary-key cleanup,
atomic failure preservation, manifest tampering, expiry and metadata privacy.
No real publisher data, production key, profile or device was used. Tests skip
when OpenSSL is unavailable; the implementation uses only the standard library
and the explicitly invoked OpenSSL executable.

This service component can now build/sign supplied native files, publish them
coherently and answer subtask HTTP requests. It does **not** yet make a stock
channel trust JWC24 signatures. Original News envelope verification/decompression,
explicit working-copy endpoint/trust preparation, native SDK/IOS registration,
real VFF storage, the live clock and original banner/globe/article UI remain
unverified. A real authorized Japanese provider and native record-generation
adapter are also still required; no content source is chosen implicitly.
