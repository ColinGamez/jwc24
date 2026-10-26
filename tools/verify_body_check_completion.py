"""Bounded original HFNJ read consumer and opaque header-pair comparisons.

Only the underlying filesystem read and diagnostic conversion boundaries are
intercepted. Original copy/clear/CRC and selected state predicates execute.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.body_check import MAX_DATASET_BYTES
from jwc24.body_check_completion import evaluate_dataset_read_completion, evaluate_header_pair_gate
from tools.verify_body_check_header_crc import SOURCE_BYTES, SOURCE_SHA256

READ_BEGIN, READ_END = 0x802BBB90, 0x802BBD3C
PAIR_BEGIN, PAIR_END = 0x802BBB10, 0x802BBB90


def _source(source):
    if (type(source) is not bytes or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('Body Check Japanese v256 executable fingerprint mismatch')


def _cpu(source):
    _source(source)
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Body Check source section exceeds guarded RAM')
        cpu.mem_write(address, source[offset:offset + size])
    return cpu


def synthetic_read_cases():
    """Deterministic test framing and opaque bytes, never health/service data."""
    data = bytearray((position * 17 + 23) % 256 for position in range(MAX_DATASET_BYTES))
    data[4:16] = bytes(range(12))
    struct.pack_into('>I', data, 0, zlib.crc32(data[4:16]))
    good = bytes(data)

    def case(status, **changes):
        result = dict(buffer=good, read_result=status, latched_flag=False, diagnostic_code=88,
                      converted_reader_diagnostic=-77, reported_length=16)
        result.update(changes)
        return result

    cases = [case(status) for status in (0, 1, 2, 3, 4, 5, 0xB006, 0xFFFFFFFF, 0x80000000)]
    bad = bytearray(good)
    bad[9] ^= 1
    cases.append(case(0, buffer=bytes(bad)))
    cases.extend(case(status, latched_flag=True, converted_reader_diagnostic=None)
                 for status in (0, 2, 5, 0xB006))
    for offset in (16, MAX_DATASET_BYTES - 1):
        changed = bytearray(good)
        changed[offset] ^= 1
        cases.append(case(0, buffer=bytes(changed)))
    cases.extend(case(0, reported_length=length) for length in (0, 1, 15, 16, MAX_DATASET_BYTES))
    cases.append(case(2, buffer=bytes(bad)))
    cases.extend(case(5, converted_reader_diagnostic=value)
                 for value in (-(1 << 31), 0, (1 << 31) - 1))
    return cases


def synthetic_header_pairs():
    return [(first, second) for first in (0, 1, 2, 255, 65535)
            for second in (0, 1, 65535)]


def verify_read_completion(source: bytes, cases):
    _source(source)
    fields = {'buffer', 'read_result', 'latched_flag', 'diagnostic_code',
              'converted_reader_diagnostic', 'reported_length'}
    if (type(cases) not in (list, tuple) or not 1 <= len(cases) <= 64
            or any(type(case) is not dict or set(case) != fields for case in cases)):
        raise ValueError('Expected a bounded explicit set of native read fixtures')
    expectations = []
    for case in cases:
        length = case['reported_length']
        if type(length) is not int or not 0 <= length <= MAX_DATASET_BYTES:
            raise ValueError('Expected bounded explicit reported-read length')
        expectations.append(evaluate_dataset_read_completion(
            **{key: value for key, value in case.items() if key != 'reported_length'}))
    cpu = _cpu(source)
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    manager, data_object, sda = 0x81000000, 0x81100000, 0x81508000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    buffer_address = data_object + 4
    filename, reader_context = 0x81310000, 0x81300000
    guard, object_tag = b'B' * 32, b'VTBL'
    current, expected = None, None
    read_calls = conversion_calls = 0
    native_calls = {'copy': 0, 'clear': 0, 'crc': 0, 'filename': 0, 'last_diagnostic': 0}
    reported_length_pointer = None
    all_instructions = 0
    dataset_reads = set()
    diagnostic_input = 0x12345678

    def ret(value):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        nonlocal read_calls, conversion_calls, all_instructions, reported_length_pointer
        all_instructions += 1
        for entry, name in ((0x80004000, 'copy'), (0x80004350, 'clear'),
                            (0x80146CD4, 'crc'), (0x8031BAE4, 'filename'),
                            (0x8031A310, 'last_diagnostic')):
            if address == entry:
                native_calls[name] += 1
        if address == 0x8031A3A0:
            arguments = [cpu.reg_read(UC_PPC_REG_0 + register) for register in range(3, 7)]
            if (arguments[:3] != [buffer_address, MAX_DATASET_BYTES, filename]
                    or not stack_lo <= arguments[3] <= stack_hi - 4):
                raise ValueError('Unexpected native Body Check read-boundary arguments')
            # Buffer is explicitly the post-reader memory snapshot. No real
            # file is opened and no fabricated record bytes are copied here.
            cpu.mem_write(arguments[3], struct.pack('>I', current['reported_length']))
            reported_length_pointer = arguments[3]
            read_calls += 1
            ret(current['read_result'])
            return
        if address == 0x801D7DFC:
            if (cpu.reg_read(UC_PPC_REG_0 + 3) != diagnostic_input
                    or current['converted_reader_diagnostic'] is None):
                raise ValueError('Unexpected native Body Check diagnostic boundary')
            conversion_calls += 1
            ret(current['converted_reader_diagnostic'])
            return
        allowed = ((READ_BEGIN, READ_END), (0x8031BAD0, 0x8031BAF0),
                   (0x8031A310, 0x8031A318), (0x80004000, 0x80004380),
                   (0x80146CD4, 0x80146E10))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError('Unexpected native Body Check read-consumer control flow')

    def read(_cpu, _access, address, size, _value, _context):
        if (reported_length_pointer is not None
                and address < reported_length_pointer + 4 and address + size > reported_length_pointer):
            raise ValueError('Selected Body Check consumer unexpectedly reads reported length')
        if buffer_address <= address < address + size <= buffer_address + MAX_DATASET_BYTES:
            dataset_reads.update(range(address - buffer_address, address + size - buffer_address))
            if address + size > buffer_address + 16:
                raise ValueError('Selected Body Check read consumer interpreted opaque trailing bytes')
            return
        allowed = ((manager, manager + 0x68), (stack_lo, stack_hi),
                   (sda - 0x5D38, sda - 0x5D34), (sda - 0x6E1C, sda - 0x6E18),
                   (sda - 0x6E24, sda - 0x6E20), (0x80381620, 0x80381660))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Native Body Check read exceeds fixture/table bounds')

    def write(_cpu, _access, address, size, _value, _context):
        allowed = ((stack_lo, stack_hi), (manager + 0x20, manager + 0x21),
                   (manager + 0x24, manager + 0x28),
                   (buffer_address, buffer_address + MAX_DATASET_BYTES))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Unexpected native Body Check read-consumer write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    aggregate_reads = aggregate_conversions = checked_headers = clears = 0
    native_totals = {key: 0 for key in native_calls}
    for current, expected in zip(cases, expectations, strict=True):
        state = bytearray(b'\xA5' * 0x68)
        state[0x20] = int(current['latched_flag'])
        struct.pack_into('>i', state, 0x24, current['diagnostic_code'])
        struct.pack_into('>I', state, 0x60, data_object)
        for pointer, value in ((manager, bytes(state)),
                               (data_object, object_tag + current['buffer'])):
            cpu.mem_write(pointer - 32, guard)
            cpu.mem_write(pointer, value)
            cpu.mem_write(pointer + len(value), guard)
        cpu.mem_write(stack_lo - 32, guard)
        cpu.mem_write(stack_hi, guard)
        globals_before = {sda - 0x5D38: struct.pack('>I', reader_context),
                          sda - 0x6E1C: struct.pack('>I', filename),
                          sda - 0x6E24: struct.pack('>I', diagnostic_input)}
        for pointer, value in globals_before.items():
            cpu.mem_write(pointer, value)
        read_calls = conversion_calls = 0
        native_calls = {key: 0 for key in native_calls}
        reported_length_pointer = None
        dataset_reads.clear()
        for register, value in {1: stack, 3: manager, 13: sda}.items():
            cpu.reg_write(UC_PPC_REG_0 + register, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(READ_BEGIN, stop, count=50000, timeout=2000000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Native Body Check read consumer exceeded its execution budget')
        if (cpu.reg_read(UC_PPC_REG_0 + 3) != expected.native_return
                or read_calls != int(expected.read_invoked)
                or conversion_calls != int(expected.diagnostic_conversion_requested)
                or bool(dataset_reads) != expected.header_crc_checked
                or native_calls != {'copy': int(expected.header_crc_checked),
                                     'clear': int(expected.buffer_cleared),
                                     'crc': int(expected.header_crc_checked),
                                     'filename': int(expected.read_invoked),
                                     'last_diagnostic': int(expected.diagnostic_conversion_requested)}):
            raise ValueError('Native Body Check read-completion outcome differs from component')
        state[0x20] = int(expected.latched_flag)
        struct.pack_into('>i', state, 0x24, expected.diagnostic_code)
        for pointer, value in ((manager, bytes(state)), (data_object, object_tag + expected.buffer)):
            if (bytes(cpu.mem_read(pointer, len(value))) != value
                    or bytes(cpu.mem_read(pointer - 32, 32)) != guard
                    or bytes(cpu.mem_read(pointer + len(value), 32)) != guard):
                raise ValueError('Native Body Check completion state/input guard mismatch')
        if (bytes(cpu.mem_read(stack_lo - 32, 32)) != guard
                or bytes(cpu.mem_read(stack_hi, 32)) != guard
                or any(bytes(cpu.mem_read(pointer, len(value))) != value
                       for pointer, value in globals_before.items())):
            raise ValueError('Native Body Check completion stack/global guard mismatch')
        aggregate_reads += read_calls
        aggregate_conversions += conversion_calls
        checked_headers += int(expected.header_crc_checked)
        clears += int(expected.buffer_cleared)
        for name, count in native_calls.items():
            native_totals[name] += count
    return {'original_main_sha256': SOURCE_SHA256, 'read_consumer_cases': len(cases),
            'read_boundary_calls': aggregate_reads, 'diagnostic_boundary_calls': aggregate_conversions,
            'header_crc_checked_cases': checked_headers, 'buffer_clear_cases': clears,
            'original_helper_calls': native_totals,
            'instructions': all_instructions, 'complete_original_read_consumer_executed': True,
            'original_copy_clear_and_crc_stubbed': False,
            'filesystem_read_and_diagnostic_conversion_stubbed': True,
            'dataset_reads_bounded_to_header': True, 'state_input_and_stack_guards_verified': True,
            'reported_length_not_used_by_selected_consumer': True,
            'opaque_payload_semantics_or_authentication_verified': False,
            'native_ui_verified': False, 'save_or_profile_modified': False}


def verify_header_pair_gate(source: bytes, pairs):
    _source(source)
    if type(pairs) not in (list, tuple) or not 1 <= len(pairs) <= 256:
        raise ValueError('Expected bounded explicit header-pair fixtures')
    expectations = []
    for pair in pairs:
        if type(pair) not in (tuple, list) or len(pair) != 2:
            raise ValueError('Expected two explicit opaque header words')
        expectations.append(evaluate_header_pair_gate(*pair))
    cpu = _cpu(source)
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    obj, sda = 0x81000000, 0x81508000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'P' * 32
    instructions = copy_calls = 0

    def code(_cpu, address, _size, _context):
        nonlocal instructions, copy_calls
        instructions += 1
        if address == 0x80004000:
            copy_calls += 1
        if not (PAIR_BEGIN <= address < PAIR_END or 0x80004000 <= address < 0x8000429C):
            raise ValueError('Unexpected native Body Check header-pair control flow')

    def read(_cpu, _access, address, size, _value, _context):
        allowed = ((obj + 0x10, obj + 0x14), (sda - 0x6028, sda - 0x6024), (stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Native Body Check header-pair read exceeds fixture bounds')

    def write(_cpu, _access, address, size, _value, _context):
        if not stack_lo <= address < address + size <= stack_hi:
            raise ValueError('Unexpected native Body Check header-pair write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    global_value = struct.pack('>I', obj)
    cpu.mem_write(sda - 0x6028, global_value)
    for pair, expected in zip(pairs, expectations, strict=True):
        copies_before = copy_calls
        data = bytes(16) + struct.pack('>HH', *pair)
        cpu.mem_write(obj - 32, guard)
        cpu.mem_write(obj, data)
        cpu.mem_write(obj + len(data), guard)
        cpu.mem_write(stack_lo - 32, guard)
        cpu.mem_write(stack_hi, guard)
        for register, value in {1: stack, 13: sda}.items():
            cpu.reg_write(UC_PPC_REG_0 + register, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(PAIR_BEGIN, stop, count=2000, timeout=100000)
        if (cpu.reg_read(UC_PPC_REG_PC) != stop or copy_calls - copies_before != 2
                or cpu.reg_read(UC_PPC_REG_0 + 3) != int(expected)):
            raise ValueError('Native Body Check opaque header-pair outcome differs')
        for pointer, value in ((obj, data),):
            if (bytes(cpu.mem_read(pointer, len(value))) != value
                    or bytes(cpu.mem_read(pointer - 32, 32)) != guard
                    or bytes(cpu.mem_read(pointer + len(value), 32)) != guard):
                raise ValueError('Native Body Check header-pair input/guard changed')
        if (bytes(cpu.mem_read(stack_lo - 32, 32)) != guard
                or bytes(cpu.mem_read(stack_hi, 32)) != guard
                or bytes(cpu.mem_read(sda - 0x6028, 4)) != global_value):
            raise ValueError('Native Body Check header-pair stack/global guard changed')
    return {'original_main_sha256': SOURCE_SHA256, 'opaque_header_pair_cases': len(pairs),
            'instructions': instructions, 'complete_original_header_pair_gate_executed': True,
            'original_two_byte_copy_calls': copy_calls,
            'original_copy_or_header_predicate_stubbed': False, 'service_boundaries_stubbed': False,
            'input_and_stack_guards_verified': True, 'header_word_meanings_verified': False,
            'native_menu_transition_or_display_verified': False, 'save_or_profile_modified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='private original decoded HFNJ v256 application')
    args = parser.parse_args(argv)
    try:
        with args.source.open('rb') as stream:
            source = stream.read(SOURCE_BYTES + 1)
        report = {'read_completion': verify_read_completion(source, synthetic_read_cases()),
                  'header_pair_gate': verify_header_pair_gate(source, synthetic_header_pairs())}
    except (OSError, ValueError, ImportError):
        print('Body Check completion input or optional dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
