"""Explicit local HFNJ SDK task images; no task table, profile or key IO.

The original caller prepares an SDK kind-three task. This module preserves
that observed layout without assigning an IOS task ID or registering anything.
"""
from dataclasses import dataclass, field
import struct


TASK_BYTES = 0x200
SDK_INITIALIZER_KIND = 3
UNASSIGNED_TASK_ID = 0xFFFF


class BodyCheckTaskError(ValueError):
    """A fixed local preparation diagnostic, excluding supplied values."""


@dataclass(frozen=True)
class DatasetTaskConfiguration:
    url: str = field(repr=False)
    filename: str = field(repr=False)
    app_id: int = field(repr=False)
    title_id: int = field(repr=False)
    title_version: int = field(repr=False)
    flags_byte: int
    flags_word: int
    interval_minutes: int
    server_interval_minutes: int
    priority: int
    opaque_word_1f8: int = field(repr=False)
    signing_key_present: bool
    encryption_key_present: bool
    evidence_ref: str = field(repr=False)


def _bounded_integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise BodyCheckTaskError('Task setting is outside the explicit supported range')


def _string(value, minimum, maximum):
    if (type(value) is not str or not minimum <= len(value) <= maximum
            or any(not 0x20 <= ord(char) <= 0x7E for char in value)):
        raise BodyCheckTaskError('Task string is outside the exact ASCII-copy subset')
    return value.encode('ascii')


def validate_configuration(configuration):
    if type(configuration) is not DatasetTaskConfiguration:
        raise BodyCheckTaskError('An explicit dataset-task configuration is required')
    c = configuration
    url = _string(c.url, 7, 235)
    filename = _string(c.filename, 1, 63)
    if not url.startswith((b'http://', b'https://')):
        raise BodyCheckTaskError('Task URL is outside the observed HTTP-prefix contract')
    _bounded_integer(c.app_id, 1, 0xFFFFFFFF)
    _bounded_integer(c.title_id, 1, 0xFFFFFFFFFFFFFFFF)
    if not c.title_id & 0xFFFFFFFF:
        raise BodyCheckTaskError('Task title needs an explicit nonzero low word')
    _bounded_integer(c.title_version, 0, 0xFFFF)
    _bounded_integer(c.flags_byte, 0x80, 0xFF)
    _bounded_integer(c.flags_word, 0, 0xFFFFFFFF)
    if c.flags_word & 4 and url.startswith(b'http://'):
        raise BodyCheckTaskError('Task flag and HTTP-prefix combination is unsupported')
    _bounded_integer(c.interval_minutes, 360, 10080)
    _bounded_integer(c.server_interval_minutes, 30, 20160)
    _bounded_integer(c.priority, 1, 100)
    _bounded_integer(c.opaque_word_1f8, 0, 0xFFFFFFFF)
    if any(type(value) is not bool for value in (c.signing_key_present, c.encryption_key_present)):
        raise BodyCheckTaskError('Explicit key-presence predicates are required')
    if (type(c.evidence_ref) is not str or not c.evidence_ref.strip()
            or len(c.evidence_ref) > 512
            or any(ord(char) < 32 for char in c.evidence_ref)):
        raise BodyCheckTaskError('A bounded explicit evidence reference is required')
    return url, filename


@dataclass(frozen=True)
class DatasetTaskImage:
    data: bytes = field(repr=False)
    existing_task: bool
    key_import_requested: bool

    def metadata(self):
        return {'sdk_task_bytes': len(self.data), 'sdk_initializer_kind': SDK_INITIALIZER_KIND,
                'existing_task_image': self.existing_task,
                'key_import_requested': self.key_import_requested,
                'sdk_context_or_task_database_verified': False,
                'key_material_written': False, 'task_registered': False,
                'scheduler_or_download_verified': False,
                'signature_trust_or_native_ui_verified': False,
                'profile_modified': False}


def prepare_dataset_task(configuration, *, existing_task: bytes | None):
    """Prepare local SDK fields from explicit values, retaining unknown bytes.

    None selects the observed unassigned kind-three initializer layout. Existing
    images must explicitly match the supplied identity fields; that local safety
    policy is stricter than some native context checks. No existing input is
    edited, SDK task ID assigned, key imported or backend task provisioned.

    Native copies stop after their terminator and preserve later bytes. Long
    inputs that would be silently truncated by the SDK are deliberately refused.
    """
    url, filename = validate_configuration(configuration)
    c = configuration
    if existing_task is None:
        data = bytearray(TASK_BYTES)
        struct.pack_into('>HBBIIQH', data, 0, UNASSIGNED_TASK_ID,
                         SDK_INITIALIZER_KIND, 0xC0, 0, c.app_id,
                         c.title_id, c.title_version)
        data[0x1A0:0x1AC] = b'content.bin\0'
    else:
        if type(existing_task) is not bytes or len(existing_task) != TASK_BYTES:
            raise BodyCheckTaskError('An existing SDK task needs one exact immutable image')
        if (existing_task[2] != SDK_INITIALIZER_KIND
                or struct.unpack_from('>I', existing_task, 8)[0] != c.app_id
                or struct.unpack_from('>Q', existing_task, 12)[0] != c.title_id
                or struct.unpack_from('>H', existing_task, 20)[0] != c.title_version):
            raise BodyCheckTaskError('Existing SDK task identity differs from the explicit configuration')
        data = bytearray(existing_task)
    data[3] = c.flags_byte
    struct.pack_into('>I', data, 4, c.flags_word)
    struct.pack_into('>H', data, 0x18, c.priority)
    struct.pack_into('>HH', data, 0x1C, c.interval_minutes, c.server_interval_minutes)
    struct.pack_into('>I', data, 0x1F8, c.opaque_word_1f8)
    data[0xB4:0xB4 + len(url) + 1] = url + b'\0'
    data[0x1A0:0x1A0 + len(filename) + 1] = filename + b'\0'
    return DatasetTaskImage(bytes(data), existing_task is not None,
                            c.signing_key_present and c.encryption_key_present)
