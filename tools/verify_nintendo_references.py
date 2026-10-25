"""Native Japanese CSData list-reference construction using synthetic configuration.

Only private original executable bytes and caller fixtures are read. No network,
filesystem services, device profile, initialization or original endpoint is used.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_csdata import decompress_csdata
from jwc24.nintendo_references import build_japanese_list_reference
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA


def verify_list_reference(source: bytes, payload: bytes, *, service_prefix: bytes,
                          language_code: int):
    expected = build_japanese_list_reference(payload, service_prefix=service_prefix,
                                             language_code=language_code)
    if (not isinstance(source, bytes) or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    raw, _kind = decompress_csdata(payload)
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    code_ranges = []
    for index, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Nintendo Channel DOL section exceeds the emulation map')
        cpu.mem_write(address, source[offset:offset + size])
        if index < 7:
            code_ranges.append((address, address + size))
    obj, data, stop = 0x81001000, 0x81010000, 0x817FF000
    stack_lo, stack_hi = 0x817D0000, 0x817E1000
    guard = b'LIST-GUARD!' * 4
    cpu.mem_write(obj - len(guard), guard)
    cpu.mem_write(obj, bytes(0x220))
    cpu.mem_write(obj + 0x220, guard)
    cpu.mem_write(data - len(guard), guard)
    cpu.mem_write(data, raw)
    cpu.mem_write(data + len(raw), guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    # Original ABI bases; only configuration storage is replaced in RAM.
    r2, r13 = 0x80808460, 0x808041E0
    prefix_slot = 0x8040AF30 + 0x20C
    prefix_bytes = service_prefix + bytes(512 - len(service_prefix))
    settings = ((prefix_slot, prefix_bytes), (r13 - 0x4E08, struct.pack('>I', 255)),
                (r13 - 0x7A8C, struct.pack('>I', 1)),
                (r13 - 0x4E00, struct.pack('>I', language_code)))
    for address, value in settings:
        cpu.mem_write(address, value)
    counts = {'instructions': 0, 'logs_stubbed': 0}
    visited = set()
    handoff_phase = False
    handoff_reached = False
    context, manager, vtable, callback = 0x81040000, 0x80408488, 0x81050000, 0x817FF100

    def instruction(_cpu, address, _size, _context):
        nonlocal handoff_reached
        counts['instructions'] += 1
        visited.add(address)
        if address == callback and handoff_phase:
            pointer = cpu.reg_read(UC_PPC_REG_0 + 4)
            if pointer != manager + 0x2870:
                raise ValueError('Unexpected native list handoff reference pointer')
            handed = bytes(cpu.mem_read(pointer, 512)).split(b'\0', 1)[0]
            if handed != expected.reference:
                raise ValueError('Native list handoff reference differs from independent plan')
            handoff_reached = True
            cpu.emu_stop()
            return
        if address == 0x8021F810 and handoff_phase:
            counts['time_calls_stubbed'] = counts.get('time_calls_stubbed', 0) + 1
            cpu.reg_write(UC_PPC_REG_0 + 3, 0)
            cpu.reg_write(UC_PPC_REG_0 + 4, 0)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if address == 0x80027070:
            counts['logs_stubbed'] += 1
            cpu.reg_write(UC_PPC_REG_0 + 3, 0)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if not any(lo <= address < hi for lo, hi in code_ranges):
            raise ValueError('Unexpected Nintendo Channel reference control flow')

    def write(_cpu, _access, address, size, _value, _context):
        if ((stack_lo <= address < address + size <= stack_hi)
                or (obj <= address < address + size <= obj + 0x220)
                or (data + 8 <= address < address + size <= data + 12)
                or (handoff_phase and context + 0x27A8 <= address < address + size <= context + 0x29A8)
                or (handoff_phase and manager + 0x2870 <= address < address + size <= manager + 0x2A70)):
            return
        raise ValueError('Unexpected Nintendo Channel reference write')

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for index, value in {1: 0x817E0000, 2: r2, 13: r13, 3: obj, 4: data}.items():
        cpu.reg_write(UC_PPC_REG_0 + index, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x800324D0, stop, count=3000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native reference construction exceeded its instruction cap')
    if cpu.reg_read(UC_PPC_REG_0 + 3) != 1:
        raise ValueError('Native reference consumer rejected the synthetic fixture')
    actual = bytes(cpu.mem_read(obj + 4, 512)).split(b'\0', 1)[0]
    if actual != expected.reference:
        raise ValueError('Native Nintendo Channel list reference differs from independent plan')
    # Execute the downstream caller's original copy and manager-copy code,
    # stopping before its virtual transport callback runs. Earlier allocation,
    # language eligibility, network initialization and polling are not executed.
    handoff_phase = True
    cpu.mem_write(context - len(guard), guard)
    cpu.mem_write(context, bytes(0x2C00))
    cpu.mem_write(context + 0x278C, struct.pack('>I', obj))
    cpu.mem_write(context + 0x2C00, guard)
    cpu.mem_write(manager + 0x2870 - len(guard), guard)
    cpu.mem_write(manager + 0x2870, bytes(512))
    cpu.mem_write(manager + 0x2A70, guard)
    synthetic_manager = struct.pack('>4I', 0x81060000, 4096, 0, 0)
    cpu.mem_write(manager, synthetic_manager)
    cpu.mem_write(manager + 0x10, struct.pack('>I', vtable))
    cpu.mem_write(vtable, bytes(8) + struct.pack('>I', callback))
    cpu.reg_write(UC_PPC_REG_0 + 30, context)
    cpu.reg_write(UC_PPC_REG_0 + 1, 0x817DFF80)
    cpu.emu_start(0x8002678C, stop, count=100000)
    if not handoff_reached:
        raise ValueError('Native list handoff did not reach the intercepted callback')
    for address, value in ((obj - len(guard), guard), (obj + 0x220, guard),
                           (data - len(guard), guard), (data, raw),
                           (data + len(raw), guard), (stack_lo - len(guard), guard),
                           (stack_hi, guard), (context - len(guard), guard),
                           (context + 0x2C00, guard),
                           (context + 0x278C, struct.pack('>I', obj)),
                           (manager + 0x2870 - len(guard), guard),
                           (manager + 0x2A70, guard), (manager, synthetic_manager),
                           (manager + 0x10, struct.pack('>I', vtable)),
                           (vtable, bytes(8) + struct.pack('>I', callback)), *settings):
        if bytes(cpu.mem_read(address, len(value))) != value:
            raise ValueError('Native reference input, configuration or guard changed')
    return {
        'reference_bytes': len(actual),
        'reference_sha256': hashlib.sha256(actual).hexdigest(),
        'native_crc_executed': 0x802A2250 in visited,
        'native_reference_append_executed': 0x800085E0 in visited,
        'native_decimal_formatter_executed': 0x80008AE0 in visited,
        'native_country_resolver_executed': 0x80031DD0 in visited,
        'native_language_resolver_executed': 0x800321F0 in visited,
        'native_reference_matches_independent_plan': True,
        'native_caller_and_manager_copies_executed': True,
        'transport_callback_intercepted_before_execution': True,
        'configuration_and_guards_verified': True,
        'counts': counts,
        'catalog_download_or_records_verified': False,
        'channel_language_eligibility_checked': False,
        'network_transport_executed': False,
        'native_ui_verified': False,
    }
