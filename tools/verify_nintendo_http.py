"""Bounded original HATJ HTTP callback and manager poll/state execution.

Only timer, underlying manager request/status and diagnostic boundaries are mocked.
Chunk copying, state branches, restart wrapper and result normalization run.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_http import apply_http_callback, poll_http_state, _state
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA


def verify_http_native(source, state, *, callback=None, poll=None):
    if (type(source) is not bytes or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    state = _state(state)
    if (callback is None) == (poll is None):
        raise ValueError('Expected exactly one explicit HTTP callback or poll fixture')
    expected = apply_http_callback(state, **callback) if callback is not None else poll_http_state(state, **poll)
    after = expected.state
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Original Nintendo image exceeds the bounded RAM mapping')
        cpu.mem_write(address, source[offset:offset + size])
    manager, buffer, frame, chunk = 0x81000000, 0x81100000, 0x81310000, 0x81320000
    reference, request_manager_object, sda = 0x81530000, 0x81540000, 0x808041E0
    retry_slot, request_manager_slot = sda - 0x7BA8, sda - 0x4E48
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    loader = manager + 0x10
    guard = b'NINTENDO-HTTP-GUARD!' * 2
    raw_manager = bytearray(0x2A80)

    def put(offset, value):
        struct.pack_into('>I', raw_manager, offset, value & 0xFFFFFFFF)

    put(0x10, 0x8038F108)
    for offset, value in ((0x14, state.word_04), (0x18, state.word_08), (0x1C, state.word_0c),
                          (0x2C, state.error_word_1c), (0x30, state.error_word_20),
                          (0x2844, state.copied_bytes), (0x2840, buffer),
                          (0x2848, len(state.buffer)), (0x2834, reference),
                          (0x2838, 0x77), (0x283C, 0x88),
                          (0x2A70, state.manager_error_word_2a70),
                          (0x2A74, state.manager_error_word_2a74)):
        put(offset, value)
    frame_bytes = struct.pack('>6I', chunk, len(callback['chunk']),
                              callback['word_08'], callback['word_0c'],
                              callback['word_10'], callback['word_14']) if callback is not None else bytes(24)
    chunk_bytes = callback['chunk'] if callback is not None else b''
    objects = [(manager, bytes(raw_manager)), (buffer, state.buffer), (frame, frame_bytes),
               (reference, b'https://synthetic.invalid/list\0'),
               (request_manager_object, struct.pack('>I', poll['request_26c80_error_word'] if poll is not None else 0)),
               (retry_slot, struct.pack('>I', state.retry_word & 0xFFFFFFFF)),
               (request_manager_slot, struct.pack('>I', request_manager_object if poll is not None and poll['request_manager_available'] else 0))]
    if chunk_bytes:
        objects.append((chunk, chunk_bytes))
    for pointer, value in objects:
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'timer_reset': 0, 'timer_start': 0, 'timer_update': 0,
              'timer_predicate': 0, 'manager_27140': 0, 'manager_271d0': 0,
              'request_26c80': 0, 'diagnostic_boundaries': 0,
              'native_restart_entries': 0, 'native_normalizer_entries': 0}

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        counts['instructions'] += 1
        if address in (0x8002BA80, 0x8002BAA0, 0x8002BAF0):
            key = {0x8002BA80: 'timer_reset', 0x8002BAA0: 'timer_start', 0x8002BAF0: 'timer_update'}[address]
            counts[key] += 1
            ret()
            return
        if address == 0x8002BB60:
            counts['timer_predicate'] += 1
            ret(int(poll['timer_expired']))
            return
        if address in (0x80027140, 0x800271D0):
            key = 'manager_27140' if address == 0x80027140 else 'manager_271d0'
            counts[key] += 1
            if cpu.reg_read(UC_PPC_REG_0 + 3) != (request_manager_object if poll['request_manager_available'] else 0):
                raise ValueError('Unexpected synthetic underlying manager object')
            ret(poll['manager_27140_result'] if address == 0x80027140 else 0)
            return
        if address == 0x80026C80:
            counts['request_26c80'] += 1
            actual = tuple(cpu.reg_read(UC_PPC_REG_0 + index) for index in range(3, 11))
            if actual != (request_manager_object, reference, loader + 0x24, 0x2800, 0x800287C0, loader, 0x77, 0x88):
                raise ValueError('Original restart changed the explicit request boundary arguments')
            ret(poll['request_26c80_result'])
            return
        if address == 0x80009290:
            counts['diagnostic_boundaries'] += 1
            ret()
            return
        if address == 0x80028490:
            counts['native_restart_entries'] += 1
        if address == 0x8002BE20:
            counts['native_normalizer_entries'] += 1
        ranges = ((0x800287E0, 0x80028914), (0x80028490, 0x80028580),
                  (0x800285E0, 0x8002872C), (0x8002BD80, 0x8002BDC8),
                  (0x8002BE20, 0x8002BEEC), (0x80028920, 0x80028928),
                  (0x80026A70, 0x80026A80),
                  (0x80004364, 0x800046E0))
        if not any(lo <= address < hi for lo, hi in ranges):
            raise ValueError(f'Unexpected native Nintendo HTTP control flow at {address:#010x}')

    def read(_cpu, _access, address, size, _value, _context):
        ranges = [(pointer, pointer + len(value)) for pointer, value in objects]
        ranges += [(stack_lo, stack_hi), (0x8038F108, 0x8038F130)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError('Original Nintendo HTTP read exceeds synthetic fixture bounds')

    def write(_cpu, _access, address, size, _value, _context):
        ranges = [(stack_lo, stack_hi), (buffer, buffer + len(state.buffer)),
                  (manager + 0x14, manager + 0x20), (manager + 0x2C, manager + 0x34),
                  (manager + 0x20, manager + 0x28),
                  (manager + 0x2834, manager + 0x284C),
                  (manager + 0x2A70, manager + 0x2A78), (retry_slot, retry_slot + 4)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError(f'Unexpected native Nintendo HTTP write at {address:#010x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.reg_write(UC_PPC_REG_MSR, 0x2000)
    for register, value in {1: stack, 13: sda, 3: loader if callback is not None else manager, 4: frame}.items():
        cpu.reg_write(UC_PPC_REG_0 + register, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x800287E0 if callback is not None else 0x8002BD80, stop, count=2000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Original Nintendo HTTP instruction bound reached')
    for offset, value in ((0x14, after.word_04), (0x18, after.word_08), (0x1C, after.word_0c),
                          (0x2C, after.error_word_1c), (0x30, after.error_word_20),
                          (0x2844, after.copied_bytes),
                          (0x2A70, after.manager_error_word_2a70),
                          (0x2A74, after.manager_error_word_2a74)):
        put(offset, value)
    if poll is not None and expected.request_26c80_called:
        put(0x20, loader + 0x24)
        put(0x24, 0x2800)
    if bytes(cpu.mem_read(manager, len(raw_manager))) != bytes(raw_manager):
        raise ValueError('Original Nintendo HTTP state differs from independent projection')
    if bytes(cpu.mem_read(buffer, len(state.buffer))) != after.buffer:
        raise ValueError('Original callback copy differs from supplied retained bytes')
    if bytes(cpu.mem_read(retry_slot, 4)) != struct.pack('>I', after.retry_word & 0xFFFFFFFF):
        raise ValueError('Original Nintendo HTTP retry state differs from independent projection')
    if poll is not None:
        returned = cpu.reg_read(UC_PPC_REG_0 + 3)
        if returned != expected.manager_result & 0xFFFFFFFF:
            raise ValueError('Original manager result differs from independent normalization')
        for key, wanted in (('manager_27140', expected.manager_27140_called),
                            ('manager_271d0', expected.manager_271d0_called),
                            ('native_restart_entries', expected.restart_called),
                            ('request_26c80', expected.request_26c80_called)):
            if counts[key] != int(wanted):
                raise ValueError('Original Nintendo HTTP boundary counts differ')
        if counts['native_normalizer_entries'] != 1:
            raise ValueError('Original manager result normalizer did not execute')
    for pointer, value in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard):
            raise ValueError('Original Nintendo HTTP fixture guard changed')
        if pointer not in (manager, buffer, retry_slot) and bytes(cpu.mem_read(pointer, len(value))) != value:
            raise ValueError('Original Nintendo HTTP immutable input changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('Original Nintendo HTTP stack guard changed')
    return {**expected.metadata(), 'counts': counts,
            'original_callback_copy_and_state_branches_stubbed': False,
            'original_poll_restart_and_normalizer_stubbed': False,
            'timer_underlying_manager_and_diagnostic_boundaries_stubbed': True,
            'immutable_input_output_state_and_stack_guards_verified': True,
            'real_network_request_or_original_ui_verified': False}
