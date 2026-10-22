"""Compare native HCCJ cipher routines with AES-CBC using synthetic inputs.

No device key derivation, save decoding, authentication or rendering is tested.
"""
import hashlib

from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, key, iv, plain):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    if not isinstance(key, bytes) or len(key) not in (16, 24, 32):
        raise ValueError('Expected synthetic AES key bytes')
    if not isinstance(iv, bytes) or len(iv) != 16:
        raise ValueError('Expected synthetic AES IV bytes')
    if not isinstance(plain, bytes) or not 16 <= len(plain) <= 16384 or len(plain) % 16:
        raise ValueError('Expected bounded complete synthetic blocks')
    from Crypto.Cipher import AES
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def hook(cpu, address, size, data):
        if address == 0x817FF000:
            cpu.emu_stop()
            return
        if address == 0x80004338:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
        # Debug reporting is suppressed; no SDK output or input bytes escape.
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x817FF000, 0x80004338, 0x8013B5D4):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    def call(address, *args):
        for n, value in {1: 0x817E0000, 2: 0x80374C40, 13: 0x80373820,
                         **dict(enumerate(args, 3))}.items():
            cpu.reg_write(UC_PPC_REG_0+n, value)
        cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
        cpu.emu_start(address, 0x817FF004, count=10_000_000)
        if cpu.reg_read(UC_PPC_REG_PC) != 0x817FF000:
            raise ValueError('Native address cipher did not return')
        return reg(3)
    context, key_address, iv_address = 0x80900000, 0x80901000, 0x80902000
    input_address, output_address = 0x81000000, 0x81100000
    cpu.mem_write(key_address, key)
    cpu.mem_write(iv_address, iv)
    def initialize():
        cpu.mem_write(context, bytes(0x108))
        if call(0x800879D0, context, key_address, len(key), iv_address) != 1:
            raise ValueError('Native address cipher initialization failed')
    expected = AES.new(key, AES.MODE_CBC, iv).encrypt(plain)
    initialize()
    cpu.mem_write(input_address, plain)
    if call(0x800879DC, context, output_address, input_address, len(plain)) != 1:
        raise ValueError('Native address cipher encryption failed')
    if bytes(cpu.mem_read(output_address, len(plain))) != expected:
        raise ValueError('Native encryption differs from independent AES-CBC')
    initialize()
    cpu.mem_write(input_address, expected)
    if call(0x80087A94, context, output_address, input_address, len(plain)) != 1:
        raise ValueError('Native address cipher decryption failed')
    if bytes(cpu.mem_read(output_address, len(plain))) != plain:
        raise ValueError('Native decryption differs from independent AES-CBC')
    initialize()
    sentinel = b'!'*32
    cpu.mem_write(output_address, sentinel)
    if call(0x80087A94, context, output_address, input_address, 17) != 0:
        raise ValueError('Native cipher accepted an incomplete block')
    if bytes(cpu.mem_read(output_address, len(sentinel))) != sentinel:
        raise ValueError('Native incomplete-block rejection changed output')
    return {'key_bits': len(key)*8, 'blocks_verified': len(plain)//16,
            'cipher': 'AES-CBC', 'native_cipher_mocked': False,
            'libc_and_debug_output_mocked': True,
            'incomplete_block_rejected_without_output_write': True,
            'key_derivation_verified': False, 'save_integrity_verified': False,
            'native_save_acceptance_verified': False}
