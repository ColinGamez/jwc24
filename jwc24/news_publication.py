"""Validated private News publication from explicit, already signed native files.

No publisher is selected, news synthesized, timestamp rewritten, trust patched,
or task provisioned. Evidence references are caller assertions recorded privately;
cryptographic validity does not establish licensing or installed-client trust.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid

from .forecast import encode_lz10, unix_to_wii_minutes
from .news import ENVELOPE_SIZE, MAX_ENVELOPE_BYTES, MAX_RAW_BYTES, NewsFormatError, inspect_news_envelope
from .news_bundle import SLOT_COUNT, MAX_BUNDLE_BYTES, NewsBundleInspection, inspect_news_bundle
from .publication_lock import directory_lock

MAX_KEY_BYTES = 16384
MAX_MANIFEST_BYTES = 65536
_PREFIX = re.compile(r'/v2/([0-6])/([0-9]{3})\Z')
_GENERATION = re.compile(r'bundle-[0-9a-f]{32}\Z')
_PREPARED = object()


class NewsPublicationError(ValueError):
    """A fixed publication diagnostic, excluding private paths/content."""


def _reference(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 512
            or any(ord(char) < 32 for char in value)):
        raise NewsPublicationError('News publication needs bounded explicit source/rights references')
    try:
        if len(value.encode('utf-8')) > 2048:
            raise NewsPublicationError('News evidence reference exceeds local bounds')
    except UnicodeError:
        raise NewsPublicationError('News evidence reference is not valid text') from None
    return value


def _read(path, maximum, *, within=None):
    path = Path(path).resolve()
    if within is not None and not path.is_relative_to(Path(within).resolve()):
        raise NewsPublicationError('News publication file escapes its generation directory')
    try:
        with path.open('rb') as stream:
            value = stream.read(maximum + 1)
    except OSError:
        raise NewsPublicationError('News publication input could not be read') from None
    if len(value) > maximum:
        raise NewsPublicationError('News publication input exceeds local bounds')
    return value


def _json(data):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise NewsPublicationError('News publication JSON repeats a field')
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=object_pairs)
    except (ValueError, UnicodeError):
        raise NewsPublicationError('News publication JSON is invalid or ambiguous') from None


def _verify_signatures(payloads, key_bytes):
    if not key_bytes or len(key_bytes) > MAX_KEY_BYTES:
        raise NewsPublicationError('News publication needs a bounded explicit public key')
    try:
        with tempfile.TemporaryDirectory(prefix='jwc24-news-verify-') as directory:
            key_path, signature_path = Path(directory) / 'public.pem', Path(directory) / 'signature.bin'
            _write_private_key(key_path, key_bytes)
            seen = set()
            for payload in payloads:
                digest = hashlib.sha256(payload).digest()
                if digest in seen:
                    continue
                seen.add(digest)
                signature_path.write_bytes(payload[64:ENVELOPE_SIZE])
                result = subprocess.run(
                    ['openssl', 'dgst', '-sha1', '-verify', str(key_path), '-signature', str(signature_path)],
                    input=payload[ENVELOPE_SIZE:], capture_output=True, check=False, timeout=15,
                )
                if result.returncode:
                    raise NewsPublicationError('News payload signature does not verify against the supplied key')
    except (OSError, subprocess.TimeoutExpired):
        raise NewsPublicationError('News signature verification could not run') from None


def _configuration(route_prefix, source_refs, rights_ref):
    match = _PREFIX.fullmatch(route_prefix) if isinstance(route_prefix, str) else None
    if match is None:
        raise NewsPublicationError('News route prefix must be an explicit native numeric v2 prefix')
    if not isinstance(source_refs, (tuple, list)) or len(source_refs) != SLOT_COUNT:
        raise NewsPublicationError('News publication needs one source reference for every explicit slot')
    return match, tuple(_reference(value) for value in source_refs), _reference(rights_ref)


def _buffers(values):
    # Reject streams/generators before iteration; the supported sequence has a
    # fixed count and is snapshotted before any validation/signing reuse.
    if type(values) not in (tuple, list) or len(values) != SLOT_COUNT:
        raise NewsPublicationError('News publication needs exactly 24 explicit byte-buffer slots')
    snapshot = tuple(values)
    if len(snapshot) != SLOT_COUNT:
        raise NewsPublicationError('News publication input slots changed during snapshotting')
    return snapshot


def _write_private_key(path, data):
    # TemporaryDirectory creates the private parent. Explicit owner-only mode
    # avoids a process-wide umask changing POSIX signing-key permissions; on
    # Windows the temporary directory's inherited ACL remains controlling.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)


@dataclass(frozen=True)
class NewsPublication:
    route_prefix: str
    payloads: tuple[bytes, ...] = field(repr=False)
    source_refs: tuple[str, ...] = field(repr=False)
    rights_ref: str = field(repr=False)
    key_sha256: str = field(repr=False)
    windows: tuple[tuple[int, int, int], ...] = field(repr=False)
    bundle: NewsBundleInspection = field(repr=False)
    _prepared: object = field(default=None, init=False, repr=False, compare=False)

    def is_prepared(self):
        return self._prepared is _PREPARED

    def is_current(self, unix_timestamp):
        if type(unix_timestamp) is not int:
            raise NewsPublicationError('News publication clock must be an integer Unix timestamp')
        try:
            minute = unix_to_wii_minutes(unix_timestamp)
        except ValueError:
            return False
        # Local publication policy; the native close-time boundary is inclusive.
        return all(updated <= minute <= closed and secondary <= minute + 1440
                   for updated, closed, secondary in self.windows)

    def metadata(self):
        if not self.is_prepared():
            raise NewsPublicationError('News publication has not completed explicit validation')
        return dict(self.bundle.metadata(), signatures_checked=True,
                    signatures_verified_against_supplied_key=True,
                    source_and_rights_references_recorded=True,
                    rights_independently_verified=False, installed_client_trust_verified=False,
                    native_vff_capacity_verified=False, task_registration_verified=False,
                    publication_windows_checked=True, current_validity_checked=True,
                    article_timestamps_verified=False,
                    scope='validated explicitly supplied signed News files; current-window serving policy')


def prepare_news_publication(payloads, *, public_key, route_prefix, source_refs,
                             rights_ref, current_unix_timestamp=None):
    """Validate explicit inputs without writing, acquiring news or changing them."""
    return _prepare(payloads, key_bytes=_read(public_key, MAX_KEY_BYTES), route_prefix=route_prefix,
                    source_refs=source_refs, rights_ref=rights_ref,
                    current_unix_timestamp=current_unix_timestamp)


def _prepare(payloads, *, key_bytes, route_prefix, source_refs, rights_ref, current_unix_timestamp):
    match, refs, rights_ref = _configuration(route_prefix, source_refs, rights_ref)
    payloads = _buffers(payloads)
    try:
        bundle = inspect_news_bundle(payloads, enveloped=True)
        inspected = tuple(inspect_news_envelope(value) for value in payloads)
    except NewsFormatError:
        raise NewsPublicationError('News publication failed coherent bounded bundle inspection') from None
    locale = int(match[2]), int(match[1])
    if any((item.country_code, item.language_code) != locale for item in inspected):
        raise NewsPublicationError('News payload locale does not match the explicit route prefix')
    _verify_signatures(payloads, key_bytes)
    publication = NewsPublication(route_prefix, payloads, refs, rights_ref,
                                  hashlib.sha256(key_bytes).hexdigest(),
                                  tuple((item.updated_timestamp, item.close_timestamp, item.secondary_timestamp)
                                        for item in inspected), bundle)
    now = int(time.time()) if current_unix_timestamp is None else current_unix_timestamp
    if not publication.is_current(now):
        raise NewsPublicationError('News payloads are outside the current publication windows')
    object.__setattr__(publication, '_prepared', _PREPARED)
    return publication


def build_news_publication(raw_buffers, *, private_key, public_key, route_prefix,
                           source_refs, rights_ref, current_unix_timestamp=None):
    """Compress/sign explicit native raw buffers; never create or retime news.

    The caller must supply a matching key pair deliberately. This implements
    the publicly corroborated envelope shape, not a Nintendo trust substitute.
    """
    _match, source_refs, rights_ref = _configuration(route_prefix, source_refs, rights_ref)
    raw_buffers = _buffers(raw_buffers)
    try:
        inspect_news_bundle(raw_buffers, enveloped=False)
    except NewsFormatError:
        raise NewsPublicationError('News build inputs failed coherent bounded raw inspection') from None
    private_bytes = _read(private_key, MAX_KEY_BYTES)
    key_bytes = _read(public_key, MAX_KEY_BYTES)
    if not private_bytes:
        raise NewsPublicationError('News build requires an explicit private signing key')
    envelopes, cache = [], {}
    try:
        with tempfile.TemporaryDirectory(prefix='jwc24-news-sign-') as directory:
            key_path = Path(directory) / 'private.pem'
            _write_private_key(key_path, private_bytes)
            for raw in raw_buffers:
                digest = hashlib.sha256(raw).digest()
                if digest not in cache:
                    compressed = encode_lz10(raw)
                    result = subprocess.run(['openssl', 'dgst', '-sha1', '-sign', str(key_path)],
                                            input=compressed, capture_output=True, check=False, timeout=15)
                    if result.returncode or len(result.stdout) != 256:
                        raise NewsPublicationError('News signing did not produce the expected explicit-key envelope')
                    cache[digest] = bytes(64) + result.stdout + compressed
                envelopes.append(cache[digest])
    except (OSError, subprocess.TimeoutExpired):
        raise NewsPublicationError('News explicit-key signing could not run') from None
    return _prepare(envelopes, key_bytes=key_bytes, route_prefix=route_prefix,
                    source_refs=source_refs, rights_ref=rights_ref,
                    current_unix_timestamp=current_unix_timestamp)


def _write_synced(path, data):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_news_publication(root, publication, *, current_unix_timestamp=None):
    """Publish a complete immutable generation, switching one pointer atomically.

    Only output under the explicit root is written. Failed staging leaves the
    previous pointer intact; complete orphan generations can be retained after
    a pointer-replace failure. No old generation is deleted automatically.
    """
    if type(publication) is not NewsPublication or not publication.is_prepared():
        raise NewsPublicationError('Expected a prepared News publication')
    now = int(time.time()) if current_unix_timestamp is None else current_unix_timestamp
    if not publication.is_current(now):
        raise NewsPublicationError('News publication expired before it could be published')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with directory_lock(root):
        staging = Path(tempfile.mkdtemp(prefix='.staging-news-', dir=root)).resolve()
        generation = 'bundle-' + uuid.uuid4().hex
        final_generation = (root / generation).resolve()
        if not staging.is_relative_to(root) or final_generation.parent != root:
            raise NewsPublicationError('News staging/generation escapes the explicit publication root')
        pointer_tmp = root / ('.pointer-news-' + uuid.uuid4().hex)
        try:
            files = []
            for slot, value in enumerate(publication.payloads):
                name = f'news.bin.{slot:02d}'
                _write_synced(staging / name, value)
                files.append({'slot': slot, 'filename': name, 'bytes': len(value),
                              'sha256': hashlib.sha256(value).hexdigest(),
                              'source_ref': publication.source_refs[slot]})
            manifest = {'schema_version': 1, 'route_prefix': publication.route_prefix,
                        'public_key_sha256': publication.key_sha256,
                        'rights_ref': publication.rights_ref, 'files': files}
            _write_synced(staging / 'manifest.json', json.dumps(manifest, ensure_ascii=False).encode('utf-8'))
            os.replace(staging, final_generation)
            pointer = json.dumps({'schema_version': 1, 'generation': generation}).encode('ascii')
            _write_synced(pointer_tmp, pointer)
            os.replace(pointer_tmp, root / 'current.json')
        finally:
            pointer_tmp.unlink(missing_ok=True)
            # Checked absolute staging path remains inside this explicit root.
            cleanup_target = staging.resolve()
            if (cleanup_target.parent == root and cleanup_target.name.startswith('.staging-news-')
                    and cleanup_target == staging and cleanup_target.exists()):
                shutil.rmtree(cleanup_target)
    return publication.metadata()


def load_news_publication(root, *, public_key, current_unix_timestamp=None):
    """Load one atomic generation and recheck hashes, signatures and structure."""
    root = Path(root).resolve()
    pointer = _json(_read(root / 'current.json', 1024, within=root))
    if (not isinstance(pointer, dict) or set(pointer) != {'schema_version', 'generation'}
            or pointer['schema_version'] != 1 or not isinstance(pointer['generation'], str)
            or not _GENERATION.fullmatch(pointer['generation'])):
        raise NewsPublicationError('News publication pointer is invalid')
    generation = (root / pointer['generation']).resolve()
    if not generation.is_relative_to(root):
        raise NewsPublicationError('News generation escapes its publication root')
    document = _json(_read(generation / 'manifest.json', MAX_MANIFEST_BYTES, within=generation))
    expected = {'schema_version', 'route_prefix', 'public_key_sha256', 'rights_ref', 'files'}
    if (not isinstance(document, dict) or set(document) != expected or document['schema_version'] != 1
            or not isinstance(document['files'], list) or len(document['files']) != SLOT_COUNT):
        raise NewsPublicationError('News generation manifest is invalid')
    key_bytes = _read(public_key, MAX_KEY_BYTES)
    if hashlib.sha256(key_bytes).hexdigest() != document['public_key_sha256']:
        raise NewsPublicationError('News generation public key differs from the explicit supplied key')
    payloads, refs, used = [], [], 0
    for slot, row in enumerate(document['files']):
        name = f'news.bin.{slot:02d}'
        if (not isinstance(row, dict) or set(row) != {'slot', 'filename', 'bytes', 'sha256', 'source_ref'}
                or type(row['slot']) is not int or row['slot'] != slot or row['filename'] != name):
            raise NewsPublicationError('News generation slots are invalid or reordered')
        value = _read(generation / name, min(MAX_ENVELOPE_BYTES, MAX_BUNDLE_BYTES - used), within=generation)
        used += len(value)
        if type(row['bytes']) is not int or row['bytes'] != len(value) or hashlib.sha256(value).hexdigest() != row['sha256']:
            raise NewsPublicationError('News generation payload size or checksum differs')
        payloads.append(value)
        refs.append(row['source_ref'])
    return _prepare(payloads, key_bytes=key_bytes, route_prefix=document['route_prefix'],
                    source_refs=refs, rights_ref=document['rights_ref'],
                    current_unix_timestamp=current_unix_timestamp)
