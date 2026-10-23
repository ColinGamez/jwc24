"""Exercise the native zpcd gate using synthetic headers only.

This checks the small header gate, not the decrypt/decompress callback or WC24.
"""
import hashlib
import struct

from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    buffer, output, end = 0x81000000, 0x81100004, 0x817FF000
    sentinel = b'UNCHANGED!!!'
    cases = [(b'zpcd'+bytes([offset]), 5, True, offset) for offset in range(256)]
    # Short declared lengths must fail even when backing memory has the magic.
    cases += [(b'zpcd\x10', size, False, None) for size in range(5)]
    for index in range(4):
        bad = bytearray(b'zpcd\x10')
        bad[index] ^= 1
        cases.append((bytes(bad), 5, False, None))
    cases.append((b'zpcd\x10'+bytes(27), 32, True, 16))
    for data, length, accepted, offset in cases:
        cpu.mem_write(buffer, data)
        cpu.mem_write(output-4, sentinel)
        for register, value in {3: buffer, 4: length, 5: output}.items():
            cpu.reg_write(UC_PPC_REG_0+register, value)
        cpu.reg_write(UC_PPC_REG_LR, end)
        cpu.emu_start(0x8002E954, end, count=1000)
        if cpu.reg_read(UC_PPC_REG_PC) != end:
            raise ValueError('Native postal header gate did not return')
        if cpu.reg_read(UC_PPC_REG_0+3) != int(accepted):
            raise ValueError('Native postal header acceptance differs')
        wanted = sentinel if not accepted else sentinel[:4]+struct.pack('>I', offset)+sentinel[8:]
        if bytes(cpu.mem_read(output-4, len(sentinel))) != wanted:
            raise ValueError('Native postal header output or guard differs')
    return {'synthetic_cases': len(cases), 'native_gate_mocked': False,
            'offset_bounds_checked_by_native_gate': False,
            'download_transport_verified': False,
            'decompression_verified': False, 'native_ui_verified': False}
