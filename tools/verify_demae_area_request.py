"""Execute the native area wrapper and URL builder with mocked libc/HTTP calls.

No emulator, saves, network requests or personal data are used.
"""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.inspect_demae_references import sections


def verify(source, code, *, logo=False, expected_sha256='da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830'):
    if hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError('Native request verifier source fingerprint mismatch')
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def string(address):
        return bytes(cpu.mem_read(address, 4096)).split(b'\0', 1)[0]
    cpu.reg_write(UC_PPC_REG_0+1, 0x817F0000)
    cpu.reg_write(UC_PPC_REG_0+2, 0x8047A440)
    cpu.reg_write(UC_PPC_REG_0+13, 0x80478660)
    cpu.reg_write(UC_PPC_REG_0+3, 0x81600000)
    cpu.reg_write(UC_PPC_REG_0+4, 0x81610000)
    cpu.mem_write(0x81610000, code.encode('ascii')+b'\0')
    cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
    captured = []
    def hook(cpu, address, size, data):
        if address == 0x80004104:
            cpu.mem_write(reg(3), bytes([reg(4) & 255])*reg(5))
        elif address == 0x80004000:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
        elif address == 0x8010216C:
            destination = reg(3)
            cpu.mem_write(destination, string(destination)+string(reg(4))+b'\0')
        elif address == 0x8019C700:
            pass
        elif address == 0x8002CD60:
            captured.append(string(reg(4)).decode('ascii'))
            cpu.reg_write(UC_PPC_REG_0+3, 1)
        elif address == 0x817FF000:
            cpu.emu_stop()
            return
        else:
            return
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.emu_start(0x8002C59C if logo else 0x800F9058, 0x817FF004, count=100000)
    if len(captured) != 1:
        raise ValueError('Native area wrapper did not submit exactly one URL')
    return captured[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    source = args.source.read_bytes()
    for code in ('0', 'TEST-JP-10', 'M10202', 'TEST-M-10202'):
        print(code, verify(source, code))
