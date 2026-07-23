from __future__ import annotations

import datetime as dt
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path


FILE_SIZE = 0x400
MAGIC = 0x57634366  # WcCf
VERSION = 8
STAGE_OFFSET = 0x14
ENABLE_BOOTING_OFFSET = 0x3F8
CHECKSUM_OFFSET = 0x3FC
STAGE_INITIAL = 0
STAGE_GENERATED = 1
STAGE_REGISTERED = 2


@dataclass(frozen=True)
class ConfigSummary:
    nwc24_id: int
    id_generation: int
    creation_stage: int
    enable_booting: int
    stored_checksum: int
    calculated_checksum: int

    @property
    def checksum_valid(self) -> bool:
        return self.stored_checksum == self.calculated_checksum


def _u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def _u64(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">Q", data, offset)[0]


def _put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into(">I", data, offset, value)


def checksum(data: bytes | bytearray) -> int:
    return sum(_u32(data, offset) for offset in range(0, CHECKSUM_OFFSET, 4)) & 0xFFFFFFFF


def validate(data: bytes | bytearray) -> None:
    if len(data) != FILE_SIZE:
        raise ValueError(f"unexpected nwc24msg.cfg size {len(data)} (expected {FILE_SIZE})")
    if _u32(data, 0) != MAGIC:
        raise ValueError("WC24 config has invalid WcCf magic")
    if _u32(data, 4) != VERSION:
        raise ValueError("WC24 config version is not 8")
    if _u32(data, 0x10) > 0x1F:
        raise ValueError("WC24 config has an invalid ID generation counter")


def read(path: Path) -> bytearray:
    data = bytearray(path.read_bytes())
    validate(data)
    return data


def summarize(data: bytes | bytearray) -> ConfigSummary:
    validate(data)
    return ConfigSummary(
        nwc24_id=_u64(data, 8),
        id_generation=_u32(data, 0x10),
        creation_stage=_u32(data, STAGE_OFFSET),
        enable_booting=_u32(data, ENABLE_BOOTING_OFFSET),
        stored_checksum=_u32(data, CHECKSUM_OFFSET),
        calculated_checksum=checksum(data),
    )


def bootstrap_local(path: Path, apply: bool) -> tuple[ConfigSummary, ConfigSummary, Path | None]:
    original = read(path)
    data = bytearray(original)
    before = summarize(data)
    if not before.checksum_valid:
        raise ValueError(
            f"refusing invalid WC24 config: checksum {before.stored_checksum:08x} "
            f"!= {before.calculated_checksum:08x}"
        )
    if before.nwc24_id == 0 or before.creation_stage == STAGE_INITIAL:
        raise ValueError("WC24 ID has not been generated; run the 4.3J WC24 setup first")
    if before.creation_stage not in {STAGE_GENERATED, STAGE_REGISTERED}:
        raise ValueError(f"unsupported WC24 creation stage: {before.creation_stage}")

    _put_u32(data, STAGE_OFFSET, STAGE_REGISTERED)
    _put_u32(data, ENABLE_BOOTING_OFFSET, 1)
    _put_u32(data, CHECKSUM_OFFSET, checksum(data))
    after = summarize(data)
    if not apply or data == original:
        return before, after, None

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.before-jwc24-registration-{timestamp}.bak")
    shutil.copy2(path, backup)
    path.write_bytes(data)
    return before, after, backup
