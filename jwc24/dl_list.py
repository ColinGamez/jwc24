from __future__ import annotations

import datetime as dt
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

from .manifest import ChannelManifest, Task


HEADER_SIZE = 0x80
RECORD_SIZE = 0x10
ENTRY_SIZE = 0x200
ENTRY_COUNT = 120
ENTRY_BASE = HEADER_SIZE + RECORD_SIZE * ENTRY_COUNT
FILE_SIZE = ENTRY_BASE + ENTRY_SIZE * ENTRY_COUNT
CHANNEL_CONTENT = 3
UNSIGNED_FLAG = 0x00000004
# Native encrypted channel-content tasks use bit 1 plus the WC24 decrypt bit.
# Without these, IOS writes the AES ciphertext into the VFF unchanged.
ENCRYPTED_CHANNEL_FLAGS = 0x0000000A


@dataclass(frozen=True)
class EntrySummary:
    slot: int
    title_type: int
    title_code: int
    filename: str
    url: str
    flags: int
    entry_type: int

    @property
    def title_id(self) -> int:
        return (self.title_type << 32) | self.title_code


def _u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _put_u16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into(">H", data, offset, value)


def _put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into(">I", data, offset, value)


def _c_string(data: bytes | bytearray, offset: int, size: int) -> str:
    return bytes(data[offset : offset + size]).split(b"\0", 1)[0].decode("ascii", "replace")


def _put_c_string(data: bytearray, offset: int, size: int, value: str) -> None:
    encoded = value.encode("ascii")
    if len(encoded) >= size:
        raise ValueError(f"value does not fit in a {size}-byte field: {value}")
    data[offset : offset + size] = b"\0" * size
    data[offset : offset + len(encoded)] = encoded


def _entry_offset(slot: int) -> int:
    return ENTRY_BASE + slot * ENTRY_SIZE


def validate(data: bytes | bytearray) -> None:
    if len(data) != FILE_SIZE:
        raise ValueError(f"unexpected nwc24dl.bin size {len(data)} (expected {FILE_SIZE})")
    if data[:4] != b"WcDl" or _u32(data, 4) != 1:
        raise ValueError("file is not a WcDl version 1 task table")
    if _u16(data, 16) > ENTRY_COUNT or _u16(data, 20) != ENTRY_COUNT:
        raise ValueError("task-table header contains unsupported entry counts")


def read(path: Path) -> bytearray:
    data = bytearray(path.read_bytes())
    validate(data)
    return data


def entry(data: bytes | bytearray, slot: int) -> EntrySummary | None:
    offset = _entry_offset(slot)
    title_code = _u32(data, offset + 8)
    title_type = _u32(data, offset + 12)
    if title_type == 0:
        return None
    return EntrySummary(
        slot=slot,
        title_type=title_type,
        title_code=title_code,
        filename=_c_string(data, offset + 416, 64),
        url=_c_string(data, offset + 180, 236),
        flags=_u32(data, offset + 4),
        entry_type=data[offset + 2],
    )


def entries(data: bytes | bytearray) -> list[EntrySummary]:
    return [value for slot in range(ENTRY_COUNT) if (value := entry(data, slot)) is not None]


def _created_task_flags(task: Task) -> int:
    if task.unsigned:
        return UNSIGNED_FLAG
    if task.envelope == "wc24-aes-ofb":
        return ENCRYPTED_CHANNEL_FLAGS
    return 0


def _write_task(data: bytearray, manifest: ChannelManifest, task: Task) -> None:
    offset = _entry_offset(task.slot)
    data[offset : offset + ENTRY_SIZE] = b"\0" * ENTRY_SIZE
    _put_u16(data, offset, task.slot)
    data[offset + 2] = CHANNEL_CONTENT
    _put_u32(data, offset + 4, _created_task_flags(task))
    _put_u32(data, offset + 8, manifest.title_code)
    _put_u32(data, offset + 12, manifest.title_type)
    _put_u16(data, offset + 24, 1)
    _put_u16(data, offset + 28, task.refresh_minutes)
    _put_u16(data, offset + 30, task.retry_minutes)
    _put_c_string(data, offset + 180, 236, manifest.base_url + task.route)
    _put_c_string(data, offset + 416, 64, task.filename)

    record = HEADER_SIZE + task.slot * RECORD_SIZE
    data[record : record + RECORD_SIZE] = b"\0" * RECORD_SIZE
    _put_u32(data, record, manifest.title_code)
    _put_u32(data, record + 4, 0)


