"""Run the installed v21 URL builder and native formatter on synthetic strings.

No platform calls are mocked and no network or browser is invoked. Original
URL pointers are replaced in emulated RAM before execution.
"""
import hashlib
import struct

SOURCE_SHA = 'aff20704bd4cf9025e34382e185b0936e9ebc6e047a3431f21a445165c9dc898'


def verify(source, mode, suffix, *, base=b'https://shop.example', manual=b'https://shop.example/manual?id='):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Shop v21 executable fingerprint mismatch')
    if type(mode) is not int or not 0 <= mode <= 0xffffffff:
        raise ValueError('Expected synthetic U32 mode')
    if any(not isinstance(value, bytes) or len(value) > 1024 or b'\0' in value
           for value in (base, manual, suffix)):
        raise ValueError('Expected bounded synthetic strings without embedded NULs')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    for pointer, address, value in ((0x8035f4f8, 0x81000000, base), (0x8035f4fc, 0x81001000, manual)):
        cpu.mem_write(address, value+b'\0')
        cpu.mem_write(pointer, struct.pack('>I', address))
    cpu.mem_write(0x81002000, suffix+b'\0')
    cpu.mem_write(0x80360728, struct.pack('>I', mode))
    output = 0x8036bf08
    guard = b'!'*32
    cpu.mem_write(output-32, guard+b'?'*256+guard)
    for register, value in {1: 0x817e0000, 2: 0x80369460, 13: 0x803674e0,
                           3: 0x81002000}.items():
        cpu.reg_write(UC_PPC_REG_0+register, value)
    end = 0x817ff000
    cpu.reg_write(UC_PPC_REG_LR, end)
    cpu.emu_start(0x8002bc10, end, count=5_000_000)
    if cpu.reg_read(UC_PPC_REG_PC) != end:
        raise ValueError('Native URL builder did not return')
    raw = bytes(cpu.mem_read(output, 256))
    expected = (manual if mode in (2, 8) else base)+suffix
    if raw.split(b'\0', 1)[0] != expected[:254] or raw[255] != 0:
        raise ValueError('Native URL composition/truncation differs')
    if int.from_bytes(cpu.mem_read(0x803607d8, 4), 'big') != output:
        raise ValueError('Native URL pointer publication differs')
    if bytes(cpu.mem_read(output-32, 32)) != guard or bytes(cpu.mem_read(output+256, 32)) != guard:
        raise ValueError('Native URL buffer guard changed')
    return {'manual_branch': mode in (2, 8), 'url_bytes': min(len(expected), 254),
            'truncated': len(expected) > 254, 'native_builder_mocked': False,
            'native_formatter_mocked': False, 'buffer_guards_verified': True,
            'startup_request_verified': False, 'browser_or_network_invoked': False}
