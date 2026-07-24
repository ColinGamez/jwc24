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
EMAIL_OFFSET = 0x18
MAIL_SECRET_OFFSET = 0x58
MLCHKID_OFFSET = 0x78
URLS_OFFSET = 0x9C
URL_LENGTH = 0x80
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


def _read_c_string(data: bytes | bytearray, offset: int, length: int) -> str:
    return bytes(data[offset : offset + length]).split(b"\0", 1)[0].decode("ascii")


def _put_c_string(data: bytearray, offset: int, length: int, value: str) -> None:
    encoded = value.encode("ascii")
    if len(encoded) >= length:
        raise ValueError(f"value is too long for WC24 config field ({length - 1} bytes)")
    data[offset : offset + length] = b"\0" * length
    data[offset : offset + len(encoded)] = encoded


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


def mail_urls(data: bytes | bytearray) -> tuple[str, ...]:
    validate(data)
    return tuple(
        _read_c_string(data, URLS_OFFSET + index * URL_LENGTH, URL_LENGTH)
        for index in range(5)
    )


def mail_credentials_present(data: bytes | bytearray) -> tuple[bool, bool]:
    validate(data)
    return (
        bool(_read_c_string(data, MAIL_SECRET_OFFSET, 0x20)),
        bool(_read_c_string(data, MLCHKID_OFFSET, 0x24)),
    )


def configure_mail(
    path: Path,
    base_url: str,
    password: str,
    mlchkid: str,
    apply: bool,
) -> tuple[tuple[str, ...], tuple[str, ...], Path | None]:
    original = read(path)
    state = summarize(original)
    if not state.checksum_valid or state.creation_stage != STAGE_REGISTERED:
        raise ValueError("WC24 config must be valid and registered before mail provisioning")
    if len(password) > 31 or not password:
        raise ValueError("mail password must contain 1..31 ASCII characters")
    if len(mlchkid) != 32:
        raise ValueError("mail check ID must contain exactly 32 ASCII characters")
    base = base_url.rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("mail base URL must be absolute HTTP(S)")
    endpoints = ("account.cgi", "check.cgi", "receive.cgi", "delete.cgi", "send.cgi")
    desired_urls = tuple(f"{base}/cgi-bin/{endpoint}" for endpoint in endpoints)
    data = bytearray(original)
    _put_c_string(data, EMAIL_OFFSET, 0x40, f"w{state.nwc24_id:016d}@wii.com")
    _put_c_string(data, MAIL_SECRET_OFFSET, 0x20, password)
    _put_c_string(data, MLCHKID_OFFSET, 0x24, mlchkid)
    for index, url in enumerate(desired_urls):
        _put_c_string(data, URLS_OFFSET + index * URL_LENGTH, URL_LENGTH, url)
    _put_u32(data, CHECKSUM_OFFSET, checksum(data))
    before_urls = mail_urls(original)
    after_urls = mail_urls(data)
    if not apply or data == original:
        return before_urls, after_urls, None
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.before-jwc24-mail-{timestamp}.bak")
    shutil.copy2(path, backup)
    path.write_bytes(data)
    return before_urls, after_urls, backup
