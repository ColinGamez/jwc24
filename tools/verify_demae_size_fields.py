"""Execute native size-row setters; no XML, stock interpretation or UI claim."""
import hashlib
import struct

from tools.inspect_demae_references import sections


def verify(source, values, *, fail_field=None):
    if hashlib.sha256(source).hexdigest() != 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830':
        raise ValueError('Native size field source fingerprint mismatch')
    fields = {'itemCode': (0x800296C0, 4, False),
              'size': (0x8002977C, 8, True),
              'price': (0x80029840, 12, True),
              'isSoldout': (0x800299C8, 20, False)}
    if not isinstance(values, dict) or set(values) != set(fields):
        raise ValueError('Expected all four size fields')
    if fail_field is not None and fail_field not in fields:
        raise ValueError('Unknown size failure field')
    encoded = {}
    for key, (_, _, wide) in fields.items():
        value = values[key]
        if not isinstance(value, str) or not value or len(value) > 128 or '\0' in value:
            raise ValueError('Expected bounded nonempty size text')
        encoded[key] = value.encode('utf-16-be' if wide else 'cp932') + bytes(2 if wide else 1)
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    heap, record, active = 0x81000000, 0x80900000, None
    freed = []
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def allocate(data):
        nonlocal heap
        address = heap
        heap += max(32, (len(data)+31)//32*32)
        if heap >= 0x81700000:
            raise ValueError('Native size test heap exhausted')
        cpu.mem_write(address, data)
        return address
    def hook(cpu, address, size, data):
        if address == 0x817FF000:
            cpu.emu_stop()
            return
        if address == 0x80022B28:
            cpu.reg_write(UC_PPC_REG_0+3, 0 if active == fail_field else allocate(bytes(reg(3))))
        elif address == 0x80022B3C:
            freed.append(reg(3))
        elif address == 0x80004000:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
        else:
            wide = address == 0x801050D0
            raw = bytes(cpu.mem_read(reg(3), 1024))
            length = next(n for n in range(0, len(raw), 2) if raw[n:n+2] == b'\0\0')//2 if wide else raw.index(0)
            cpu.reg_write(UC_PPC_REG_0+3, length)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x817FF000, 0x80022B28, 0x80022B3C, 0x80004000, 0x800FB34C, 0x801050D0):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    def call(address, pointer):
        for n, value in {1: 0x817E0000, 2: 0x8047A440, 13: 0x80478660, 3: record, 4: pointer}.items():
            cpu.reg_write(UC_PPC_REG_0+n, value)
        cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
        cpu.emu_start(address, 0x817FF004, count=100_000)
        if cpu.reg_read(UC_PPC_REG_PC) != 0x817FF000:
            raise ValueError('Native size setter did not return')
        return reg(3)
    for active, (setter, offset, _) in fields.items():
        # Start with owned text to exercise replacement and failure cleanup.
        old = allocate(b'old\0')
        cpu.mem_write(record+offset, struct.pack('>I', old))
        pointer = allocate(encoded[active])
        result = call(setter, pointer)
        stored = struct.unpack('>I', cpu.mem_read(record+offset, 4))[0]
        if old not in freed:
            raise ValueError('Native setter did not release prior field')
        if active == fail_field:
            if result != 0 or stored != 0:
                raise ValueError('Native setter allocation failure differed')
            continue
        if result != 1 or stored == pointer or not stored:
            raise ValueError('Native setter did not own a copied field')
        cpu.mem_write(pointer, bytes(len(encoded[active])))
        if bytes(cpu.mem_read(stored, len(encoded[active]))) != encoded[active]:
            raise ValueError('Native size text copy differed')
    return {'fields_verified': len(fields), 'failed_field': fail_field,
            'replacement_failure_clears_field': fail_field is not None,
            'allocation_and_libc_mocked': True, 'stock_semantics_verified': False,
            'native_rendering_verified': False}
