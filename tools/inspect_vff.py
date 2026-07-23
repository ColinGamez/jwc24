from __future__ import annotations

import argparse
import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path


SECTOR_SIZE = 512
VFF_SECTOR_BIAS = 480


def align(value: int, amount: int) -> int:
    return (value + amount - 1) & ~(amount - 1)


@dataclass(frozen=True)
class Geometry:
    fat_bits: int
    cluster_size: int
    cluster_count: int
    fat_sectors: int
    directory_sector: int
    data_sector: int


def sector_offset(sector: int) -> int:
    if sector == 0:
        raise ValueError("VFF sector zero is the 32-byte container header")
    return sector * SECTOR_SIZE - VFF_SECTOR_BIAS


def geometry(data: bytes) -> Geometry:
    if len(data) < 32 or data[:4] != b"VFF ":
        raise ValueError("not a VFF container")
    endianness, _, volume_size, cluster_units = struct.unpack_from(">HHIH", data, 4)
    if endianness != 0xFEFF:
        raise ValueError(f"unsupported VFF endianness: {endianness:#06x}")
    cluster_size = cluster_units * 16
    if cluster_size != SECTOR_SIZE:
        raise ValueError(f"unsupported cluster size: {cluster_size}")
    cluster_count = volume_size // cluster_size
    if cluster_count < 4085:
        fat_bits = 12
        fat_bytes = align(((cluster_count + 1) // 2) * 3, cluster_size)
    elif cluster_count < 65525:
        fat_bits = 16
        fat_bytes = align(cluster_count * 2, cluster_size)
    else:
        raise ValueError("VFF is neither FAT12 nor FAT16")
    fat_sectors = fat_bytes // SECTOR_SIZE
    directory_sector = 1 + fat_sectors * 2
    data_sector = directory_sector + 8
    return Geometry(fat_bits, cluster_size, cluster_count, fat_sectors, directory_sector, data_sector)


def fat12_next(fat: bytes, cluster: int) -> int:
    offset = cluster + cluster // 2
    pair = int.from_bytes(fat[offset : offset + 2], "little")
    return (pair >> 4) & 0xFFF if cluster & 1 else pair & 0xFFF


def short_name(entry: bytes) -> str:
    stem = entry[:8].decode("ascii", errors="replace").rstrip()
    suffix = entry[8:11].decode("ascii", errors="replace").rstrip()
    return f"{stem}.{suffix}" if suffix else stem


def extract_file(data: bytes, geo: Geometry, first_cluster: int, size: int) -> bytes:
    fat_start = sector_offset(1)
    fat = data[fat_start : fat_start + geo.fat_sectors * SECTOR_SIZE]
    output = bytearray()
    seen: set[int] = set()
    cluster = first_cluster
    end_of_chain = 0xFF8 if geo.fat_bits == 12 else 0xFFF8
    while 2 <= cluster < end_of_chain and len(output) < size:
        if cluster in seen:
            raise ValueError("FAT12 cluster loop")
        seen.add(cluster)
        sector = geo.data_sector + cluster - 2
        offset = sector_offset(sector)
        output.extend(data[offset : offset + geo.cluster_size])
        cluster = (
            fat12_next(fat, cluster)
            if geo.fat_bits == 12
            else int.from_bytes(fat[cluster * 2 : cluster * 2 + 2], "little")
        )
    return bytes(output[:size])


def lz10_literal(payload: bytes) -> bytes:
    output = bytearray((0x10,))
    output.extend(len(payload).to_bytes(3, "little"))
    for offset in range(0, len(payload), 8):
        output.append(0)
        output.extend(payload[offset : offset + 8])
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a big-endian FAT12 WC24 VFF.")
    parser.add_argument("vff", type=Path)
    parser.add_argument("--compare", type=Path, help="compare HEADER.BIN with a local payload")
    args = parser.parse_args()

    data = args.vff.read_bytes()
    geo = geometry(data)
    print(
        f"VFF: size={len(data)} FAT{geo.fat_bits} clusters={geo.cluster_count} "
        f"fat_sectors={geo.fat_sectors} data_sector={geo.data_sector}"
    )
    directory_offset = sector_offset(geo.directory_sector)
    directory = data[directory_offset : directory_offset + 4096]
    files: dict[str, bytes] = {}
    for offset in range(0, len(directory), 32):
        entry = directory[offset : offset + 32]
        if entry[0] in {0x00, 0xE5} or entry[11] == 0x0F:
            continue
        name = short_name(entry)
        first_cluster = int.from_bytes(entry[26:28], "little")
        size = int.from_bytes(entry[28:32], "little")
        payload = extract_file(data, geo, first_cluster, size)
        files[name.upper()] = payload
        digest = hashlib.sha256(payload).hexdigest().upper()
        print(f"{name}: size={size} cluster={first_cluster} sha256={digest}")

    if args.compare:
        current = files.get("HEADER.BIN")
        if current is None:
            raise SystemExit("HEADER.BIN is not present in the live VFF directory")
        expected = args.compare.read_bytes()
        print(f"HEADER.BIN equals {args.compare}: {current == expected}")
        print(f"HEADER.BIN equals LZ10({args.compare}): {current == lz10_literal(expected)}")
        print(f"HEADER.BIN prefix: {current[:16].hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
