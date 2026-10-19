"""Execute native menu text setters, linked-list insertion and selection.

Allocation, free, memcpy and string lengths are mocked. Model code and text
copies are native; lunch data and UI rendering are outside this check.
"""
import hashlib
import struct

from tools.inspect_demae_references import sections


def verify(source, entries, *, fail_allocation=None):
    if hashlib.sha256(source).hexdigest() != 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830':
        raise ValueError('Native menu model source fingerprint mismatch')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
        raise ValueError('Expected bounded native menu model test rows')
    if fail_allocation is not None and (type(fail_allocation) is not int or fail_allocation < 1):
        raise ValueError('Expected a positive native allocation failure index')
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def word(address):
        return struct.unpack('>I', cpu.mem_read(address, 4))[0]
    def string(address, wide=False):
        raw = bytes(cpu.mem_read(address, 4096))
        if wide:
            end = next(n for n in range(0, len(raw), 2) if raw[n:n+2] == b'\0\0')
            return raw[:end]
        return raw.split(b'\0', 1)[0]
    heap = 0x81000000
    def allocate(data):
        nonlocal heap
        address = heap
        heap += max(32, (len(data)+31)//32*32)
        if heap >= 0x81700000:
            raise ValueError('Native menu test heap exhausted')
        cpu.mem_write(address, data)
        return address
    allocations = 0
    def hook(cpu, address, size, data):
        nonlocal allocations
        if address == 0x817FF000:
            cpu.emu_stop()
            return
        if address == 0x80022AE0:
            allocations += 1
            cpu.reg_write(UC_PPC_REG_0+3,
                          0 if allocations == fail_allocation else allocate(bytes(reg(3))))
        elif address == 0x80004000:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
        elif address in (0x800FB34C, 0x801050D0):
            raw = string(reg(3), address == 0x801050D0)
            cpu.reg_write(UC_PPC_REG_0+3, len(raw)//(2 if address == 0x801050D0 else 1))
        # Free is mocked; allocations stay readable to check deep copying.
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x817FF000, 0x80022AE0, 0x80022AF4, 0x80004000, 0x800FB34C, 0x801050D0):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    def call(address, **values):
        for n, value in {1: 0x817E0000, 2: 0x8047A440, 13: 0x80478660,
                         **{int(k): v for k,v in values.items()}}.items():
            cpu.reg_write(UC_PPC_REG_0+n, value)
        cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
        cpu.emu_start(address, 0x817FF004, count=1_000_000)
        if cpu.reg_read(UC_PPC_REG_PC) != 0x817FF000:
            raise ValueError('Native menu model did not return')
        return reg(3)
    model, record = 0x80900000, 0x80901000
    def failed(stage, completed_rows):
        if allocations != fail_allocation:
            raise ValueError('Unexpected native menu allocation failure')
        if word(model) != completed_rows:
            raise ValueError('Failed native operation changed linked menu row count')
        # Previously linked records must remain selectable after a failure.
        for index in range(completed_rows):
            node = call(0x80029F00, **{'3': model, '4': index})
            retained = {key: string(word(node+offset), wide).decode('utf-16-be' if wide else 'cp932')
                for key, offset, wide in [('menuCode', 4, False), ('linkTitle', 8, True),
                                         ('name', 16, True), ('info', 20, True), ('setNum', 24, False)]} if node else {}
            if node:
                retained['enabledLink'] = word(node+12)
            if retained != entries[index]:
                raise ValueError('Allocation failure damaged previously linked menu rows')
        return {'allocation_failure_handled': True, 'failed_stage': stage,
                'failed_allocation': fail_allocation, 'rows_retained': completed_rows,
                'native_model_mocked': False, 'native_rendering_verified': False}
    setters = {'menuCode': (0x8002A468, False), 'linkTitle': (0x8002A524, True),
               'name': (0x8002A5FC, True), 'info': (0x8002A6C0, True), 'setNum': (0x8002A784, False)}
    for index, entry in enumerate(entries):
        call(0x80029F28, **{'3': record})
        for key, (setter, wide) in setters.items():
            value = entry[key]
            if not isinstance(value, str) or not value or len(value) > 128 or '\0' in value:
                raise ValueError('Invalid menu model test label')
            encoded = value.encode('utf-16-be' if wide else 'cp932') + (b'\0\0' if wide else b'\0')
            if call(setter, **{'3': record, '4': allocate(encoded)}) != 1:
                return failed('setter:'+key, index)
        if type(entry['enabledLink']) is not int or entry['enabledLink'] not in (0, 1):
            raise ValueError('Invalid menu model test flag')
        call(0x8002A5E8, **{'3': record, '4': entry['enabledLink']})
        if not call(0x80029D08, **{'3': model, '4': index, '5': record}):
            return failed('insertion', index)
        # Destroy/reinitialize the original to ensure linked nodes own copies.
        call(0x80029FCC, **{'3': record})
    if word(model) != len(entries):
        raise ValueError('Native menu model count differs')
    received = []
    for index in range(len(entries)):
        node = call(0x80029F00, **{'3': model, '4': index})
        received.append({key: string(word(node+offset), wide).decode('utf-16-be' if wide else 'cp932')
            for key, offset, wide in [('menuCode', 4, False), ('linkTitle', 8, True),
                                     ('name', 16, True), ('info', 20, True), ('setNum', 24, False)]})
        received[-1]['enabledLink'] = word(node+12)
    if received != entries:
        raise ValueError('Native menu text or insertion order differs')
    if fail_allocation is not None:
        raise ValueError('Requested native allocation failure was not reached')
    return {'rows_verified': len(received), 'native_model_mocked': False,
            'allocation_and_libc_mocked': True, 'lunch_verified': False,
            'native_rendering_verified': False}
