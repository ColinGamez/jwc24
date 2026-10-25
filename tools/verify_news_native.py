"""Guarded Japanese HAGJ v7 news-buffer validation on synthetic input only.

The full original validator and CRC execute. Time/calendar services are explicit
stubs. No signatures, downloads, storage, actual news or native UI are involved.
"""
from __future__ import annotations

import hashlib
import struct

SOURCE_SHA256 = '8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852'
ENTRY = 0x8000AFC8
CRC = 0x8007621C
MAX_BODY_BYTES = 65536
MAX_INSTRUCTIONS = 10000000


def verify_news_buffers(source, buffers, *, current_minute=10000, current_hour=0):
    """Return native status, slot choices and mutation counts, never news bytes.

    There must be exactly 24 bytes-or-None slots. A missing hourly slot can yield
    native -2 even if the present payload is structurally valid; -2 is not an
    authenticated startup result. The validator can remove unresolved/oversized
    article references from the latest topic lists in synthetic RAM.
    """
    if (not isinstance(source, bytes) or len(source) > 4 * 1024 * 1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('Japanese News v7 executable fingerprint mismatch')
    if (not isinstance(buffers, (tuple, list)) or len(buffers) != 24
            or any(value is not None and (not isinstance(value, bytes)
                   or not 104 <= len(value) <= MAX_BODY_BYTES) for value in buffers)):
        raise ValueError('Expected 24 bounded synthetic News buffer slots')
    if (type(current_minute) is not int or not 0 <= current_minute <= 0xFFFFF000
            or type(current_hour) is not int or not 0 <= current_hour < 24):
        raise ValueError('Expected bounded synthetic News time fields')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC

    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    pointers, sizes, selected, mask = 0x81000000, 0x81000100, 0x81000200, 0x81000300
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'N' * 32
    allocated = []
    for index, value in enumerate(buffers):
        address = 0x81100000 + index * 0x20000
        if value is not None:
            cpu.mem_write(address - 32, guard)
            cpu.mem_write(address, value)
            cpu.mem_write(address + len(value), guard)
            allocated.append((index, address, value))
        cpu.mem_write(pointers + index * 4, struct.pack('>I', address if value is not None else 0))
        cpu.mem_write(sizes + index * 4, struct.pack('>I', len(value) if value is not None else 0))
    fixed = ((pointers, 96), (sizes, 96), (selected, 4), (mask, 4))
    for address, size in fixed:
        cpu.mem_write(address - 32, guard)
        cpu.mem_write(address + size, guard)
    cpu.mem_write(selected, b'\xFF' * 4)
    cpu.mem_write(mask, b'\xFF' * 4)
    cpu.mem_write(stack_lo - 32, guard)
    cpu.mem_write(stack_hi, guard)
    pointer_bytes = bytes(cpu.mem_read(pointers, 96))
    size_bytes = bytes(cpu.mem_read(sizes, 96))
    counts = {'instructions': 0, 'crc_calls': 0, 'now_calls': 0,
              'tick_calls': 0, 'calendar_calls': 0}
    body_ranges = [(address, address + len(value)) for _, address, value in allocated]

    def return_stub(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value)
        cpu.reg_write(UC_PPC_REG_0 + 4, 0)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def instruction(_cpu, address, _size, _context):
        counts['instructions'] += 1
        if address == 0x80044F08:
            counts['now_calls'] += 1
            return_stub(current_minute)
            return
        if address == 0x80106E9C:
            counts['tick_calls'] += 1
            return_stub()
            return
        if address == 0x80076138:
            counts['calendar_calls'] += 1
            output = cpu.reg_read(UC_PPC_REG_0 + 3)
            if not stack_lo <= output <= stack_hi - 40:
                raise ValueError('Unexpected News calendar output pointer')
            cpu.mem_write(output, struct.pack('>10I', 0, 0, current_hour, 1, 0, 2000, 6, 0, 0, 0))
            return_stub(1)
            return
        allowed = ((ENTRY, 0x8000BE30), (CRC, 0x80076350),
                   (0x8017A5FC, 0x8017A678))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError('Unexpected native News validator control flow')
        if address == CRC:
            counts['crc_calls'] += 1

    def read(_cpu, _access, address, size, _value, _context):
        allowed = body_ranges + [(pointers, pointers + 96), (sizes, sizes + 96),
                  (selected, selected + 4), (mask, mask + 4), (stack_lo, stack_hi),
                  (0x801AAC88, 0x801AACC8)]  # Original CRC nibble table.
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Native News read exceeds synthetic input bounds')

    def write(_cpu, _access, address, size, _value, _context):
        pc = cpu.reg_read(UC_PPC_REG_PC)
        if ((stack_lo <= address < address + size <= stack_hi)
                or (selected <= address < address + size <= selected + 4)
                or (mask <= address < address + size <= mask + 4)):
            return
        if pc in (0x8000BB3C, 0x8000BB44, 0x8000BB5C) and any(
                lo <= address < address + size <= hi for lo, hi in body_ranges):
            return
        raise ValueError('Unexpected native News validator write')

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for index, value in {1: stack, 3: pointers, 4: sizes, 5: selected, 6: mask}.items():
        cpu.reg_write(UC_PPC_REG_0 + index, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(ENTRY, stop, count=MAX_INSTRUCTIONS)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native News validator exceeded instruction cap')
    for address, size in fixed:
        if (bytes(cpu.mem_read(address - 32, 32)) != guard
                or bytes(cpu.mem_read(address + size, 32)) != guard):
            raise ValueError('Native News fixture guard changed')
    changed = []
    for index, address, value in allocated:
        if (bytes(cpu.mem_read(address - 32, 32)) != guard
                or bytes(cpu.mem_read(address + len(value), 32)) != guard):
            raise ValueError('Native News body guard changed')
        if bytes(cpu.mem_read(address, len(value))) != value:
            changed.append(index)
    if (bytes(cpu.mem_read(pointers, 96)) != pointer_bytes
            or bytes(cpu.mem_read(sizes, 96)) != size_bytes
            or bytes(cpu.mem_read(stack_lo - 32, 32)) != guard
            or bytes(cpu.mem_read(stack_hi, 32)) != guard):
        raise ValueError('Native News input table or stack guard changed')
    status = cpu.reg_read(UC_PPC_REG_0 + 3)
    status = status - 0x100000000 if status >= 0x80000000 else status
    selected_slot = struct.unpack('>i', cpu.mem_read(selected, 4))[0]
    return {'status': status, 'selected_slot': selected_slot,
            'refresh_mask': struct.unpack('>I', cpu.mem_read(mask, 4))[0],
            'mutated_slots': changed, 'counts': counts,
            'native_validator_and_crc_stubbed': False,
            'synthetic_time_services_stubbed': True,
            'input_and_stack_guards_verified': True,
            'signatures_download_storage_or_ui_verified': False}