def _adopt_task(data: bytearray, manifest: ChannelManifest, task: Task) -> None:
    current = entry(data, task.slot)
    if current is None:
        raise ValueError(f"slot {task.slot} does not contain the native task required for adoption")
    if current.title_id != manifest.title_id or current.filename != task.filename:
        raise ValueError(
            f"slot {task.slot} cannot be adopted: contains "
            f"{current.title_id:016x} {current.filename!r}"
        )

    offset = _entry_offset(task.slot)
    flags = _u32(data, offset + 4)
    if task.unsigned:
        flags = (flags | UNSIGNED_FLAG) & ~0x00000008
    _put_u32(data, offset + 4, flags)
    _put_u16(data, offset + 24, 1)
    _put_u16(data, offset + 26, 0)
    _put_u32(data, offset + 32, 0)
    _put_c_string(data, offset + 180, 236, manifest.base_url + task.route)

    # Preserve the native record key but make the repaired task immediately due.
    record = HEADER_SIZE + task.slot * RECORD_SIZE
    _put_u32(data, record + 4, 0)
    _put_u32(data, record + 8, 0)


def _clear_task(data: bytearray, slot: int) -> None:
    record = HEADER_SIZE + slot * RECORD_SIZE
    data[record : record + RECORD_SIZE] = b"\0" * RECORD_SIZE
    offset = _entry_offset(slot)
    data[offset : offset + ENTRY_SIZE] = b"\0" * ENTRY_SIZE


def provision(path: Path, manifest: ChannelManifest, apply: bool) -> tuple[list[str], Path | None]:
    data = read(path)
    changes: list[str] = []
    if manifest.prune_duplicate_tasks:
        desired_slots = {task.filename: task.slot for task in manifest.tasks}
        for current in entries(data):
            desired_slot = desired_slots.get(current.filename)
            if (
                current.title_id == manifest.title_id
                and desired_slot is not None
                and current.slot != desired_slot
            ):
                changes.append(
                    f"slot {current.slot}: remove duplicate {current.filename} "
                    f"(canonical slot {desired_slot})"
                )
                _clear_task(data, current.slot)
    for task in manifest.tasks:
        current = entry(data, task.slot)
        if current and (current.title_id != manifest.title_id or current.filename != task.filename):
            raise ValueError(
                f"slot {task.slot} is occupied by {current.title_id:016x} {current.filename!r}"
            )
        expected_url = manifest.base_url + task.route
        expected_flags = _created_task_flags(task)
        if (
            current
            and current.url == expected_url
            and (
                current.flags == expected_flags
                if task.mode == "create"
                else bool(current.flags & UNSIGNED_FLAG) == task.unsigned
            )
            and current.entry_type == CHANNEL_CONTENT
        ):
            if task.mode == "adopt":
                changes.append(f"slot {task.slot}: refresh adopted task now ({task.filename})")
                _adopt_task(data, manifest, task)
            else:
                changes.append(f"slot {task.slot}: already configured ({task.filename})")
            continue
        if task.mode == "adopt":
            changes.append(f"slot {task.slot}: adopt native {task.filename} -> {expected_url}")
            _adopt_task(data, manifest, task)
            continue
        action = "update" if current else "create"
        changes.append(f"slot {task.slot}: {action} {task.filename} -> {expected_url}")
        _write_task(data, manifest, task)

    if not apply:
        return changes, None
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.before-{manifest.channel_id.lower()}-{timestamp}.bak")
    shutil.copy2(path, backup)
    path.write_bytes(data)
    return changes, backup
