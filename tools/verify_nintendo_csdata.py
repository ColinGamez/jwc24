"""Run selected original HATJ v1792 CSData consumers with bounded synthetic RAM.

Original executable bytes remain a private input. No service, NAND or device is
used. The header prefix stops before URL construction; log calls are stubbed.
The configured maximum reference length is explicitly synthetic.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_csdata import (
    MAX_CSDATA_BYTES, decompress_csdata,
)

SOURCE_SHA = 'aef18b3a045c09b0a1c4dfdd9aed99f78bd4a6be8c0a967deea3e6aa93523264'
SOURCE_BYTES = 4194944
MAX_INSTRUCTIONS = 3000000


def verify_csdata_native(source: bytes, payload: bytes, *, decompress=False,
                         configured_reference_limit=255) -> dict[str, object]:
    """Return metadata-only native results, without exporting input or DOL bytes.

    Decompression mode requires a safely decoded input before native execution;
    this is not a native malformed-stream safety test. Header mode may vary CRC,
    version/status and reference bytes, but never permits an out-of-buffer CRC.
    """
    if (not isinstance(source, bytes) or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    if (type(decompress) is not bool or type(configured_reference_limit) is not int
            or not 0 <= configured_reference_limit <= 255):
        raise ValueError('Expected bounded synthetic CSData fixture options')
    if not isinstance(payload, bytes):
        raise ValueError('Expected bounded synthetic CSData bytes')
    expected = None
    if decompress:
        expected, kind = decompress_csdata(payload)
        if kind == 'none':
            raise ValueError('Native decompression fixture must use LZ10 or LZ11')
    elif not 12 <= len(payload) <= MAX_CSDATA_BYTES:
        raise ValueError('Synthetic CSData header buffer is outside the supported range')
    elif struct.unpack_from('>I', payload, 4)[0] > len(payload):
        raise ValueError('Synthetic CSData declared size exceeds its buffer')

    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Native DOL section is outside the emulation map')
        cpu.mem_write(address, source[offset:offset + size])
    data, obj, output = 0x81010000, 0x81001000, 0x81040000
    stack_begin, stack_end, stop = 0x817DC000, 0x817E1000, 0x817FF000
    guard = b'CS-GUARD!' * 4
    cpu.mem_write(data - len(guard), guard)
    cpu.mem_write(data, payload)
    cpu.mem_write(data + len(payload), guard)
    cpu.mem_write(obj - len(guard), guard)
    cpu.mem_write(obj, struct.pack('>I', data) + bytes(0x220 - 4))
    cpu.mem_write(obj + 0x220, guard)
    cpu.mem_write(stack_begin - len(guard), guard)
    cpu.mem_write(stack_end, guard)
    cpu.mem_write(output - len(guard), guard)
    output_length = len(expected) if expected is not None else 0
    cpu.mem_write(output, b'\xA5' * output_length)
    cpu.mem_write(output + output_length, guard)
    # The selected original accessor reads only this configured SDA slot.
    sda, limit_slot = 0x81008000, 0x810031F8
    cpu.mem_write(limit_slot, struct.pack('>I', configured_reference_limit))
    calls = logs = 0
    reached_construction = False
    crc_executed = False
    allowed = ((0x800324D0, 0x800326EC), (0x800326F0, 0x80032718),
               (0x80032890, 0x80032998), (0x80031440, 0x800314AC),
               (0x80025160, 0x80025198), (0x8033FDF8, 0x8033FF00),
               (0x802A2250, 0x802A2388), (0x80100A20, 0x80100BAC))

    def code(_cpu, address, _size, _context):
        nonlocal calls, logs, reached_construction, crc_executed
        calls += 1
        if address == 0x802A2250:
            crc_executed = True
        if address == 0x800325F8:
            reached_construction = True
            cpu.emu_stop()
            return
        if address == 0x80027070:
            logs += 1
            cpu.reg_write(UC_PPC_REG_0 + 3, 0)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if not any(begin <= address < end for begin, end in allowed):
            raise ValueError('Unexpected native CSData control flow')

    def write(_cpu, _access, address, size, _value, _context):
        permitted = (stack_begin <= address < address + size <= stack_end)
        if decompress:
            permitted |= output <= address < address + size <= output + output_length
        else:
            permitted |= obj <= address < address + size <= obj + 0x220
            permitted |= data + 8 <= address < address + size <= data + 12
        if not permitted:
            raise ValueError('Unexpected native CSData write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for index, value in {1: 0x817E0000, 13: sda, 3: data if decompress else obj,
                         4: output if decompress else data}.items():
        cpu.reg_write(UC_PPC_REG_0 + index, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80100A60 if decompress else 0x800324D0, stop, count=MAX_INSTRUCTIONS)
    if not reached_construction and cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native CSData execution exceeded its instruction cap')
    checks = ((data - len(guard), guard), (data, payload),
              (data + len(payload), guard), (obj - len(guard), guard),
              (obj + 0x220, guard), (stack_begin - len(guard), guard),
              (stack_end, guard), (output - len(guard), guard),
              (output + output_length, guard),
              (limit_slot, struct.pack('>I', configured_reference_limit)))
    for address, value in checks:
        if bytes(cpu.mem_read(address, len(value))) != value:
            raise ValueError('Native CSData input or fixture guard changed')
    if decompress and bytes(cpu.mem_read(output, output_length)) != expected:
        raise ValueError('Native CSData decompression differs from independent decoder')
    return {
        'native_header_prefix_result': None if decompress or reached_construction else cpu.reg_read(UC_PPC_REG_0 + 3),
        'reached_reference_construction_boundary': reached_construction,
        'native_crc_mocked': False,
        'native_crc_executed': crc_executed,
        'native_decompressor_executed': decompress,
        'decompressed_bytes': output_length if decompress else None,
        'native_decompression_matches_independent_decoder': decompress,
        'guard_checks_passed': True,
        'instructions': calls,
        'log_calls_stubbed': logs,
        'url_construction_or_full_load_verified': False,
        'native_download_or_ui_verified': False,
    }
