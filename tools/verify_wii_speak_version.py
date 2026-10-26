"""Execute HCFJ v512's version constructor/reader with synthetic VF services.

No IOS, files, keys, download task, profile, DWC or voice service is used. Only
the fingerprinted retail application executes; VF and allocator calls are mocks.
"""
from __future__ import annotations

import hashlib
import struct

SOURCE_SHA256 = '7da329f17754d3199b6254f26c3e059913671820f9017c2424236430aa64eff3'
MAX_FIXTURE_BYTES = 8192


def verify_version_reader(source: bytes, data: bytes):
    if (type(source) is not bytes or len(source) > 5 * 1024 * 1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('Japanese Wii Speak v512 executable fingerprint mismatch')
    if type(data) is not bytes or len(data) > MAX_FIXTURE_BYTES:
        raise ValueError('Expected bounded synthetic VF file bytes')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC

    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    source_ranges = []
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
        source_ranges.append((address, address + size))
    obj, sda, handle = 0x81000000, 0x81600000, 0x81002000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    allocations = [(obj, obj + 32), (stack_lo, stack_hi)]
    globals_ = [(sda - 0x61E0, sda - 0x61D8), (sda - 0x78D0, sda - 0x78CC),
                (sda - 0x5770, sda - 0x5768)]
    guard = b'HCFJ-VERSION-GUARD' * 2
    for lo, hi in allocations:
        cpu.mem_write(lo - len(guard), guard)
        cpu.mem_write(hi, guard)
    events, instructions = [], 0

    def reg(i):
        return cpu.reg_read(UC_PPC_REG_0 + i)

    def word(pointer, value):
        cpu.mem_write(pointer, struct.pack('>I', value & 0xFFFFFFFF))

    def returned(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        nonlocal instructions
        instructions += 1
        if address == 0x8018FA78:
            if reg(3) != 32:
                raise ValueError('Unexpected native allocation')
            events.append('allocate_object_mock')
            returned(obj)
        elif address == 0x80197654:
            events.append('base_constructor_mock')
            returned(reg(3))
        elif address == 0x802AC6F0:
            events.append('get_vf_path_mock')
            returned()
        elif address == 0x8029F7A8:
            returned()  # SDK error-state query, no IO.
        elif address == 0x802CADB4:
            events.append('mount_mock')
            returned()
        elif address == 0x802CB5B4:
            events.append('open_mock')
            returned(handle)
        elif address == 0x802CBB20:
            events.append('size_mock')
            returned(len(data))
        elif address == 0x802CB788:
            if reg(4) != obj + 16 or reg(5) != len(data) or len(data) > 8:
                raise ValueError('Native VF read exceeded its supplied capacity')
            events.append('read_mock')
            cpu.mem_write(reg(4), data)
            returned()
        elif address in (0x802CB690, 0x802CB258):
            events.append('close_mock' if address == 0x802CB690 else 'unmount_mock')
            returned()
        elif not any(lo <= address < hi for lo, hi in (
                (0x80052174, 0x800521FC), (0x801A9780, 0x801A9890),
                (0x801A8C58, 0x801A8CA0), (0x80095F30, 0x80095F48),
                (0x80044EA8, 0x80044EBC))):
            raise ValueError('Unexpected native Wii Speak control flow')

    def read(_cpu, _access, address, size, _value, _context):
        if not any(lo <= address < address + size <= hi
                   for lo, hi in allocations + globals_ + source_ranges):
            raise ValueError('Native Wii Speak read exceeded fixture bounds')

    def write(_cpu, _access, address, size, _value, _context):
        if not any(lo <= address < address + size <= hi for lo, hi in allocations + globals_):
            raise ValueError('Native Wii Speak write exceeded fixture bounds')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def run(entry, until=stop, arguments=()):
        cpu.reg_write(UC_PPC_REG_0 + 1, stack)
        cpu.reg_write(UC_PPC_REG_0 + 13, sda)
        for i, value in enumerate(arguments, 3):
            cpu.reg_write(UC_PPC_REG_0 + i, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(entry, until, count=10000)
        if cpu.reg_read(UC_PPC_REG_PC) != until:
            raise ValueError('Native Wii Speak instruction cap reached')
        for lo, hi in allocations:
            if (bytes(cpu.mem_read(lo - len(guard), len(guard))) != guard
                    or bytes(cpu.mem_read(hi, len(guard))) != guard):
                raise ValueError('Native Wii Speak fixture guard changed')
        return reg(3)

    run(0x80052174, arguments=(0, 4))
    initial = bytes(cpu.mem_read(obj + 16, 8))
    pointer, capacity = struct.unpack('>II', cpu.mem_read(obj + 24, 8))
    if pointer != obj + 16 or capacity != 8:
        raise ValueError('Unexpected native version destination')
    status = run(0x801A9780, arguments=(pointer, capacity, 0x803AE396, 0))
    output = bytes(cpu.mem_read(pointer, capacity))
    run(0x80095F30, until=0x80095F48)
    newer = bool(reg(3))
    # The genuine caller has a larger object; this slice only reads its size.
    cpu.reg_write(UC_PPC_REG_0 + 3, obj - 0x3BC)
    # r3+0x3BC is the already guarded object's first word (synthetic size).
    run(0x80044EA8, until=0x80044EBC)
    size_limit = reg(0)
    return {'status': status, 'destination_capacity': capacity,
            'constructor_words': list(struct.unpack('>II', initial)),
            'result_words': list(struct.unpack('>II', output)),
            'newer_than_client_2': newer, 'size_limit_bytes_u32': size_limit,
            'read_performed': 'read_mock' in events,
            'events': events, 'native_instructions': instructions,
            'input_object_stack_guards_verified': True,
            'vf_allocator_and_sdk_services_mocked': True,
            'native_ios_crypto_delivery_or_voice_verified': False}
