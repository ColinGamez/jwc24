"""Exercise HCCJ's native postal decompression file wrapper offline.

Only file/heap services are mocked. Fixtures, paths and handles are synthetic;
no real files, device identifiers, keys, network or NAND services are used.
"""
import hashlib
import struct

from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, compressed, expected, *, capacity=0x40000, fault=None, expected_status=0):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    if (not isinstance(compressed, bytes) or len(compressed) > 0x40000
            or not isinstance(expected, bytes) or len(expected) > 0x40000):
        raise ValueError('Expected bounded synthetic input/output bytes')
    faults = (None, 'open_source', 'open_destination', 'allocate_input', 'allocate_output',
              'read', 'short_read', 'write', 'close_source', 'close_destination')
    if (fault not in faults or type(capacity) is not int or not 0 <= capacity <= 0x40000
            or type(expected_status) is not int or expected_status not in (0, 0x14, 0x15, 0x17, 0x18, 0x1c)):
        raise ValueError('Invalid synthetic wrapper options')
    # Never permit the size reader to cause a large native allocation, even in
    # a malformed-input experiment. The wrapper itself may reject smaller caps.
    if len(compressed) >= 8:
        declared = int.from_bytes(compressed[1:4], 'little')
        if declared == 0:
            declared = int.from_bytes(compressed[4:8], 'little')
        if declared > 0x40000:
            raise ValueError('Declared size exceeds harness bound')
        if expected_status == 0 and len(expected) != declared:
            raise ValueError('Expected output length differs from declared size')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    state = {'allocated': [], 'freed': [], 'open': set(), 'writes': [], 'unmounts': 0,
             'fault_hit': False, 'allocation_calls': 0}
    guard = b'!'*32
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def fail(name):
        if fault == name and not state['fault_hit']:
            state['fault_hit'] = True
            return True
        return False
    def hook(cpu, address, size, user):
        result = 0
        if address == 0x800a0ad0:
            handle = 1 if reg(3) == 0x80903000 else 2
            if not fail('open_source' if handle == 1 else 'open_destination'):
                state['open'].add(handle)
                result = handle
        elif address == 0x800a0f6c:
            result = len(compressed)
        elif address == 0x8016014c:
            index = state['allocation_calls']
            state['allocation_calls'] += 1
            if not fail('allocate_input' if index == 0 else 'allocate_output'):
                if index > 1 or reg(4) > 0x40000:
                    raise ValueError('Unexpected native allocation')
                result = 0x81000020+index*0x100000
                cpu.mem_write(result-32, guard+bytes(reg(4))+guard)
                state['allocated'].append((result, reg(4)))
        elif address == 0x800a0ca4:
            if reg(3) != 1 or reg(5) != len(compressed):
                raise ValueError('Unexpected native read')
            if fail('read'):
                result = 5
            else:
                count = len(compressed)-1 if fail('short_read') else len(compressed)
                if count:
                    cpu.mem_write(reg(4), compressed[:count])
                cpu.mem_write(reg(6), struct.pack('>I', count))
        elif address == 0x800a0bac:
            if fail('close_source' if reg(3) == 1 else 'close_destination'):
                result = 5
            else:
                if reg(3) not in state['open']:
                    raise ValueError('Native close of unopened synthetic handle')
                state['open'].remove(reg(3))
        elif address == 0x800a0d40:
            if reg(3) != 2 or reg(5) > 0x40000:
                raise ValueError('Unexpected native write')
            if fail('write'):
                result = 5
            else:
                state['writes'].append(bytes(cpu.mem_read(reg(4), reg(5))))
        elif address == 0x800a0918:
            state['unmounts'] += 1
        elif address == 0x8015fa1c:
            result = 0x80905000
        elif address == 0x801601fc:
            state['freed'].append(reg(4))
        cpu.reg_write(UC_PPC_REG_0+3, result)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x800a0600, 0x800a0ad0, 0x800a0f6c, 0x8016014c, 0x800a0ca4,
                    0x800a0bac, 0x800a0d40, 0x800a0918, 0x8015fa1c, 0x801601fc):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    end = 0x817ff000
    for register, value in {1: 0x817e0000, 2: 0x80374c40, 13: 0x80373820,
                           3: 0x80904000, 4: 0x80903000, 5: 0x80903100,
                           6: capacity, 7: 0x80905000, 8: 0, 9: 0}.items():
        cpu.reg_write(UC_PPC_REG_0+register, value)
    cpu.reg_write(UC_PPC_REG_LR, end)
    cpu.emu_start(0x8002d044, end, count=20_000_000)
    if cpu.reg_read(UC_PPC_REG_PC) != end or reg(3) != expected_status:
        raise ValueError(f'Native unpack wrapper status/return differs: {reg(3):#x}')
    if fault is not None and not state['fault_hit']:
        raise ValueError('Requested fault was not exercised')
    wanted_writes = [expected] if expected_status == 0 or fault == 'close_destination' else []
    if state['writes'] != wanted_writes:
        raise ValueError('Native unpack wrapper output differs')
    if (state['open'] or state['unmounts'] != 1
            or sorted(state['freed']) != sorted(address for address, _ in state['allocated'])):
        raise ValueError('Native unpack wrapper cleanup differs')
    for address, size in state['allocated']:
        if (bytes(cpu.mem_read(address-32, 32)) != guard
                or bytes(cpu.mem_read(address+size, 32)) != guard):
            raise ValueError('Native unpack allocation guard changed')
    return {'native_status': expected_status, 'native_wrapper_mocked': False,
            'native_lz_mocked': False, 'filesystem_heap_mocked': True,
            'cleanup_verified': True, 'allocation_guards_verified': True,
            'fault_exercised': fault, 'download_transport_verified': False,
            'native_ui_verified': False}
