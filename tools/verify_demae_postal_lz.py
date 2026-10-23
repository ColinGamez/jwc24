"""Execute the original HCCJ bounded LZ consumer on synthetic fixtures.

No decompression instructions or platform calls are mocked. This is not the
filesystem wrapper, WC24 download transport or a native UI acceptance test.
"""
import hashlib

from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, compressed, expected, *, expected_status=0):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    if not isinstance(compressed, bytes) or not 4 <= len(compressed) <= 0x40000:
        raise ValueError('Expected bounded synthetic compressed bytes')
    if not isinstance(expected, bytes) or len(expected) > 0x40000:
        raise ValueError('Expected bounded synthetic output bytes')
    if type(expected_status) is not int or expected_status not in (0, -1, -2, -3, -4):
        raise ValueError('Invalid expected native LZ status')
    declared = int.from_bytes(compressed[1:4], 'little')
    if declared == 0:
        if len(compressed) < 8:
            raise ValueError('Extended size must be present for bounded emulation')
        declared = int.from_bytes(compressed[4:8], 'little')
    if declared > 0x40000:
        raise ValueError('Declared native output exceeds harness bound')
    if expected_status == 0 and len(expected) != declared:
        raise ValueError('Expected output must match declared size')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    input_address, output, end = 0x81000000, 0x81100020, 0x817ff000
    cpu.mem_write(input_address, compressed)
    guard = b'!'*32
    cpu.mem_write(output-32, guard+bytes(declared)+guard)
    def call(address, *args):
        for register, value in {1: 0x817e0000, **dict(enumerate(args, 3))}.items():
            cpu.reg_write(UC_PPC_REG_0+register, value)
        cpu.reg_write(UC_PPC_REG_LR, end)
        cpu.emu_start(address, end, count=20_000_000)
        if cpu.reg_read(UC_PPC_REG_PC) != end:
            raise ValueError('Native postal LZ routine did not return')
        return cpu.reg_read(UC_PPC_REG_0+3)
    if call(0x80160aa0, input_address) != declared:
        raise ValueError('Native declared size differs')
    status = call(0x80160d80, input_address, len(compressed), output)
    if status != expected_status & 0xffffffff:
        raise ValueError(f'Native LZ status differs: {status:#x}')
    if expected_status == 0 and bytes(cpu.mem_read(output, declared)) != expected:
        raise ValueError('Native LZ output differs')
    if (bytes(cpu.mem_read(output-32, 32)) != guard
            or bytes(cpu.mem_read(output+declared, 32)) != guard):
        raise ValueError('Native LZ output guard changed')
    return {'native_status': expected_status, 'declared_bytes': declared,
            'native_size_reader_mocked': False, 'native_lz_mocked': False,
            'output_guards_verified': True, 'filesystem_wrapper_verified': False,
            'download_transport_verified': False, 'native_ui_verified': False}
