"""Complete original FD descriptor/URL construction on guarded synthetic state."""
from __future__ import annotations

import hashlib
import struct

from jwc24.cmoc_request import build_first_data_request
from tools.verify_cmoc_framing import SOURCE_SHA256

ORIGINAL_ORIGIN = 'http://miicontest.wapp.wii.com'


def verify_first_data_request(source: bytes, **inputs):
    expected = build_first_data_request(origin=ORIGINAL_ORIGIN, **inputs)
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
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('CMOC section exceeds guarded RAM')
        cpu.mem_write(address, source[offset:offset + size])
    descriptor, singleton, manager, configuration = 0x81000000, 0x81001000, 0x81002000, 0x81003000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    sda = 0x80432BA0
    config_global = sda - 0x69C8
    original_slot = bytes(cpu.mem_read(config_global, 4))
    initial = bytearray(b'\xA5' * 0xC0)
    initial[12:32] = inputs['opaque_header_tail']
    single = bytearray(b'\xA5' * 0x20)
    single[0x10], single[0x11] = inputs['byte_2'], inputs['byte_3']
    manager_bytes = bytearray(b'\xA5' * 0x30)
    struct.pack_into('>I', manager_bytes, 0x2C, 1)
    configuration_bytes = bytearray(b'\xA5' * 0x800)
    struct.pack_into('>I', configuration_bytes, 0xE8 + 0x67C,
                     1 if inputs['configuration_2c_predicate'] else 0)
    objects = ((descriptor, bytes(initial)), (singleton, bytes(single)),
               (manager, bytes(manager_bytes)), (configuration, bytes(configuration_bytes)))
    guard = b'REQUEST-GUARD!!!' * 2
    for pointer, value in objects:
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(config_global, struct.pack('>I', configuration))
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'singleton_lookups_stubbed': 0,
              'manager_lookups_stubbed': 0, 'native_snprintf_calls': 0,
              'native_configuration_predicate_calls': 0}

    def ret(value):
        cpu.reg_write(UC_PPC_REG_0 + 3, value)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        counts['instructions'] += 1
        if address == 0x80064EF4:
            counts['singleton_lookups_stubbed'] += 1
            ret(singleton)
            return
        if address == 0x800650A4:
            counts['manager_lookups_stubbed'] += 1
            ret(manager)
            return
        if address == 0x800DC68C:
            counts['native_snprintf_calls'] += 1
        if address == 0x8003C2C4:
            counts['native_configuration_predicate_calls'] += 1
        allowed = ((0x80069A18, 0x80069AC0), (0x80074248, 0x80074AA0),
                   (0x800697F4, 0x8006980C), (0x8003C2C4, 0x8003C448),
                   (0x800D5EEC, 0x800D6000), (0x800D64D0, 0x800D6580),
                   (0x800DA2E0, 0x800DBA00),
                   (0x800DBA00, 0x800E8000),
                   (0x80004000, 0x80004134))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC request control flow at {address:#x}')

    def read(_cpu, _access, address, size, _value, _context):
        allowed = [(pointer, pointer + len(value)) for pointer, value in objects]
        allowed += [(base, base + length) for index, _, base, length in layout if index >= 7]
        allowed += [(config_global, config_global + 4), (stack_lo, stack_hi)]
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'CMOC request read exceeds guarded fixtures at {address:#x}')

    def write(_cpu, _access, address, size, _value, _context):
        allowed = ((descriptor, descriptor + 12), (descriptor + 0x20, descriptor + 0xAE),
                   (descriptor + 0xB0, descriptor + 0xB4), (stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC request write at {address:#x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for register, value in {1: stack, 2: 0x80435BE0, 13: sda,
                            3: descriptor, 4: 0x4644,
                            5: inputs['word_4'], 6: inputs['word_8']}.items():
        cpu.reg_write(UC_PPC_REG_0 + register, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80069A18, stop, count=100000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native CMOC request instruction cap reached')
    wanted = bytearray(initial)
    wanted[:32] = expected.cached_header
    wanted[0x20:0x2E] = bytes(14)
    url_bytes = expected.url.encode('ascii')
    wanted[0x2E:0x2E + len(url_bytes) + 1] = url_bytes + b'\0'
    struct.pack_into('>I', wanted, 0xB0, len(url_bytes))
    for pointer, value in objects:
        target = bytes(wanted) if pointer == descriptor else value
        if (bytes(cpu.mem_read(pointer, len(value))) != target
                or bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard):
            raise ValueError('Native CMOC request descriptor/input guards changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard
            or bytes(cpu.mem_read(config_global, 4)) != struct.pack('>I', configuration)):
        raise ValueError('Native CMOC request stack/configuration guards changed')
    cpu.mem_write(config_global, original_slot)  # Synthetic RAM only.
    return {**expected.metadata(), 'counts': counts,
            'complete_request_seed_and_descriptor_constructor_executed': True,
            'native_printf_header_copy_suffix_or_config_predicate_stubbed': False,
            'only_singleton_and_manager_lookup_boundaries_stubbed': True,
            'opaque_header_tail_preserved_unchanged': True,
            'input_descriptor_and_stack_guards_verified': True}
