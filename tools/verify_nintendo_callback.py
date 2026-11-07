"""Original event-four producer through manager relay and original HTTP consumer.

Only SDK getters, tick and callback timer boundaries are intercepted. Original
state stores, signed division, header clearing, relay and consumer execute.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_callback import CONTEXT, ERROR, DETAIL, PHASE, RESPONSE, apply_sdk_event4
from jwc24.nintendo_request import INNER, STORAGE_BYTES, TICK
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA

OBJECT_WORD, LOADER_CONTEXT_WORD = 0x81000000, 0x81010010


def verify_callback_native(source, request, loader, inputs, *, sdk_results, tick_words):
    if (type(source) is not bytes or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    if request.object_word != OBJECT_WORD:
        raise ValueError('Native fixture requires its explicit manager object word')
    expected = apply_sdk_event4(request, loader, inputs, loader_context_word=LOADER_CONTEXT_WORD,
                                sdk_results=sdk_results, tick_words=tick_words)
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Original Nintendo image exceeds bounded RAM')
        cpu.mem_write(address, source[offset:offset + size])
    outer, buffer, descriptor = LOADER_CONTEXT_WORD - 0x10, 0x81100000, 0x81330000
    r13 = 0x808041E0
    phase_slot, retry_slot, frequency_slot = r13 - 0x4E30, r13 - 0x7BA8, 0x800000F8
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'NINTENDO-EVENT4-GUARD!' * 2
    outer_image = bytearray(0x2A80)

    def put(offset, value):
        struct.pack_into('>I', outer_image, offset, value & 0xFFFFFFFF)

    put(0x10, 0x8038F108)
    for offset, value in ((0x14, loader.word_04), (0x18, loader.word_08), (0x1C, loader.word_0c),
                          (0x2C, loader.error_word_1c), (0x30, loader.error_word_20),
                          (0x2844, loader.copied_bytes), (0x2840, buffer), (0x2848, len(loader.buffer)),
                          (0x2A70, loader.manager_error_word_2a70), (0x2A74, loader.manager_error_word_2a74)):
        put(offset, value)
    objects = [(OBJECT_WORD, request.storage), (outer, bytes(outer_image)), (buffer, loader.buffer)]
    if inputs.descriptor:
        objects.append((descriptor, inputs.descriptor))
    for pointer, value in objects:
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    slots = ((phase_slot, struct.pack('>I', request.shared_word)),
             (retry_slot, struct.pack('>I', request.retry_word & 0xFFFFFFFF)),
             (frequency_slot, struct.pack('>I', inputs.frequency_word)))
    for pointer, value in slots:
        cpu.mem_write(pointer, value)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'sdk_wrapper': 0, 'inner_dispatch': 0, 'event_four_branch': 0,
              'native_signed_division': 0, 'header_clear': 0, 'manager_thunk': 0,
              'manager_relay': 0, 'http_callback_wrapper': 0, 'http_callback_body': 0,
              'sdk_getters': 0, 'tick': 0, 'timer_reset': 0, 'timer_start': 0}
    entries = {0x80027E40: 'sdk_wrapper', 0x80027E90: 'inner_dispatch', 0x80028068: 'event_four_branch',
               0x803405BC: 'native_signed_division', 0x800282B0: 'header_clear',
               0x80026AE0: 'manager_thunk', 0x80026B10: 'manager_relay',
               0x800287C0: 'http_callback_wrapper', 0x800287E0: 'http_callback_body'}
    code_ranges = ((0x80027E40, 0x80028158), (0x800282B0, 0x800282FC),
                   (0x80026AE0, 0x80026B04), (0x80026B10, 0x80026C78),
                   (0x80027D70, 0x80027E24), (0x8002B6A0, 0x8002B86C),
                   (0x8002BA20, 0x8002BA30), (0x800287C0, 0x80028914),
                   (0x80340400, 0x80340B00), (0x8034757C, 0x8034763C))
    read_ranges = [(pointer, pointer + len(value)) for pointer, value in (*objects, *slots)]
    read_ranges += [(stack_lo, stack_hi), (0x8038F960, 0x8038F9E8), (0x807FC640, 0x807FC660)]
    call_index = 0
    remaining_sdk, remaining_ticks = list(sdk_results), list(tick_words)

    def check_read(address, size):
        if not any(lo <= address < address + size <= hi for lo, hi in read_ranges):
            raise ValueError(f'Original callback read exceeds guarded bounds at {address:#010x}/{size}')

    def host_read(address, size):
        check_read(address, size)
        return bytes(cpu.mem_read(address, size))

    def register(index):
        return cpu.reg_read(UC_PPC_REG_0 + index)

    def instruction(_cpu, address, size, _context):
        nonlocal call_index
        counts['instructions'] += 1
        if address in entries:
            counts[entries[address]] += 1
        if address in (CONTEXT, ERROR, DETAIL, PHASE, RESPONSE, TICK):
            if call_index >= len(expected.calls) or expected.calls[call_index].address != address:
                raise ValueError('Original callback SDK/tick boundary order differs')
            call = expected.calls[call_index]
            call_index += 1
            if address == TICK:
                if not remaining_ticks or remaining_ticks.pop(0) != call.returned_words:
                    raise ValueError('Original callback tick sequence differs')
                counts['tick'] += 1
                cpu.reg_write(UC_PPC_REG_0 + 3, call.returned_words[0])
                cpu.reg_write(UC_PPC_REG_0 + 4, call.returned_words[1])
            else:
                if (not remaining_sdk or remaining_sdk.pop(0) != (address, call.returned_words[0])
                        or (register(3),) != call.arguments):
                    raise ValueError('Original callback SDK getter arguments/outcomes differ')
                counts['sdk_getters'] += 1
                cpu.reg_write(UC_PPC_REG_0 + 3, call.returned_words[0])
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if address in (0x8002BA80, 0x8002BAA0):
            if register(3) != LOADER_CONTEXT_WORD + 0x2840:
                raise ValueError('Original HTTP timer received another loader')
            counts['timer_reset' if address == 0x8002BA80 else 'timer_start'] += 1
            cpu.reg_write(UC_PPC_REG_0 + 3, 0)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if not any(lo <= address < address + size <= hi for lo, hi in code_ranges):
            raise ValueError(f'Unexpected original callback control flow at {address:#010x}')
        if address == 0x800287C0:
            pointer = register(3)
            if expected.delivery is None or expected.delivery.frame is None or not stack_lo <= pointer < pointer + 24 <= stack_hi:
                raise ValueError('Original callback frame is outside the supplied chain/stack')
            frame = expected.delivery.frame
            if (struct.unpack('>6I', host_read(pointer, 24)) != (0, 0, frame.word_08,
                    frame.word_0c, frame.word_10, frame.word_14) or register(4) != frame.callback_context_word):
                raise ValueError('Original final callback frame/context differs')

    def read(_cpu, _access, address, size, _value, _context):
        check_read(address, size)

    def write(_cpu, _access, address, size, _value, _context):
        ranges = ((OBJECT_WORD, OBJECT_WORD + STORAGE_BYTES), (stack_lo, stack_hi),
                  (outer + 0x14, outer + 0x20), (outer + 0x2C, outer + 0x34),
                  (retry_slot, retry_slot + 4), (phase_slot, phase_slot + 4))
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError(f'Unexpected original callback write at {address:#010x}')

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for index, value in {1: stack, 13: r13, 3: inputs.sdk_handle_word,
                          4: inputs.event_word, 5: descriptor}.items():
        cpu.reg_write(UC_PPC_REG_0 + index, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80027E40, stop, count=2000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Original event-four instruction bound reached')
    after = expected.loader
    for offset, value in ((0x14, after.word_04), (0x18, after.word_08), (0x1C, after.word_0c),
                          (0x2C, after.error_word_1c), (0x30, after.error_word_20)):
        put(offset, value)
    if (register(3) != 0 or call_index != len(expected.calls) or remaining_sdk or remaining_ticks
            or host_read(OBJECT_WORD, STORAGE_BYTES) != expected.request.storage
            or host_read(outer, len(outer_image)) != bytes(outer_image)
            or host_read(buffer, len(loader.buffer)) != after.buffer
            or host_read(phase_slot, 4) != struct.pack('>I', expected.request.shared_word)
            or host_read(retry_slot, 4) != struct.pack('>I', after.retry_word & 0xFFFFFFFF)
            or host_read(frequency_slot, 4) != struct.pack('>I', inputs.frequency_word)):
        raise ValueError('Original event-four state/result differs from independent projection')
    consumed = expected.delivery is not None and expected.delivery.callback is not None
    wanted = {'sdk_wrapper': 1, 'inner_dispatch': 1, 'event_four_branch': 1, 'header_clear': 1,
              'native_signed_division': int(request.shared_word == 2),
              'manager_thunk': int(expected.inner_callback_invoked),
              'manager_relay': int(expected.manager_relay_invoked),
              'http_callback_wrapper': int(expected.delivery is not None and expected.delivery.frame is not None),
              'http_callback_body': int(consumed), 'timer_reset': int(consumed), 'timer_start': int(consumed)}
    if any(counts[key] != value for key, value in wanted.items()):
        raise ValueError('Original event-four branch counts differ from projection')
    for pointer, value in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard):
            raise ValueError('Original callback fixture guard changed')
        if pointer not in (OBJECT_WORD, outer) and host_read(pointer, len(value)) != value:
            raise ValueError('Original callback immutable input changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('Original callback stack guard changed')
    return {**expected.metadata(), 'counts': counts,
            'original_wrapper_event_four_division_header_clear_relay_and_consumer_stubbed': False,
            'sdk_getters_ticks_and_callback_timer_boundaries_stubbed': True,
            'host_inspection_reads_share_emulated_bounds': True,
            'exact_storage_descriptor_context_arguments_state_and_guards_checked': True,
            'other_events_cancellation_or_worker_lifetime_verified': False}
