"""Run original CMOC receive-buffer resets and configured geometry fragments.

Synthetic RAM only. No SDK, resources, crypto, socket or native UI is invoked.
"""
import hashlib
import struct

from tools.verify_cmoc_framing import SOURCE_SHA256


def verify_receive_geometry(source):
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
    worker, descriptor = 0x81000000, 0x81100000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    wire = worker + 0x298
    guard = b'CMOC-RECEIVE-GUARD' * 2
    original = bytes([0xA5]) * 0xAE0
    cpu.mem_write(worker - len(guard), guard)
    cpu.mem_write(worker, original)
    cpu.mem_write(worker + len(original), guard)
    cpu.mem_write(descriptor - len(guard), guard)
    cpu.mem_write(descriptor, bytes(12))
    cpu.mem_write(descriptor + 12, guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    state = {'stop': stop, 'instructions': 0}

    def word(address, value):
        cpu.mem_write(address, struct.pack('>I', value))

    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0 + n)

    def code(_cpu, address, _size, _ctx):
        state['instructions'] += 1
        allowed = ((0x8007F1B4, 0x8007F1F4), (0x8007F28C, 0x8007F2A8),
                   (0x8007F3A8, 0x8007F3D8), (0x8007F49C, 0x8007F4D8),
                   (0x80004000, 0x80004134), (0x800DE0A8, 0x800DE164))
        if address != state['stop'] and not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError(f'Unexpected native CMOC receive control flow at {address:#x}')

    def read(_cpu, _access, address, size, _value, _ctx):
        if not any(lo <= address < address + size <= hi for lo, hi in (
                (worker, worker + len(original)), (descriptor, descriptor + 12), (stack_lo, stack_hi))):
            raise ValueError('Unexpected native CMOC receive read')

    def write(_cpu, _access, address, size, _value, _ctx):
        if not any(lo <= address < address + size <= hi for lo, hi in (
                (worker, worker + len(original)), (stack_lo, stack_hi))):
            raise ValueError('Unexpected native CMOC receive write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def run(start, finish, registers):
        state['stop'] = finish
        before_worker = bytes(cpu.mem_read(worker, len(original)))
        before_descriptor = bytes(cpu.mem_read(descriptor, 12))
        for n in range(32):
            cpu.reg_write(UC_PPC_REG_0 + n, 0)
        for n, value in {1: stack, **registers}.items():
            cpu.reg_write(UC_PPC_REG_0 + n, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(start, finish, count=100000)
        if cpu.reg_read(UC_PPC_REG_PC) != finish:
            raise ValueError('Native CMOC receive instruction bound reached')
        if (bytes(cpu.mem_read(descriptor, 12)) != before_descriptor
                or start in (0x8007F1B4, 0x8007F49C)
                and bytes(cpu.mem_read(worker, len(original))) != before_worker):
            raise ValueError('Native CMOC receive arithmetic changed its inputs')

    resets = 0
    for entry, offset, length in ((0x8007F3C0, 0x294, 0x440),
                                 (0x8007F3A8, 0x6D8, 0x400)):
        cpu.mem_write(worker, original)
        run(entry, stop, {3: worker + offset})
        expected = original[:offset] + bytes(length + 4) + original[offset + length + 4:]
        if bytes(cpu.mem_read(worker, len(original))) != expected:
            raise ValueError('Original CMOC reset storage extent differs')
        resets += 1
    capacities = in_bounds = out_of_bounds = transforms = underflow_cases = 0
    for span in range(65):
        for prefix in range(65):
            word(worker + 0xC8, span)
            word(worker + 0x20C, prefix)
            run(0x8007F1B4, 0x8007F1F4, {31: worker, 24: 0x81200000, 25: 0})
            capacity = reg(6)
            offset = span + prefix
            if reg(5) != wire or capacity != offset + 0x400:
                raise ValueError('Original CMOC receive capacity differs')
            capacities += 1
            in_bounds += capacity <= 0x440
            out_of_bounds += capacity > 0x440
            for payload in (0, 1, 15, 16, 17, 1023, 1024):
                word(descriptor, wire)
                word(descriptor + 4, capacity)
                word(descriptor + 8, offset + payload)
                run(0x8007F49C, 0x8007F4D8, {3: worker, 31: worker, 28: descriptor})
                if reg(29) != wire + offset or reg(30) != (payload + 15) & ~15:
                    raise ValueError('Original CMOC rounded input geometry differs')
                transforms += 1
            for deficit in (1, 15, 16, 17):
                if deficit > offset:
                    continue
                word(descriptor + 8, offset - deficit)
                run(0x8007F49C, 0x8007F4D8, {3: worker, 31: worker, 28: descriptor})
                if reg(30) != ((-deficit + 15) & 0xFFFFFFF0):
                    raise ValueError('Original CMOC partial-header arithmetic differs')
                underflow_cases += 1
    for pointer, length in ((worker, len(original)), (descriptor, 12)):
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + length, len(guard))) != guard):
            raise ValueError('CMOC receive object guard changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('CMOC receive stack guard changed')
    return dict(source_application_sha256=SOURCE_SHA256, original_storage_resets=resets,
        wire_storage_bytes=0x440, intermediate_storage_bytes=0x400,
        original_capacity_cases=capacities, capacity_fits_storage_cases=in_bounds,
        capacity_exceeds_storage_cases=out_of_bounds, original_rounding_cases=transforms,
        original_partial_header_cases=underflow_cases, instructions=state['instructions'],
        original_helpers_or_memset_stubbed=False, object_and_stack_guards_unchanged=True,
        actual_live_resource_sizes_verified=False, sdk_chunking_or_crypto_verified=False)
