"""Execute original HATJ setup/helpers with explicit scalar SDK/tick boundaries.

The device-derived configuration generator is forbidden. Only initialized
synthetic configuration is supplied; opaque SDK resources are never read.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_request import (STORAGE_BYTES, INNER, CREATE, DESTROY, HEADER,
                                    CONFIGURE, SELECT, OPTION, SEND, LAST_ERROR, TICK,
                                    prepare_request, submit_request)
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA

OBJECT_WORD = 0x81000000


def verify_request_native(source, state, *, inputs, sdk_results, tick_words, entry):
    if (type(source) is not bytes or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    if state.object_word != OBJECT_WORD:
        raise ValueError('Native fixture requires its explicit request object word')
    if entry == 'prepare':
        expected = prepare_request(state, inputs, sdk_results=sdk_results, tick_words=tick_words)
    elif entry == 'submit' and inputs is None:
        expected = submit_request(state, sdk_results=sdk_results, tick_words=tick_words)
    else:
        raise ValueError('Expected explicit setup or direct submission entry')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    layout = sections(source)
    for _, offset, address, size in layout:
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Original Nintendo image exceeds bounded RAM')
        cpu.mem_write(address, source[offset:offset + size])
    r2, r13 = 0x80808460, 0x808041E0
    phase_slot, retry_slot = r13 - 0x4E30, r13 - 0x7BA8
    config, reference, referer = 0x80406120, 0x81300000, 0x81302000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'NINTENDO-REQUEST-GUARD!' * 2
    objects = [(OBJECT_WORD, state.storage)]
    # ABI globals adjoin original literals/tables. Do not overwrite their
    # neighbours with fixture guards; compare the exact slots separately.
    slots = ((phase_slot, struct.pack('>I', state.shared_word)),
             (retry_slot, struct.pack('>I', state.retry_word & 0xFFFFFFFF)))
    for pointer, value in slots:
        cpu.mem_write(pointer, value)
    if inputs is not None:
        objects.extend(((config, b'\x01' + inputs.user_agent + b'\0'),
                        (reference, inputs.reference + b'\0')))
        if inputs.referer is not None:
            objects.append((referer, inputs.referer + b'\0'))
    for pointer, value in objects:
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'setup': 0, 'create': 0, 'initialized_config_getter': 0,
              'header_user_agent': 0, 'header_referer': 0, 'header_range': 0,
              'submit': 0, 'cleanup': 0, 'reset_inner': 0,
              'sdk_boundaries': 0, 'tick_boundaries': 0}
    entries = {0x80026C80: 'setup', 0x80027A40: 'create', 0x80025860: 'initialized_config_getter',
               0x80027880: 'header_user_agent', 0x80027900: 'header_referer',
               0x800277F0: 'header_range', 0x80027B60: 'submit',
               0x800281A0: 'cleanup', 0x80028170: 'reset_inner'}
    code_ranges = ((0x80004364, 0x800046E0), (0x80025110, 0x80025130), (0x800251E0, 0x80025260),
                   (0x80025860, 0x800258BC), (0x80026C80, 0x80026DD0),
                   (0x800271E0, 0x80027238), (0x80027570, 0x800275FC),
                   (0x800277F0, 0x80027974), (0x80027A40, 0x80027C10),
                   (0x80028170, 0x80028208), (0x80028270, 0x800283B8),
                   (0x8002B6A0, 0x8002B780), (0x8033F000, 0x80350000))
    call_index = 0
    remaining_sdk = list(sdk_results)
    remaining_ticks = list(tick_words)
    read_ranges = [(pointer, pointer + len(value)) for pointer, value in (*objects, *slots)]
    read_ranges += [(stack_lo, stack_hi), (0x80389800, 0x80389C00),
                    (0x8038F000, 0x80390000), (0x803FD000, 0x803FF000),
                    (0x807FC600, 0x807FC700), (0x808006A0, 0x808006D0)]

    def check_read(address, size):
        if not any(lo <= address < address + size <= hi for lo, hi in read_ranges):
            raise ValueError(f'Original request read exceeds reviewed bounds at {address:#010x}/{size}')

    def word(address):
        if address not in (phase_slot, retry_slot, r13 - 0x7BB0, r13 - 0x7BAC,
                            r2 - 0x7DB8, r2 - 0x7DB4):
            raise ValueError('Host word inspection exceeds explicit ABI/table slots')
        check_read(address, 4)
        return struct.unpack('>I', bytes(cpu.mem_read(address, 4)))[0]

    def cstring(address, maximum):
        output = bytearray()
        for index in range(maximum + 1):
            check_read(address + index, 1)
            value = bytes(cpu.mem_read(address + index, 1))[0]
            if value == 0:
                return bytes(output)
            output.append(value)
        raise ValueError('Original request string exceeds its reviewed bound')

    def register(index):
        return cpu.reg_read(UC_PPC_REG_0 + index)

    def instruction(_cpu, address, size, _context):
        nonlocal call_index
        counts['instructions'] += 1
        if address == 0x800256A0:
            raise ValueError('Device-derived configuration generation is forbidden')
        if address in entries:
            counts[entries[address]] += 1
        if address in (CREATE, DESTROY, HEADER, CONFIGURE, SELECT, OPTION, SEND, LAST_ERROR, TICK):
            if call_index >= len(expected.calls):
                raise ValueError('Unexpected original SDK/tick boundary')
            call = expected.calls[call_index]
            if call.address != address:
                raise ValueError('Original SDK/tick boundary order differs from projection')
            call_index += 1
            if address == TICK:
                if not remaining_ticks or tuple(call.returned_words) != remaining_ticks.pop(0):
                    raise ValueError('Original tick outcome sequence differs')
                counts['tick_boundaries'] += 1
                cpu.reg_write(UC_PPC_REG_0 + 3, call.returned_words[0])
                cpu.reg_write(UC_PPC_REG_0 + 4, call.returned_words[1])
            else:
                if not remaining_sdk or remaining_sdk.pop(0) != (address, call.returned_words[0]):
                    raise ValueError('Original SDK outcome sequence differs')
                counts['sdk_boundaries'] += 1
                if address == CREATE:
                    actual = (cstring(register(3), 511), register(4), register(5), register(6), register(7), register(8))
                elif address == HEADER:
                    actual = (register(3), cstring(register(4), 64), cstring(register(5), 63))
                elif address == SELECT:
                    handle, selector = call.arguments
                    # Only the original pointer/length table words are read.
                    # The resources they reference are not dereferenced.
                    if (register(3), register(4), register(5)) != (
                            handle, word(r13 - 0x7BB0 + 4 * selector), word(r2 - 0x7DB8 + 4 * selector)):
                        raise ValueError('Original opaque SDK selector arguments differ')
                    actual = (handle, selector)
                elif address == OPTION:
                    actual = (register(3), register(4))
                elif address == LAST_ERROR:
                    actual = ()
                else:
                    actual = (register(3),)
                if actual != call.arguments:
                    raise ValueError(f'Original SDK request arguments differ from projection at {address:#010x}')
                cpu.reg_write(UC_PPC_REG_0 + 3, call.returned_words[0])
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if not any(lo <= address < address + size <= hi for lo, hi in code_ranges):
            raise ValueError(f'Unexpected original request control flow at {address:#010x}')

    def read(_cpu, _access, address, size, _value, _context):
        check_read(address, size)

    def write(_cpu, _access, address, size, _value, _context):
        if not any(lo <= address < address + size <= hi for lo, hi in (
                (OBJECT_WORD, OBJECT_WORD + STORAGE_BYTES), (stack_lo, stack_hi), (phase_slot, phase_slot + 4))):
            raise ValueError(f'Unexpected original request write at {address:#010x}')

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.reg_write(UC_PPC_REG_MSR, 0x2000)
    registers = {1: stack, 2: r2, 13: r13, 3: OBJECT_WORD + (INNER if entry == 'submit' else 0)}
    if inputs is not None:
        registers.update({4: reference, 5: inputs.receive_word, 6: inputs.capacity_word,
                          7: inputs.callback_word, 8: inputs.callback_context_word,
                          9: referer if inputs.referer is not None else 0, 10: inputs.range_word})
    for index, value in registers.items():
        cpu.reg_write(UC_PPC_REG_0 + index, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80026C80 if entry == 'prepare' else 0x80027B60, stop, count=3000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Original request instruction bound reached')
    if (call_index != len(expected.calls) or remaining_sdk or remaining_ticks
            or register(3) != expected.result & 0xFFFFFFFF
            or bytes(cpu.mem_read(OBJECT_WORD, STORAGE_BYTES)) != expected.state.storage
            or word(phase_slot) != expected.state.shared_word
            or word(retry_slot) != state.retry_word & 0xFFFFFFFF):
        raise ValueError('Original request state/result/outcomes differ from independent projection')
    for pointer, value in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard):
            raise ValueError('Original request fixture guard changed')
        if pointer not in (OBJECT_WORD, phase_slot) and bytes(cpu.mem_read(pointer, len(value))) != value:
            raise ValueError('Original request immutable input changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('Original request stack guard changed')
    return {**expected.metadata(), 'counts': counts,
            'original_setup_create_cleanup_headers_submission_and_error_conversion_stubbed': False,
            'sdk_leaves_and_tick_stubbed': True, 'device_configuration_generator_executed': False,
            'referenced_sdk_resources_read': False,
            'host_side_inspection_reads_share_emulated_read_bounds': True,
            'exact_storage_arguments_outcome_sequence_and_guards_checked': True}
