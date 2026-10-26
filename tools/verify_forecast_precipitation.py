"""Bounded original HAFJ v7 precipitation block check; no service or device IO."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


SOURCE_SHA256 = 'ec33ec8eb2a8b9c76c2605ac6de2fd16dd5279b0c641d90746206a86a3a499b5'
SOURCE_BYTES = 1925536
BEGIN, END = 0x8000D2B0, 0x8000D310


def original_block(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) != SOURCE_BYTES or hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Original HAFJ v7 application identity does not match')
    # DOL text sections only. The guarded image supplies these tables; no
    # executable bytes are copied to the repository or modified on disk.
    for index in range(7):
        offset = struct.unpack_from('>I', data, index * 4)[0]
        address = struct.unpack_from('>I', data, 0x48 + index * 4)[0]
        size = struct.unpack_from('>I', data, 0x90 + index * 4)[0]
        if address <= BEGIN < END <= address + size:
            start = offset + BEGIN - address
            block = data[start:start + END - BEGIN]
            if len(block) == END - BEGIN:
                return block
    raise ValueError('Guarded application lacks the expected text block')


def verify(path: Path) -> dict:
    block = original_block(path)
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_PROT_READ, UC_PROT_EXEC)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_6, UC_PPC_REG_PC

    native = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    native.mem_map(0x8000D000, 0x1000)
    native.mem_write(BEGIN, block)
    native.mem_protect(0x8000D000, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
    row_page, row_address = 0x90000000, 0x90000080
    native.mem_map(row_page, 0x1000)
    native.mem_write(row_page, b'G' * 0x1000)
    native.mem_protect(row_page, 0x1000, UC_PROT_READ)
    accepted = rejected = 0
    for slot in range(4):
        for value in range(256):
            row = bytearray(0x20)
            row[0x12 + slot] = value
            native.mem_write(row_address, bytes(row))
            native.reg_write(UC_PPC_REG_6, row_address)
            # The isolated block only preserves r0 or changes it to -1.
            # Zero is synthetic incoming state, not a full-validator result.
            native.reg_write(UC_PPC_REG_0, 0)
            native.emu_start(BEGIN, END, timeout=100000, count=32)
            if native.reg_read(UC_PPC_REG_PC) != END:
                raise AssertionError('Original block did not reach its exact exit')
            expected = 0 if value <= 100 or value == 255 else 0xFFFFFFFF
            if native.reg_read(UC_PPC_REG_0) & 0xFFFFFFFF != expected:
                raise AssertionError(f'Original probability mismatch: slot {slot}, byte {value}')
            if (bytes(native.mem_read(row_address, len(row))) != bytes(row)
                    or bytes(native.mem_read(row_address - 32, 32)) != b'G' * 32
                    or bytes(native.mem_read(row_address + len(row), 32)) != b'G' * 32):
                raise AssertionError('Original probability block changed its guarded fixture')
            if expected:
                rejected += 1
            else:
                accepted += 1
    if bytes(native.mem_read(BEGIN, len(block))) != block:
        raise AssertionError('Original probability instructions changed during execution')
    return {
        'source_sha256': SOURCE_SHA256,
        'block_start': f'0x{BEGIN:08X}', 'block_exit': f'0x{END:08X}',
        'cases': accepted + rejected, 'preserved_zero_cases': accepted,
        'set_minus_one_cases': rejected, 'synthetic_register_and_record_state': True,
        'hooks_or_service_mocks': False, 'full_validator_executed': False,
        'read_only_code_and_record_pages': True, 'immutable_input_guards_verified': True,
        'caller_result_propagation_verified': False, 'native_ui_verified': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_app', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(verify(args.original_app), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
