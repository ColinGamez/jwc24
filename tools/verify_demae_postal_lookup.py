"""Compare bounded processed postal lookup with the native HCCJ consumer.

Synthetic inputs only; no encrypted download, address save or production route.
"""
import hashlib
import struct

from jwc24.demae import lookup_processed_postal
from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, data, postal_code):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    expected = lookup_processed_postal(data, postal_code)
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    def hook(cpu, address, size, user):
        if address == 0x817FF000:
            cpu.emu_stop()
            return
        args = [cpu.reg_read(UC_PPC_REG_0+n) for n in (3, 4, 5)]
        if address == 0x80004338:
            cpu.mem_write(args[0], bytes(cpu.mem_read(args[1], args[2])))
        else:
            cpu.mem_write(args[0], bytes([args[1] & 255])*args[2])
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x817FF000, 0x80004338, 0x8000443C):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    if data:
        cpu.mem_write(0x81000000, data)
    output = 0x81100000
    sentinel = b'!'*0x104
    cpu.mem_write(output, sentinel)
    for register, value in {1: 0x817E0000, 2: 0x80374C40, 13: 0x80373820,
                            3: 0x81000000, 4: len(data), 5: postal_code, 6: output}.items():
        cpu.reg_write(UC_PPC_REG_0+register, value)
    cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
    cpu.emu_start(0x8002EBCC, 0x817FF004, count=5_000_000)
    if cpu.reg_read(UC_PPC_REG_PC) != 0x817FF000:
        raise ValueError('Native postal lookup did not return')
    status = cpu.reg_read(UC_PPC_REG_0+3)
    if status != {'exact': 0, 'alternative': 1, 'not_found': 2}[expected.kind]:
        raise ValueError('Native postal lookup result kind differs')
    received = bytes(cpu.mem_read(output, 0x104))
    if expected.record is None:
        if received != sentinel:
            raise ValueError('Missing native postal lookup changed output')
    else:
        if struct.unpack_from('>I', received)[0] != expected.record.postal_code:
            raise ValueError('Native postal lookup selected a different code')
        for offset, units, value in zip((4, 0x44, 0x84), (32, 32, 64), expected.record.strings):
            wanted = (value.encode('utf-16-be')+b'\0\0').ljust(units*2, b'\0')
            if received[offset:offset+units*2] != wanted:
                raise ValueError('Native postal lookup text differs')
    return {'result_kind': expected.kind, 'native_lookup_mocked': False,
            'libc_mocked': True, 'download_transport_verified': False,
            'native_ui_verified': False, 'delivery_eligibility_verified': False}
