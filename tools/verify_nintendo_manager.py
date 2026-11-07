"""Bounded original manager thunk/relay through the actual HTTP callback copy.

Only the callback timer reset/start boundaries are intercepted. No networking,
SDK callback state production, provider trust or full timer behavior is claimed.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_manager import _manager, apply_manager_callback
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA

LOADER_CONTEXT_WORD = 0x81010010


def verify_manager_native(source, state, manager, chunk):
    if (type(source) is not bytes or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    manager = _manager(manager)
    if manager.callback_context_word not in (0, LOADER_CONTEXT_WORD):
        raise ValueError('Native fixture requires its explicit loader context or zero')
    expected = apply_manager_callback(state, manager, chunk, loader_context_word=LOADER_CONTEXT_WORD)
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Original Nintendo image exceeds bounded RAM')
        cpu.mem_write(address, source[offset:offset + size])
    request, outer, buffer, input_chunk = 0x81000000, LOADER_CONTEXT_WORD - 0x10, 0x81100000, 0x81320000
    sda = 0x808041E0
    retry_slot, phase_slot = sda - 0x7BA8, sda - 0x4E30
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    request_image = bytearray(0x2D3C)
    for offset, word in ((0x29AC, 0x800287C0 if manager.callback_present else 0),
                         (0x29B0, manager.callback_context_word), (0x2C20, manager.word_2c20),
                         (0x2D28, manager.error_word_2d28), (0x2D2C, manager.detail_word_2d2c),
                         (0x2D30, manager.response_word_2d30), (0x2D38, manager.flag_word_2d38)):
        struct.pack_into('>I', request_image, offset, word)
    outer_image = bytearray(0x2A80)

    def put(offset, value):
        struct.pack_into('>I', outer_image, offset, value & 0xFFFFFFFF)

    put(0x10, 0x8038F108)
    for offset, value in ((0x14, state.word_04), (0x18, state.word_08), (0x1C, state.word_0c),
                          (0x2C, state.error_word_1c), (0x30, state.error_word_20),
                          (0x2844, state.copied_bytes), (0x2840, buffer), (0x2848, len(state.buffer)),
                          (0x2A70, state.manager_error_word_2a70), (0x2A74, state.manager_error_word_2a74)):
        put(offset, value)
    guard = b'NINTENDO-MANAGER-GUARD!' * 2
    objects = [(request, bytes(request_image)), (outer, bytes(outer_image)), (buffer, state.buffer),
               (phase_slot, struct.pack('>I', manager.shared_word)),
               (retry_slot, struct.pack('>I', state.retry_word & 0xFFFFFFFF))]
    if chunk:
        objects.append((input_chunk, chunk))
    for pointer, value in objects:
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'manager_thunk': 0, 'manager_relay': 0,
              'http_callback_wrapper': 0, 'http_callback_body': 0,
              'native_copy': 0, 'timer_reset': 0, 'timer_start': 0}
    entries = {0x80026AE0: 'manager_thunk', 0x80026B10: 'manager_relay',
               0x800287C0: 'http_callback_wrapper', 0x800287E0: 'http_callback_body',
               0x80004364: 'native_copy'}
    code_ranges = ((0x80026AE0, 0x80026B04), (0x80026B10, 0x80026C78),
                   (0x80027D70, 0x80027E24), (0x8002B6A0, 0x8002B86C),
                   (0x8002BA20, 0x8002BA30), (0x800287C0, 0x80028914),
                   (0x80004364, 0x800046E0))

    def code(_cpu, address, size, _context):
        counts['instructions'] += 1
        if address in entries:
            counts[entries[address]] += 1
        if address in (0x8002BA80, 0x8002BAA0):
            if cpu.reg_read(UC_PPC_REG_0 + 3) != LOADER_CONTEXT_WORD + 0x2840:
                raise ValueError('Original callback timer received another object')
            counts['timer_reset' if address == 0x8002BA80 else 'timer_start'] += 1
            cpu.reg_write(UC_PPC_REG_0 + 3, 0)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if not any(lo <= address < address + size <= hi for lo, hi in code_ranges):
            raise ValueError(f'Unexpected native manager control flow at {address:#010x}')
        if address == 0x800287C0:
            pointer = cpu.reg_read(UC_PPC_REG_0 + 3)
            if not stack_lo <= pointer < pointer + 24 <= stack_hi or expected.frame is None:
                raise ValueError('Original manager callback frame is outside guarded stack')
            frame = expected.frame
            actual = struct.unpack('>6I', bytes(cpu.mem_read(pointer, 24)))
            if (actual != (input_chunk, len(chunk), frame.word_08, frame.word_0c, frame.word_10, frame.word_14)
                    or cpu.reg_read(UC_PPC_REG_0 + 4) != frame.callback_context_word):
                raise ValueError('Original manager frame or runtime context differs from projection')

    def read(_cpu, _access, address, size, _value, _context):
        ranges = [(pointer, pointer + len(value)) for pointer, value in objects]
        ranges += [(stack_lo, stack_hi), (0x8038F960, 0x8038F9E8)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError(f'Original manager read exceeds guarded fixture at {address:#010x}')

    def write(_cpu, _access, address, size, _value, _context):
        ranges = [(stack_lo, stack_hi), (buffer, buffer + len(state.buffer)),
                  (outer + 0x14, outer + 0x20), (outer + 0x2C, outer + 0x34),
                  (outer + 0x2844, outer + 0x2848), (retry_slot, retry_slot + 4)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError(f'Unexpected native manager write at {address:#010x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.reg_write(UC_PPC_REG_MSR, 0x2000)
    for register, value in {1: stack, 13: sda, 3: input_chunk, 4: len(chunk),
                            5: request if manager.manager_present else 0}.items():
        cpu.reg_write(UC_PPC_REG_0 + register, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80026AE0, stop, count=2000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Original manager instruction bound reached')
    after = expected.state
    for offset, value in ((0x14, after.word_04), (0x18, after.word_08), (0x1C, after.word_0c),
                          (0x2C, after.error_word_1c), (0x30, after.error_word_20),
                          (0x2844, after.copied_bytes)):
        put(offset, value)
    if (bytes(cpu.mem_read(outer, len(outer_image))) != bytes(outer_image)
            or bytes(cpu.mem_read(buffer, len(state.buffer))) != after.buffer
            or bytes(cpu.mem_read(retry_slot, 4)) != struct.pack('>I', after.retry_word & 0xFFFFFFFF)):
        raise ValueError('Original composed callback state or retained bytes differ from projection')
    consumed = expected.callback is not None
    wanted_counts = {'manager_thunk': 1, 'manager_relay': int(manager.manager_present),
                     'http_callback_wrapper': int(expected.frame is not None),
                     'http_callback_body': int(consumed), 'timer_reset': int(consumed),
                     'timer_start': int(consumed),
                     'native_copy': int(consumed and expected.callback.retained_bytes != 0)}
    if any(counts[name] != wanted for name, wanted in wanted_counts.items()):
        raise ValueError('Original manager or callback branch counts differ from projection')
    for pointer, value in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard):
            raise ValueError('Original manager fixture guard changed')
        if pointer not in (outer, buffer, retry_slot) and bytes(cpu.mem_read(pointer, len(value))) != value:
            raise ValueError('Original manager immutable input changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('Original manager stack guard changed')
    return {**expected.metadata(), 'counts': counts,
            'original_thunk_relay_predicates_error_maps_and_callback_stubbed': False,
            'original_byte_copy_stubbed': False,
            'timer_reset_start_boundaries_stubbed': True,
            'immutable_input_output_state_and_stack_guards_verified': True,
            'sdk_callback_state_production_or_real_network_verified': False}
