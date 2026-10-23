"""Run HCCJ's decrypt/header-strip callback with synthetic file I/O.

The original AES and header gate execute; filesystem, heap and lock services
are mocked. No original keys, files, network or NAND services are used.
"""
import hashlib
import struct

from tools.inspect_demae_address_save import SOURCE_SHA


def verify(source, key, iv, ciphertext, *, capacity=0x40000, fail_allocation=0):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Address helper executable fingerprint mismatch')
    if not isinstance(key, bytes) or len(key) != 32 or not isinstance(iv, bytes) or len(iv) != 16:
        raise ValueError('Expected synthetic AES-256 key and IV')
    if not isinstance(ciphertext, bytes) or len(ciphertext) > 0x40000:
        raise ValueError('Expected bounded synthetic ciphertext')
    if (type(capacity) is not int or not 0 <= capacity <= 0x40000
            or type(fail_allocation) is not int or fail_allocation not in (0, 1, 2)):
        raise ValueError('Invalid synthetic callback options')
    from Crypto.Cipher import AES
    expected_status, expected_body = 0, None
    if len(ciphertext) < 16 or len(ciphertext) % 16 or len(ciphertext) > capacity:
        expected_status = 0x17
    elif fail_allocation:
        expected_status = 0x18
    else:
        plain = AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)
        if plain[:4] != b'zpcd':
            expected_status = 0x1b
        else:
            offset = plain[4]
            if not 5 <= offset <= len(plain):
                raise ValueError('Unsafe synthetic offset excluded from callback harness')
            expected_body = plain[offset:]
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    state = {'allocations': [], 'freed': [], 'writes': [], 'closed': [], 'unmounted': 0,
             'lock_acquired': 0, 'lock_released': 0}
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def word(address, value):
        cpu.mem_write(address, struct.pack('>I', value))
    def hook(cpu, address, size, user):
        result = 0
        if address == 0x80004338:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
            result = reg(3)
        elif address == 0x800a0ad0:  # synthetic source/destination handles
            result = 1 if reg(3) == 0x80903000 else 2
        elif address == 0x800a0f6c:
            result = len(ciphertext)
        elif address == 0x8016014c:
            number = len(state['allocations'])+1
            result = 0 if number == fail_allocation else 0x81000000+(number-1)*0x80000
            state['allocations'].append(result)
        elif address == 0x800a0ca4:
            if reg(5) != len(ciphertext):
                raise ValueError('Unexpected synthetic read size')
            if ciphertext:
                cpu.mem_write(reg(4), ciphertext)
            word(reg(6), len(ciphertext))
        elif address == 0x800a0bac:
            state['closed'].append(reg(3))
        elif address == 0x80086f9c:
            state['lock_acquired'] += 1
            result = 1
        elif address == 0x8008702c:
            state['lock_released'] += 1
        elif address == 0x800a0d40:
            if reg(5) > len(ciphertext):
                raise ValueError('Native stripped length exceeds synthetic input')
            state['writes'].append(bytes(cpu.mem_read(reg(4), reg(5))))
        elif address == 0x800a0918:
            state['unmounted'] += 1
        elif address == 0x8015fa1c:
            result = 0x80905000  # synthetic owning heap
        elif address == 0x801601fc:
            state['freed'].append(reg(4))
        cpu.reg_write(UC_PPC_REG_0+3, result)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    mocked = (0x80004338, 0x8013b5d4, 0x800a0600, 0x800a0ad0, 0x800a0f6c,
              0x8016014c, 0x800a0ca4, 0x800a0bac, 0x80086f9c, 0x8008702c,
              0x800a0d40, 0x800a0918, 0x8015fa1c, 0x801601fc)
    for address in mocked:
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    cpu.mem_write(0x80901000, key)
    cpu.mem_write(0x80902000, iv)
    stack, end = 0x817e0000, 0x817ff000
    word(stack+8, 0x8002e954)
    word(stack+12, 0)  # do not request source deletion
    for register, value in {1: stack, 2: 0x80374c40, 13: 0x80373820,
                           3: 0x80904000, 4: 0x80903000, 5: 0x80903100,
                           6: capacity, 7: 0x80901000, 8: 32,
                           9: 0x80902000, 10: 0x80905000}.items():
        cpu.reg_write(UC_PPC_REG_0+register, value)
    cpu.reg_write(UC_PPC_REG_LR, end)
    cpu.emu_start(0x8002d370, end, count=20_000_000)
    if cpu.reg_read(UC_PPC_REG_PC) != end:
        raise ValueError('Native postal callback did not return')
    status = reg(3)
    if status != expected_status or state['writes'] != ([] if expected_body is None else [expected_body]):
        raise ValueError('Native callback status or stripped body differs')
    if sorted(state['freed']) != sorted(address for address in state['allocations'] if address):
        raise ValueError('Native callback did not release synthetic allocations')
    if state['lock_acquired'] != state['lock_released'] or state['unmounted'] != 1:
        raise ValueError('Native callback lock/mount cleanup differs')
    if state['closed'] != ([1, 2] if expected_status == 0 else [1]):
        raise ValueError('Native callback file handle cleanup differs')
    return {'native_status': status, 'stripped_bytes': len(expected_body) if expected_body is not None else 0,
            'native_aes_mocked': False, 'native_header_gate_mocked': False,
            'filesystem_heap_locks_mocked': True, 'cleanup_verified': True,
            'decompression_verified': False, 'download_transport_verified': False}
