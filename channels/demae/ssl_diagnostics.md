# Demae SSL diagnostics

## October 14 live result

The diagnostic captured `hostname=127.0.0.1`, handshake result -29184
(`MBEDTLS_ERR_SSL_INVALID_RECORD`, -0x7200). A caller still selected TLS against
the local plain HTTP fixture listener. Patching the common local API GET and
POST scheme selectors resolved this transport failure in the native shared
profile test: the listener received `webApi_document_template`, and the channel
advanced from 331401 to 333400 when that unsupported action returned HTTP 400.
The document-template response contract remains to be implemented; no restored
channel or successful ordering is claimed.

## Investigation scope

Static tracing maps it to `331400 - raw_error`, with raw error -1. The request
manager's SSL-result path can produce that value; the precise live producer
and failing hostname were not established by the breakpoint captures. The
separate runtime diagnostic provided the hostname/result evidence above.

The current application content matches the rebuilt auth-patched WAD. Live
RAM checks confirmed the patched HTTP selector instructions were loaded.
Those checks establish which code was present, not which request failed.

A diagnostic variant of the existing Dolphin source adds opt-in stderr events
for SSL creation, connecting-state failure and final MbedTLS handshake results.
Enable it only for the diagnostic process with `JWC24_SSL_DIAGNOSTICS=1`.
The hostname is restricted to DNS/IP characters and at most 255 bytes;
invalid input is withheld. URLs, query strings, bodies, keys and certificates
are not printed. Read/write retry events are suppressed. Without the environment
flag, the helper emits nothing. SSL verification and the earlier socket
single-reply fix are preserved.

The diagnostic executable is built separately and placed beside the existing
emulator so it can use the same dependencies. Run it only against the existing
`%APPDATA%/Dolphin Emulator` profile. The regular executable is not replaced.
Its purpose is to establish the live SSL host/result before further endpoint
or response changes. A successful build is not evidence that Demae is fixed.
