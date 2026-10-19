"""Execute native shop-list insertion/selection with mocked allocation and copy.

This verifies linked-list capacity/order, not XML consumers, UI or image loading.
"""
import hashlib
import struct

from tools.inspect_demae_references import sections


def verify(source, count):
    if hashlib.sha256(source).hexdigest() != 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830':
        raise ValueError('Native shop model source fingerprint mismatch')
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError('Expected bounded shop count')
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def put(address, value):
        cpu.mem_write(address, struct.pack('>I', value))
    def word(address):
        return struct.unpack('>I', cpu.mem_read(address, 4))[0]
    heap = 0x81000000
    allocations = []
    def hook(cpu, address, size, data):
        nonlocal heap
        if address == 0x80022A50:
            if reg(3) != 0x9C:
                raise ValueError('Unexpected native node allocation size')
            node = heap
            heap += 0xA0
            allocations.append(node)
            cpu.mem_write(node, bytes(0xA0))
            cpu.reg_write(UC_PPC_REG_0+3, node)
        elif address == 0x800BF45C:
            pass  # Allocation was zeroed; no SDK constructor state is needed.
        elif address == 0x800BF560:
            put(reg(3), word(reg(5)))  # Stand-in record identity, not SDK text.
            cpu.reg_write(UC_PPC_REG_0+3, 1)
        else:
            cpu.emu_stop()
            return
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x80022A50, 0x800BF45C, 0x800BF560, 0x817FF000):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    def call(address, values):
        for n, value in {1: 0x817E0000, **values}.items():
            cpu.reg_write(UC_PPC_REG_0+n, value)
        cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
        cpu.emu_start(address, 0x817FF004, count=2_000_000)
        if cpu.reg_read(UC_PPC_REG_PC) != 0x817FF000:
            raise ValueError('Native shop model did not return')
        return reg(3)
    model, record = 0x80900000, 0x80901000
    for index in range(count):
        put(record, index+1)
        if not call(0x800BF0F4, {3: model, 4: index, 5: record}):
            raise ValueError('Native model rejected shop insertion')
    if word(model+8) != count:
        raise ValueError('Native model count differs')
    for index in range(count):
        node = call(0x800BF3A0, {3: model, 4: index})
        if node != allocations[index] or word(node) != index+1:
            raise ValueError('Native shop selection order differs')
    return {'native_rows_inserted': count, 'native_rows_selected': count,
            'native_node_bytes': count*0x9C, 'native_render_verified': False}
