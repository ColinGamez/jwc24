"""Original CMOC SDK status/header lookup and scanf on synthetic HTTP storage."""
from __future__ import annotations

import hashlib
import struct

from jwc24.cmoc_http import decode_completion_transport
from tools.verify_cmoc_framing import SOURCE_SHA256


def verify_http_transport(source: bytes, **inputs):
    expected = decode_completion_transport(**inputs)
    if (type(source) is not bytes or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    layout = sections(source)
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in layout:
        cpu.mem_write(address, source[offset:offset + size])
    wrapper, response, names, heap_base = 0x81000000, 0x81100000, 0x81200000, 0x81300000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    raw = b'HTTP/1.1 200 OK\r\n' + b''.join(name + b': ' + value + b'\r\n'
                                                   for name, value in inputs['headers']) + b'\r\n'
    response_bytes = bytearray(0x438)
    struct.pack_into('>I', response_bytes, 0, len(raw))
    struct.pack_into('>II', response_bytes, 0x14, int(inputs['response_ready']),
                     (inputs['status_field'] or 0) & 0xFFFFFFFF)
    response_bytes[0x38:0x38 + len(raw)] = raw
    available = inputs['status_field'] is not None
    objects = ((wrapper, struct.pack('>I', 77 if available else 0)),
               (response, bytes(response_bytes)), (names, b'X-RESULT\0X-MC-HOST\0'))
    guard = b'S' * 32
    for pointer, value in objects:
        cpu.mem_write(pointer - 32, guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(stack_lo - 32, guard)
    cpu.mem_write(stack_hi, guard)
    allocations = []
    counts = {'instructions': 0, 'allocations': 0, 'frees': 0,
              'registry_boundaries': 0, 'sdk_header_lookups': 0,
              'native_scanf_calls': 0, 'native_status_getters': 0}

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        counts['instructions'] += 1
        if address in (0x8019E0E8, 0x8019E16C, 0x8019DD14):
            counts['registry_boundaries'] += 1
            ret(response if address == 0x8019DD14 and available else 0)
            return
        if address == 0x80196958:
            size = cpu.reg_read(UC_PPC_REG_0 + 3)
            if not 0 < size <= 1024 or len(allocations) >= 4:
                raise ValueError('Unexpected synthetic CMOC HTTP allocation')
            pointer = heap_base + len(allocations) * 0x1000
            cpu.mem_write(pointer - 32, guard)
            cpu.mem_write(pointer, bytes(size))
            cpu.mem_write(pointer + size, guard)
            allocations.append((pointer, size))
            counts['allocations'] += 1
            ret(pointer)
            return
        if address == 0x801969B4:
            if cpu.reg_read(UC_PPC_REG_0 + 3) not in [pointer for pointer, _ in allocations]:
                raise ValueError('Unexpected synthetic CMOC HTTP free')
            counts['frees'] += 1
            ret()
            return
        allowed = ((0x8007A19C, 0x8007A27C), (0x800D64D0, 0x800D6580),
                   (0x800D5F08, 0x800D6000),
                   (0x800DC000, 0x800E8000), (0x80197500, 0x80199A00),
                   (0x8019D458, 0x8019D610), (0x80004000, 0x80004104))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError('Unexpected native CMOC HTTP accessor control flow')
        for entry, key in ((0x80198828, 'sdk_header_lookups'),
                           (0x800DDE70, 'native_scanf_calls'),
                           (0x8019D5B0, 'native_status_getters')):
            if address == entry:
                counts[key] += 1

    def read(_cpu, _access, address, size, _value, _context):
        allowed = [(pointer, pointer + len(value)) for pointer, value in objects]
        allowed += [(pointer, pointer + length) for pointer, length in allocations]
        allowed += [(base, base + length) for index, _, base, length in layout if index >= 7]
        allowed.append((stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Native CMOC HTTP read exceeds fixture/static-data bounds')

    def write(_cpu, _access, address, size, _value, _context):
        allowed = [(stack_lo, stack_hi), (response + 0x24, response + 0x28)]
        allowed += [(pointer, pointer + length) for pointer, length in allocations]
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Unexpected native CMOC HTTP accessor write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def run(entry, *arguments):
        for register, value in {1: stack, 2: 0x80435BE0, 13: 0x80432BA0}.items():
            cpu.reg_write(UC_PPC_REG_0 + register, value)
        for register, value in enumerate(arguments, 3):
            cpu.reg_write(UC_PPC_REG_0 + register, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(entry, stop, count=250000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Native CMOC HTTP accessor instruction cap reached')
        return cpu.reg_read(UC_PPC_REG_0 + 3)

    signed = lambda value: value - 0x100000000 if value >= 0x80000000 else value
    status = signed(run(0x8007A19C, wrapper))
    result = signed(run(0x8007A21C, wrapper, names, 0x8042AEAC))
    host_pointer = run(0x8007A1E8, wrapper, names + 9)
    host = None
    if host_pointer:
        length = next((size for pointer, size in allocations if pointer == host_pointer), None)
        if length is None:
            raise ValueError('Native CMOC host result is outside synthetic allocation')
        host = bytes(cpu.mem_read(host_pointer, length)).split(b'\0', 1)[0]
    if (status, result, host) != (expected.http_status, expected.x_result, expected.host_override):
        raise ValueError('Native CMOC HTTP conversion differs from independent component')
    for pointer, value in objects:
        actual = bytes(cpu.mem_read(pointer, len(value)))
        if pointer == response:
            actual = actual[:0x24] + value[0x24:0x28] + actual[0x28:]
        if (actual != value or bytes(cpu.mem_read(pointer - 32, 32)) != guard
                or bytes(cpu.mem_read(pointer + len(value), 32)) != guard):
            raise ValueError('Native CMOC HTTP input fixture changed')
    for pointer, size in allocations + [(stack_lo, stack_hi - stack_lo)]:
        if (bytes(cpu.mem_read(pointer - 32, 32)) != guard
                or bytes(cpu.mem_read(pointer + size, 32)) != guard):
            raise ValueError('Native CMOC HTTP heap/stack guard changed')
    return {**expected.metadata(), 'counts': counts,
            'sdk_header_lookup_and_scanf_stubbed': False,
            'registry_and_allocation_boundaries_stubbed': True,
            'input_heap_and_stack_guards_verified': True}
