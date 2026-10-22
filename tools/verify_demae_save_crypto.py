"""Compare native HCCJ cipher routines with AES-CBC using synthetic inputs.

No real device material, save decoding, authentication or rendering is tested.
"""
import hashlib
import struct

from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, key, iv, plain, *, synthetic_identifier=None):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    if not isinstance(key, bytes) or len(key) not in (16, 24, 32):
        raise ValueError('Expected synthetic AES key bytes')
    if not isinstance(iv, bytes) or len(iv) != 16:
        raise ValueError('Expected synthetic AES IV bytes')
    if not isinstance(plain, bytes) or not 16 <= len(plain) <= 16384 or len(plain) % 16:
        raise ValueError('Expected bounded complete synthetic blocks')
    if synthetic_identifier is not None and (type(synthetic_identifier) is not int
            or not 0 <= synthetic_identifier <= 0xFFFFFFFF or len(key) != 32):
        raise ValueError('Expected a synthetic U32 identifier and 32-byte template')
    from Crypto.Cipher import AES
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    query_state = {'status': 0, 'calls': 0}
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def hook(cpu, address, size, data):
        if address == 0x817FF000:
            cpu.emu_stop()
            return
        if address == 0x80004338:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
        elif address == 0x80169674:
            query_state['calls'] += 1
            pointer, length = struct.unpack('>II', cpu.mem_read(reg(7), 8))
            if (reg(4), reg(5), reg(6), length) != (7, 0, 1, 4):
                raise ValueError('Native identifier IPC request shape differs')
            if query_state['status'] == 0:
                cpu.mem_write(pointer, synthetic_identifier.to_bytes(4, 'big'))
            cpu.reg_write(UC_PPC_REG_0+3, query_state['status'] & 0xFFFFFFFF)
        # Debug reporting is suppressed; no SDK output or input bytes escape.
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    for address in (0x817FF000, 0x80004338, 0x8013B5D4, 0x80169674):
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
    if synthetic_identifier is not None:
        # Execute the real platform query wrapper with only IOS IPC mocked.
        identifier_address, descriptor_address = 0x80903000, 0x80373820-0x7758
        cpu.mem_write(descriptor_address, struct.pack('>I', 3))
        if call(0x80167F68, identifier_address) != 0:
            raise ValueError('Native synthetic identifier query failed')
        fetched_identifier = int.from_bytes(cpu.mem_read(identifier_address, 4), 'big')
        if fetched_identifier != synthetic_identifier:
            raise ValueError('Native identifier query copied the wrong value')
        query_state['status'] = -9
        cpu.mem_write(identifier_address, b'!!!!')
        if call(0x80167F68, identifier_address) != (-9 & 0xFFFFFFFF):
            raise ValueError('Native identifier query did not propagate IPC error')
        if bytes(cpu.mem_read(identifier_address, 4)) != b'!!!!':
            raise ValueError('Failed identifier query changed caller output')
        calls_before = query_state['calls']
        cpu.mem_write(descriptor_address, struct.pack('>I', 0xFFFFFFFF))
        if call(0x80167F68, identifier_address) == 0:
            raise ValueError('Native identifier query accepted invalid descriptor')
        cpu.mem_write(descriptor_address, struct.pack('>I', 3))
        if call(0x80167F68, 0) == 0 or query_state['calls'] != calls_before:
            raise ValueError('Native identifier validation reached IPC unexpectedly')
        # Replace original template material in emulated RAM before executing
        # the native constructor. Never read or report its original constants.
        cpu.mem_write(0x80373820-0x7ABC, key)
        cpu.mem_write(0x801D1674, iv)
        cpu.mem_write(key_address, b'!'*48)
        cpu.mem_write(iv_address, b'!'*32)
        call(0x800E431C, key_address, iv_address, fetched_identifier)
        identifier_bytes = synthetic_identifier.to_bytes(4, 'big')
        expected_key = bytearray(key)
        for index, value in enumerate(identifier_bytes):
            expected_key[index*8+7] = value
        expected_iv = iv[:12]+identifier_bytes
        if bytes(cpu.mem_read(key_address, 32)) != expected_key:
            raise ValueError('Native synthetic key construction differs')
        if bytes(cpu.mem_read(iv_address, 16)) != expected_iv:
            raise ValueError('Native synthetic IV construction differs')
        if bytes(cpu.mem_read(key_address+32, 16)) != b'!'*16 or bytes(cpu.mem_read(iv_address+16, 16)) != b'!'*16:
            raise ValueError('Native constructor overwrote output bounds')
        key, iv = bytes(expected_key), expected_iv
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
            'synthetic_identifier_construction_verified': synthetic_identifier is not None,
            'platform_query_with_mocked_ipc_verified': synthetic_identifier is not None,
            'original_templates_replaced': synthetic_identifier is not None,
            'key_derivation_verified': False, 'save_integrity_verified': False,
            'native_save_acceptance_verified': False}
