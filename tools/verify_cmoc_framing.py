"""Run the Japanese CMOC v512 framing routines against bounded synthetic bytes.

The original executable is a private local input. This is not a network server,
Mii decoder, authentication check, or evidence of accepted startup records.
"""
from __future__ import annotations

import hashlib
import struct

SOURCE_SHA256 = '3957942d54501633bd7d256c636517885958ed152d9c914f4e07aadecf84a5b3'
MAX_BYTES = 1024 * 1024
MAX_RECORDS = 4096
_CONSTRUCT = 0x800695D0
_HEADER = 0x80069634
_PEEK = 0x8006966C
_NEXT = 0x80069728
_SIZE = 0x80068344
_MATCH = 0x8006A57C


class NativeFramingBoundsError(ValueError):
    """The original routine attempted a read outside a synthetic input buffer."""


def verify_framing(source: bytes, data: bytes, *, expected_header: bytes | None = None):
    """Return offsets, sizes and flags only; no source, Mii or header identity bytes.

    A zero short size selects the native 32-bit accessor at record+12. Reads
    beyond the declared body are trapped, including the native iterator's
    unchecked extended-size read. Successful iteration proves framing alone.
    """
    if (not isinstance(source, bytes) or len(source) > 4 * 1024 * 1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC v512 executable fingerprint mismatch')
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ValueError('Expected bounded synthetic response bytes')
    if expected_header is not None and (not isinstance(expected_header, bytes)
                                        or len(expected_header) != 32):
        raise ValueError('Expected exactly 32 synthetic header bytes')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC

    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    obj, body, expected = 0x81000000, 0x81100000, 0x81300000
    stack_lo, stack_hi, stop = 0x817D0000, 0x817E1000, 0x817FF000
    guard = b'G' * 32
    cpu.mem_write(obj - 32, guard)
    cpu.mem_write(obj, b'\xA5' * 24)
    cpu.mem_write(obj + 24, guard)
    for pointer, value in ((body, data), (expected, expected_header or bytes(32))):
        cpu.mem_write(pointer - 32, guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(stack_lo - 32, guard)
    cpu.mem_write(stack_hi, guard)
    allowed_code = ((_CONSTRUCT, 0x80069618), (_HEADER, 0x800697F4),
                    (_SIZE, 0x80068360), (_MATCH, 0x8006A5BC))
    instructions = 0

    def code(_cpu, address, _size, _context):
        nonlocal instructions
        instructions += 1
        if not any(lo <= address < hi for lo, hi in allowed_code):
            raise ValueError('Unexpected native CMOC control flow')

    def read(_cpu, _access, address, size, _value, _context):
        allowed = ((obj, obj + 24), (body, body + len(data)),
                   (expected, expected + 32), (stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise NativeFramingBoundsError('Native CMOC read exceeds synthetic input bounds')

    def write(_cpu, _access, address, size, _value, _context):
        if not ((obj <= address < address + size <= obj + 24)
                or (stack_lo <= address < address + size <= stack_hi)):
            raise ValueError('Unexpected native CMOC write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def run(entry, *arguments):
        cpu.reg_write(UC_PPC_REG_0 + 1, 0x817E0000)
        for index, value in enumerate(arguments, 3):
            cpu.reg_write(UC_PPC_REG_0 + index, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(entry, stop, count=2000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Native CMOC instruction limit reached')
        return cpu.reg_read(UC_PPC_REG_0 + 3)

    run(_CONSTRUCT, obj, body, len(data))
    header_present = run(_HEADER, obj) == body
    matches = (bool(run(_MATCH, body, expected))
               if header_present and expected_header is not None else None)
    records = []
    for _ in range(MAX_RECORDS + 1):
        record = run(_PEEK, obj)
        if record == 0:
            break
        if len(records) >= MAX_RECORDS:
            raise ValueError('Native CMOC record count exceeds harness cap')
        size = run(_SIZE, record)
        if run(_NEXT, obj) != record:
            raise ValueError('Native CMOC peek and advance disagree')
        records.append({'offset': record - body, 'size': size})
    cursor = struct.unpack('>Q', cpu.mem_read(obj + 8, 8))[0]
    for pointer, value in ((body, data), (expected, expected_header or bytes(32))):
        if (bytes(cpu.mem_read(pointer - 32, 32)) != guard
                or bytes(cpu.mem_read(pointer, len(value))) != value
                or bytes(cpu.mem_read(pointer + len(value), 32)) != guard):
            raise ValueError('Native CMOC input or guards changed')
    if (bytes(cpu.mem_read(obj - 32, 32)) != guard
            or bytes(cpu.mem_read(obj + 24, 32)) != guard
            or bytes(cpu.mem_read(obj + 4, 4)) != b'\xA5' * 4
            or bytes(cpu.mem_read(stack_lo - 32, 32)) != guard
            or bytes(cpu.mem_read(stack_hi, 32)) != guard):
        raise ValueError('Native CMOC object or stack guards changed')
    return {'header_present': header_present, 'header_matches': matches,
            'records': records, 'cursor': cursor,
            'unconsumed_bytes': max(0, len(data) - cursor),
            'native_instructions': instructions, 'native_routines_stubbed': False,
            'input_object_and_stack_guards_verified': True,
            'network_authentication_or_startup_verified': False}
