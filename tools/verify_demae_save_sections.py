"""Compare synthetic decrypted-buffer framing with native section lookup.

SDK memcpy is mocked. No original save or decrypted personal data is needed.
"""
import hashlib
import struct

from jwc24.demae_save_sections import inspect_sections
from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, data, *, probe_tags=()):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    _, sections = inspect_sections(data)
    if not isinstance(probe_tags, tuple) or len(probe_tags) > 32 or any(
            not isinstance(tag, bytes) or len(tag) != 4 for tag in probe_tags):
        raise ValueError('Expected bounded four-byte probe tags')
    from tools.inspect_demae_references import sections as dol_sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in dol_sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    def hook(cpu, address, size, user):
        if address == 0x817FF000:
            cpu.emu_stop()
            return
        args = [cpu.reg_read(UC_PPC_REG_0+n) for n in (3, 4, 5)]
        cpu.mem_write(args[0], bytes(cpu.mem_read(args[1], args[2])))
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x817FF000, 0x80004338):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    cpu.mem_write(0x80373820-0x7468, struct.pack('>I', 0x80900000))
    cpu.mem_write(0x80904000, data)
    tags = list(dict.fromkeys(section.tag for section in sections))
    missing = next(struct.pack('>I', n) for n in range(len(tags)+1)
                   if struct.pack('>I', n) not in tags)
    for tag in list(dict.fromkeys(tags+list(probe_tags)+[missing])):
        out = 0x80910000
        cpu.mem_write(out, b'!'*12)
        values = {1: 0x817E0000, 2: 0x80374C40, 13: 0x80373820,
                  3: int.from_bytes(tag, 'big'), 4: out, 5: out+4, 6: out+8}
        for register, value in values.items():
            cpu.reg_write(UC_PPC_REG_0+register, value)
        cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
        cpu.emu_start(0x800E3F0C, 0x817FF004, count=100_000)
        if cpu.reg_read(UC_PPC_REG_PC) != 0x817FF000:
            raise ValueError('Native address section lookup did not return')
        found = cpu.reg_read(UC_PPC_REG_0+3)
        expected = next((section for section in sections if section.tag == tag), None)
        if found != int(expected is not None):
            raise ValueError('Native address section presence differs')
        if expected:
            offset, length = struct.unpack('>II', cpu.mem_read(out, 8))
            stop = bytes(cpu.mem_read(out+8, 1))[0]
            if (offset, length, stop) != (expected.offset, expected.byte_length, expected.stop_byte):
                raise ValueError('Native address section metadata differs')
        elif bytes(cpu.mem_read(out, 12)) != b'!'*12:
            raise ValueError('Missing native section changed output arguments')
    return {'sections_verified': len(sections), 'distinct_tag_lookups': len(tags),
            'missing_tag_verified': True, 'native_lookup_mocked': False,
            'personal_fields_decoded': False, 'integrity_verified': False,
            'native_save_acceptance_verified': False}
