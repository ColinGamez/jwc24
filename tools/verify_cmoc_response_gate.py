"""Guard the complete original CMOC HTTP-completion/header state handler.

Transport accessors, cached request lookup, singleton lookup and completion
callback are intercepted. Actual branch order/header checks/state update run.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.cmoc_response_gate import evaluate_response_gate
from tools.verify_cmoc_framing import SOURCE_SHA256


def verify_response_gate(source: bytes, data: bytes, **inputs):
    expected = evaluate_response_gate(data, **inputs)
    if (type(source) is not bytes or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    response, request, state, callback = 0x81000000, 0x81300000, 0x81400000, 0x81500000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    raw_object = bytearray(0xAE0 + len(data))
    raw_object[0x208] = inputs['response_flags']
    struct.pack_into('>I', raw_object, 0xADC, len(data))
    raw_object[0xAE0:] = data
    state_bytes = bytearray(b'\xA5' * 32)
    state_bytes[0x10] = inputs['limit_byte_2']
    state_bytes[0x11] = inputs['learned_byte_3']
    objects = ((response, bytes(raw_object)), (request, inputs['expected_request'] or bytes(32)),
               (state, bytes(state_bytes)), (callback, bytes(32)))
    guard = b'G' * 32
    for address, value in objects:
        cpu.mem_write(address - 32, guard)
        cpu.mem_write(address, value)
        cpu.mem_write(address + len(value), guard)
    cpu.mem_write(stack_lo - 32, guard)
    cpu.mem_write(stack_hi, guard)
    visited = set()
    counts = {'instructions': 0, 'cached_request_lookups': 0,
              'http_status_reads': 0, 'parsed_x_result_reads': 0,
              'host_override_header_reads': 0, 'singleton_lookups': 0,
              'completion_callbacks': 0}
    completion = None

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        nonlocal completion
        counts['instructions'] += 1
        visited.add(address)
        stubs = {0x800721F8: ('cached_request_lookups', request if inputs['expected_request'] is not None else 0),
                 0x8007A19C: ('http_status_reads', inputs['http_status']),
                 0x8007A21C: ('parsed_x_result_reads', inputs['x_result']),
                 0x8007A1E8: ('host_override_header_reads', 0),
                 0x80064EF4: ('singleton_lookups', state)}
        if address in stubs:
            name, value = stubs[address]
            counts[name] += 1
            ret(value)
            return
        if address == 0x8006EAE4:
            if cpu.reg_read(UC_PPC_REG_0 + 3) != callback:
                raise ValueError('Unexpected synthetic CMOC completion object')
            completion = cpu.reg_read(UC_PPC_REG_0 + 4)
            counts['completion_callbacks'] += 1
            ret()
            return
        allowed = ((0x80072CE0, 0x800730E8), (0x800731C4, 0x800731FC),
                   (0x80068690, 0x800686C0), (0x800695D0, 0x8006966C),
                   (0x80067D1C, 0x80067D74), (0x8006A57C, 0x8006A5BC))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError('Unexpected native CMOC response-gate control flow')

    def read(_cpu, _access, address, size, _value, _context):
        allowed = [(pointer, pointer + len(value)) for pointer, value in objects]
        allowed.append((stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Native CMOC response-gate read exceeds fixture bounds')

    def write(_cpu, _access, address, size, _value, _context):
        if not ((stack_lo <= address < address + size <= stack_hi)
                or (state + 0x11 <= address < address + size <= state + 0x12)):
            raise ValueError('Unexpected native CMOC response-gate state write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for register, value in {1: stack, 3: callback, 4: response}.items():
        cpu.reg_write(UC_PPC_REG_0 + register, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80072CE0, stop, count=20000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native CMOC response-gate instruction limit reached')
    if (completion != expected.completion_code or counts['completion_callbacks'] != 1
            or (0x80072F34 in visited) != expected.header_gate_passed
            or (0x80072E5C in visited) != expected.body_header_checked
            or bool(counts['http_status_reads']) != expected.http_status_checked
            or bool(counts['parsed_x_result_reads']) != expected.x_result_checked):
        raise ValueError('Native CMOC response-gate outcome differs from independent component')
    state_bytes[0x11] = expected.next_byte_3
    for pointer, value in objects:
        wanted = bytes(state_bytes) if pointer == state else value
        if (bytes(cpu.mem_read(pointer, len(value))) != wanted
                or bytes(cpu.mem_read(pointer - 32, 32)) != guard
                or bytes(cpu.mem_read(pointer + len(value), 32)) != guard):
            raise ValueError('Native CMOC response-gate input/state guard changed')
    if (bytes(cpu.mem_read(stack_lo - 32, 32)) != guard
            or bytes(cpu.mem_read(stack_hi, 32)) != guard):
        raise ValueError('Native CMOC response-gate stack guard changed')
    return {**expected.metadata(), 'counts': counts,
            'full_completion_handler_executed': True,
            'header_branches_or_state_updates_stubbed': False,
            'transport_cache_singleton_and_callback_stubbed': True,
            'host_override_supplied': False,
            'input_state_and_stack_guards_verified': True}
