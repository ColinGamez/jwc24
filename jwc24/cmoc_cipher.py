"""Bounded offline CMOC AES-CBC and observed application write semantics.

Keys, chunks and acquisition outcomes are explicit caller inputs. No resource
ownership, device identity, transport or authentication is established here.
"""
from dataclasses import dataclass, field


def _chunks(chunks):
    if (type(chunks) is not tuple or len(chunks) > 64
            or any(type(c) is not bytes for c in chunks)
            or sum(map(len, chunks)) > 1024 * 1024):
        raise ValueError('Expected bounded immutable CMOC cipher chunks')
    return chunks


def _aes(key, iv):
    try:
        from Crypto.Cipher import AES
    except ImportError as error:
        raise RuntimeError('CMOC AES inspection requires the optional crypto extra') from error
    return AES.new(key, AES.MODE_CBC, iv)


def decrypt_aes_cbc(*, key, iv, chunks):
    """Decrypt exact complete blocks; never pad, unpad or infer an IV."""
    _chunks(chunks)
    if type(key) is not bytes or len(key) not in (16, 24, 32):
        raise ValueError('Expected an explicit AES key of 16, 24 or 32 bytes')
    if type(iv) is not bytes or len(iv) != 16:
        raise ValueError('Expected an explicit sixteen-byte AES IV')
    if any(len(chunk) % 16 for chunk in chunks):
        raise ValueError('CMOC AES input chunks must contain complete sixteen-byte blocks')
    context = _aes(key, iv)
    return tuple(context.decrypt(chunk) for chunk in chunks)


@dataclass(frozen=True)
class CipherChunk:
    requested_size: int
    return_size: int
    sdk_accepted: bool | None
    written: bytes | None = field(repr=False)


@dataclass(frozen=True)
class CipherInspection:
    setup_enabled: bool
    setup_key_size: int
    enabled: bool
    resolved_key_size: int
    chunks: tuple[CipherChunk, ...]
    final_chain: bytes | None = field(repr=False)

    def metadata(self):
        return dict(algorithm='AES-CBC', setup_enabled=self.setup_enabled,
                    setup_key_size=self.setup_key_size, enabled=self.enabled,
                    resolved_key_size=self.resolved_key_size,
                    chunks=[dict(requested_size=c.requested_size,
                                 return_size=c.return_size,
                                 sdk_accepted=c.sdk_accepted,
                                 written_size=None if c.written is None else len(c.written))
                            for c in self.chunks],
                    source_authentication_established=False,
                    service_or_transport_completed=False)


def inspect_application_cipher(*, key, key_size, iv, chunks,
                               setup_acquired, chunk_acquired,
                               release=False, release_acquired=None):
    """Project original setup/decode/release at explicit acquisition boundaries.

    A None chunk write means the original left caller output unchanged. It does
    not mean empty plaintext or successful decoding. The application can return
    a requested non-block size even when its SDK rejected it without writing.
    Acquisition inputs describe wrapper results, not simulated IOS resources.
    """
    _chunks(chunks)
    if type(key_size) is not int or not 0 <= key_size <= 4096:
        raise ValueError('Expected an explicit bounded CMOC key size')
    if key is not None and (type(key) is not bytes or len(key) > 4096
                            or key_size > len(key)):
        raise ValueError('Expected bounded explicit CMOC key bytes')
    if iv is not None and (type(iv) is not bytes or len(iv) != 16):
        raise ValueError('Expected an explicit sixteen-byte IV or native null IV')
    if type(release) is not bool or type(chunk_acquired) is not tuple or len(chunk_acquired) != len(chunks):
        raise ValueError('Expected explicit acquisition outcomes for every chunk')
    if key is None:
        if key_size != 0 or setup_acquired is not None:
            raise ValueError('Disabled cipher has no setup acquisition')
        selected = b''
        enabled = False
    else:
        if type(setup_acquired) is not bool:
            raise ValueError('Expected an explicit setup acquisition result')
        if setup_acquired:
            if key_size == 0:
                if b'\0' not in key:
                    raise ValueError('CMOC strlen mode requires a supplied NUL terminator')
                selected = key.split(b'\0', 1)[0]
            else:
                selected = key[:key_size]
            enabled = len(selected) in (16, 24, 32)
        else:
            selected = b''
            enabled = False
    setup_enabled = enabled
    setup_size = len(selected) if enabled else 0
    chain = (bytes(16) if iv is None else iv) if enabled else None
    rows = []
    for chunk, acquired in zip(chunks, chunk_acquired):
        if not enabled:
            if acquired is not None:
                raise ValueError('Disabled cipher does not acquire for chunk copying')
            rows.append(CipherChunk(len(chunk), len(chunk), None, chunk))
            continue
        if type(acquired) is not bool:
            raise ValueError('Enabled cipher requires an explicit chunk acquisition result')
        if not acquired:
            rows.append(CipherChunk(len(chunk), 0, None, None))
        elif len(chunk) % 16:
            rows.append(CipherChunk(len(chunk), len(chunk), False, None))
        else:
            output = decrypt_aes_cbc(key=selected, iv=chain, chunks=(chunk,))[0]
            rows.append(CipherChunk(len(chunk), len(chunk), True, output))
            if chunk:
                chain = chunk[-16:]
    if release and enabled:
        if type(release_acquired) is not bool:
            raise ValueError('Enabled cipher release requires an explicit acquisition result')
        if release_acquired:
            enabled = False
    elif release_acquired is not None:
        raise ValueError('No release acquisition occurs on this path')
    return CipherInspection(setup_enabled, setup_size, enabled,
                            setup_size if enabled else 0, tuple(rows), chain)
