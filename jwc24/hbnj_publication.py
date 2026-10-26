"""Offline HBNJ generations; requires source-checkout tools for validation.

No collection, IOS tasks or transport keys. Wheel-only runtime is unsupported
until the independent validator tools are packaged with the library.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from types import MappingProxyType
import uuid

from .publication_lock import directory_lock

WORKSPACE = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


class HBNJPublicationError(ValueError):
    pass


class HBNJSnapshotExpired(HBNJPublicationError):
    pass


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise HBNJPublicationError('Duplicate publication JSON field')
            result[key] = value
        return result
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise HBNJPublicationError('Publication JSON is invalid') from None


def _read(path, limit=MAX_FILE_BYTES):
    try:
        with Path(path).open('rb') as stream:
            value = stream.read(limit + 1)
    except OSError:
        raise HBNJPublicationError('Explicit publication input could not be read') from None
    if not value or len(value) > limit:
        raise HBNJPublicationError('Publication input exceeds local byte bounds')
    return value


def _contained(root, filename):
    resolved = (root / filename).resolve()
    if not resolved.is_relative_to(root):
        raise HBNJPublicationError('HBNJ publication file escaped its explicit root')
    return resolved


def _reference(value):
    if (type(value) is not str or not value.strip() or len(value) > 2048
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise HBNJPublicationError('Explicit bounded rights reference required')
    return value


def _clock(value):
    value = int(time.time()) if value is None else value
    if type(value) is not int or not 946684800 <= value < 0xFFFFFFFF:
        raise HBNJPublicationError('Expected bounded integer Unix time')
    return value


def _time(value, *, local=False):
    try:
        if type(value) is not str:
            raise ValueError()
        parsed = datetime.fromisoformat(value)
        if local and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=JST)
        elif parsed.utcoffset() is None:
            raise ValueError()
        # Existing HBNJ packer preserves local clock fields rather than
        # converting aware offsets. Require its actual JST input convention.
        if local and parsed.utcoffset() != timedelta(hours=9):
            raise ValueError()
        return int(parsed.timestamp())
    except (ValueError, OverflowError, OSError):
        raise HBNJPublicationError('Guide timestamp is outside the reviewed time convention') from None


def _guide_metadata(raw, *, now, max_collection_age_seconds, rights_ref):
    if (type(max_collection_age_seconds) is not int
            or not 1 <= max_collection_age_seconds <= 7 * 86400):
        raise HBNJPublicationError('Explicit collection-age policy must be 1..604800 seconds')
    guide = _json(raw)
    try:
        if (guide['format'] != 'jwc24_hbnj_guide_v1' or guide['status'] != 'ok'
                or type(guide['areas']) is not list or len(guide['areas']) != 54
                or type(guide['programs']) is not list or not guide['programs']):
            raise HBNJPublicationError('Expected complete normalized HBNJ guide')
        collected = _time(guide['collected_at'])
        if not collected <= now < collected + max_collection_age_seconds:
            raise HBNJSnapshotExpired('Guide collection is future-dated or exceeds its age policy')
        area_ids, channels = [], set()
        ends, starts = {}, {}
        for program in guide['programs']:
            channel = program['channel_id']
            start, end = _time(program['start'], local=True), _time(program['end'], local=True)
            if end <= start:
                raise HBNJPublicationError('Guide program time window is invalid')
            starts[channel] = min(starts.get(channel, start), start)
            ends[channel] = max(ends.get(channel, end), end)
        area_close = []
        for area in guide['areas']:
            identifier = area['id']
            if type(identifier) is not int or not 1001 <= identifier <= 1054 or not area['channel_ids']:
                raise HBNJPublicationError('Guide contains an unsupported area ID')
            area_ids.append(identifier)
            channels.update(area['channel_ids'])
            # Every station must have started its supplied schedule and still
            # have scheduled material; this is not a gap-free coverage claim.
            if any(not starts[channel] <= now < ends[channel] for channel in area['channel_ids']):
                raise HBNJSnapshotExpired('A station schedule does not cover the current time range')
            area_close.append(min(ends[channel] for channel in area['channel_ids']))
        if len(set(area_ids)) != 54:
            raise HBNJPublicationError('Guide area IDs must be unique')
    except (KeyError, TypeError):
        raise HBNJPublicationError('Guide metadata is incomplete') from None
    return {'collected_unix': collected,
            'expires_unix': min(collected + max_collection_age_seconds, *area_close),
            'max_collection_age_seconds': max_collection_age_seconds,
            'rights_ref': _reference(rights_ref), 'area_ids': sorted(area_ids),
            'channels': len(channels), 'programs': len(guide['programs'])}


def _filenames(area_ids):
    return ['header.hdpk', 'epg.hdpk', 'string.hdpk'] + [
        f'areas/{identifier}/{name}.hdpk' for identifier in area_ids for name in ('epg', 'string')]


def _validate_files(directory):
    environment = os.environ.copy()
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment['PYTHONPATH'] = str(WORKSPACE)
    commands = [
        ('validate_hbnj_guide.py', 'guide.json'),
        ('validate_hbnj_payloads.py', 'guide.json', '.'),
        ('validate_hbnj_area_payloads.py', 'guide.json', 'areas'),
    ]
    for tool, *arguments in commands:
        try:
            result = subprocess.run([sys.executable, str(WORKSPACE / 'tools' / tool), *arguments],
                                    cwd=directory, env=environment, capture_output=True,
                                    check=False, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            raise HBNJPublicationError('HBNJ independent validation could not run') from None
        if result.returncode:
            # Source URLs, article/program copy and paths remain private.
            raise HBNJPublicationError('HBNJ independent validation failed')


def _cleanup(directory, root):
    resolved = directory.resolve()
    if resolved.parent != root or not resolved.name.startswith('.stage-'):
        raise HBNJPublicationError('Publication cleanup escaped its explicit root')
    if resolved.exists():
        shutil.rmtree(resolved)


def publish_hbnj_snapshot(guide_file, payload_directory, output_root, *,
                          rights_ref, max_collection_age_seconds, now=None):
    """Publish one complete validated generation, atomically switching one pointer.

    Inputs are explicit local files. All bytes are copied before validation;
    no provider or legacy generated/current file is changed. Complete orphan
    generations may remain after pointer failure, preserving the prior pointer.
    """
    wall_clock = now is None
    now = _clock(now)
    guide_raw = _read(guide_file)
    metadata = _guide_metadata(guide_raw, now=now,
                               max_collection_age_seconds=max_collection_age_seconds,
                               rights_ref=rights_ref)
    files, total = {'guide.json': guide_raw}, len(guide_raw)
    for filename in _filenames(metadata['area_ids']):
        files[filename] = _read(Path(payload_directory) / filename)
        total += len(files[filename])
        if total > MAX_TOTAL_BYTES:
            raise HBNJPublicationError('HBNJ generation exceeds local aggregate bounds')
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with directory_lock(root):
        stage = None
        pointer_temp = None
        generation = 'generation-' + uuid.uuid4().hex
        try:
            stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=root))
            for filename, data in files.items():
                path = stage / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            _validate_files(stage)
            # Long offline validation must not publish an input that expired meanwhile.
            checked_now = _clock(None if wall_clock else now)
            _guide_metadata(guide_raw, now=checked_now,
                            max_collection_age_seconds=max_collection_age_seconds,
                            rights_ref=rights_ref)
            manifest = dict(metadata, schema_version=1, generation=generation,
                            files=[{'path': filename, 'bytes': len(value),
                                    'sha256': hashlib.sha256(value).hexdigest()}
                                   for filename, value in sorted(files.items())])
            (stage / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
            os.replace(stage, root / generation)
            stage = None
            with tempfile.NamedTemporaryFile(dir=root, prefix='.pointer-', delete=False) as temporary:
                pointer_temp = Path(temporary.name)
                temporary.write(json.dumps({'schema_version': 1, 'generation': generation}).encode('utf-8'))
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(pointer_temp, root / 'current.json')
            return {'generation': generation, 'areas': 54, 'routes': 109,
                    'files': len(files), 'coherent_generation_published': True,
                    'runtime_snapshot_activation_required': True}
        finally:
            if stage is not None:
                _cleanup(stage, root)
            if pointer_temp is not None:
                pointer_temp.unlink(missing_ok=True)


@dataclass(frozen=True, init=False)
class HBNJRouteSnapshot:
    generation: str
    collected_unix: int
    expires_unix: int
    _routes: object = field(repr=False)
    _prepared: bool = field(default=False, init=False, repr=False)

    def _require_prepared(self):
        if self._prepared is not True:
            raise HBNJPublicationError('Only a validated loaded HBNJ snapshot can be used')

    def raw_payload(self, request_target, *, now=None):
        self._require_prepared()
        data = self._routes.get(request_target)
        if data is not None and not self.collected_unix <= _clock(now) < self.expires_unix:
            raise HBNJSnapshotExpired('Prepared HBNJ snapshot is no longer current')
        return data

    def metadata(self):
        self._require_prepared()
        return {'generation': self.generation, 'routes': len(self._routes),
                'collection_age_and_schedule_ranges_checked': True,
                'provider_issue_or_correction_time_verified': False,
                'gap_free_program_coverage_verified': False,
                'source_rights_independently_verified': False,
                'raw_hdpk_only': True, 'transport_crypto_or_native_delivery_verified': False}


def load_hbnj_snapshot(output_root, *, now=None):
    """Verify a single pointed generation and freeze all 109 route payloads.

    The caller must apply the existing LZ10/WC24 transport for HBNJ. This loader
    never reads a NAND key or reloads the pointer during individual requests.
    """
    wall_clock = now is None
    now = _clock(now)
    root = Path(output_root).resolve()
    pointer = _json(_read(_contained(root, 'current.json'), 1024))
    if (type(pointer) is not dict or set(pointer) != {'schema_version', 'generation'}
            or type(pointer['schema_version']) is not int or pointer['schema_version'] != 1
            or type(pointer['generation']) is not str
            or re.fullmatch('generation-[0-9a-f]{32}', pointer['generation']) is None):
        raise HBNJPublicationError('HBNJ current pointer is invalid')
    generation = (root / pointer['generation']).resolve()
    if generation.parent != root:
        raise HBNJPublicationError('HBNJ generation escaped the explicit root')
    manifest = _json(_read(_contained(generation, 'manifest.json'), 128 * 1024))
    if type(manifest) is not dict:
        raise HBNJPublicationError('HBNJ generation manifest is invalid')
    guide_raw = _read(_contained(generation, 'guide.json'))
    metadata = _guide_metadata(guide_raw, now=now,
                               max_collection_age_seconds=manifest.get('max_collection_age_seconds'),
                               rights_ref=manifest.get('rights_ref'))
    names = ['guide.json'] + _filenames(metadata['area_ids'])
    if (type(manifest.get('files')) is not list or len(manifest['files']) != len(names)
            or type(manifest.get('schema_version')) is not int or manifest.get('schema_version') != 1
            or manifest.get('generation') != pointer['generation']
            or any(manifest.get(key) != value for key, value in metadata.items())):
        raise HBNJPublicationError('HBNJ generation manifest does not match the guide')
    files, total = {}, 0
    for row, filename in zip(manifest['files'], sorted(names), strict=True):
        path = _contained(generation, filename)
        if type(row) is not dict:
            raise HBNJPublicationError('HBNJ generation file escaped its root')
        data = _read(path)
        total += len(data)
        if total > MAX_TOTAL_BYTES or row != {'path': filename, 'bytes': len(data),
                                             'sha256': hashlib.sha256(data).hexdigest()}:
            raise HBNJPublicationError('HBNJ generation file integrity check failed')
        files[filename] = data
    _validate_files(generation)
    for filename, expected in files.items():
        if _read(_contained(generation, filename)) != expected:
            raise HBNJPublicationError('HBNJ generation changed during independent validation')
    _guide_metadata(guide_raw, now=_clock(None if wall_clock else now),
                    max_collection_age_seconds=metadata['max_collection_age_seconds'],
                    rights_ref=metadata['rights_ref'])
    routes = {'/header.bin': files['header.hdpk']}
    for identifier in metadata['area_ids']:
        routes[f'/{identifier}/epg.bin'] = files[f'areas/{identifier}/epg.hdpk']
        routes[f'/{identifier}/str.bin'] = files[f'areas/{identifier}/string.hdpk']
    snapshot = object.__new__(HBNJRouteSnapshot)
    for key, value in {'generation': pointer['generation'],
                       'collected_unix': metadata['collected_unix'],
                       'expires_unix': metadata['expires_unix'],
                       '_routes': MappingProxyType(routes), '_prepared': True}.items():
        object.__setattr__(snapshot, key, value)
    return snapshot
