"""Read-only original HFNJ header CRC comparisons on synthetic twelve-byte data.

This executes only the native CRC leaf routine. The loader, dataset records,
signature/encryption trust, saves and measurements are not executed or verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import zlib

SOURCE_BYTES = 4110944
SOURCE_SHA256 = 'ca6677094a9293219b4122038b916cb64f6361b5b4106a670ade438292d4969c'
CRC_ENTRY, CRC_END = 0x80146CD4, 0x80146E10
CRC_TABLE, CRC_TABLE_END = 0x80381620, 0x80381660


def synthetic_crc_cases():
    generator = random.Random(256)
    return [bytes(12), b'\xFF' * 12, bytes(range(12)),
            *(bytes(generator.randrange(256) for _ in range(12)) for _ in range(64))]


def verify_header_crc(source: bytes, cases):
    """Compare native CRC against zlib, exposing only counts and scope.

    Exactly twelve supplied bytes represent the application's covered header
    region, not health records or an authenticated/downloadable dataset.
    """
    if (not isinstance(source, bytes) or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('Body Check Japanese v256 executable fingerprint mismatch')
    if (not isinstance(cases, (list, tuple)) or not 1 <= len(cases) <= 256
            or any(not isinstance(case, bytes) or len(case) != 12 for case in cases)):
        raise ValueError('Expected bounded synthetic twelve-byte CRC cases')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Body Check executable section exceeds emulation bounds')
        cpu.mem_write(address, source[offset:offset + size])
    pointer, stop, guard = 0x81100000, 0x817FF000, b'CRC-GUARD!' * 4
    cpu.mem_write(pointer - len(guard), guard)
    cpu.mem_write(pointer + 12, guard)
    instructions = 0

    def code(_cpu, address, _size, _context):
        nonlocal instructions
        instructions += 1
        if not CRC_ENTRY <= address < CRC_END:
            raise ValueError('Unexpected original Body Check CRC control flow')

    def read(_cpu, _access, address, size, _value, _context):
        if not (pointer <= address < address + size <= pointer + 12
                or CRC_TABLE <= address < address + size <= CRC_TABLE_END):
            raise ValueError('Original Body Check CRC read exceeds synthetic input/table bounds')

    def write(*_args):
        raise ValueError('Original Body Check CRC unexpectedly attempted a memory write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for case in cases:
        cpu.mem_write(pointer, case)
        cpu.reg_write(UC_PPC_REG_0 + 3, pointer)
        cpu.reg_write(UC_PPC_REG_0 + 4, 12)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(CRC_ENTRY, stop, count=2000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Original Body Check CRC exceeded instruction cap')
        if cpu.reg_read(UC_PPC_REG_0 + 3) != zlib.crc32(case):
            raise ValueError('Original Body Check CRC differs from independent zlib result')
        if (bytes(cpu.mem_read(pointer, 12)) != case
                or bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + 12, len(guard))) != guard):
            raise ValueError('Original Body Check CRC input/guard changed')
    return {'original_main_sha256': SOURCE_SHA256,
            'synthetic_crc_cases': len(cases), 'covered_bytes_per_case': 12,
            'native_crc_matches_zlib': True, 'native_crc_stubbed': False,
            'bounded_input_and_original_table_reads': True,
            'input_guards_verified': True, 'native_memory_writes_attempted': False,
            'instructions': instructions,
            'native_dataset_loader_executed': False,
            'dataset_records_or_authentication_verified': False,
            'save_or_profile_modified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='private original decoded HFNJ v256 application DOL')
    args = parser.parse_args(argv)
    try:
        with args.source.open('rb') as stream:
            source = stream.read(SOURCE_BYTES + 1)
        result = verify_header_crc(source, synthetic_crc_cases())
    except (OSError, ValueError, ImportError):
        print('Body Check native CRC verification input or optional dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
