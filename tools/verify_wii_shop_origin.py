"""Execute fixed retail-v21 origin/trust predicates on synthetic browser fields.

protocol/hostname/port are already-separated callback arguments, not parsed here
from a URL. current_url is independent synthetic callback output. No browser,
network, credentials, connection startup or original protection patch is used.
The native test-mode override is always OFF and is not a public option.
"""
import hashlib
import struct

from tools.verify_wii_shop_url import SOURCE_SHA

ENTRY = 0x80091150
HOST_PREDICATE = 0x800a6d90
MAX_STRING_BYTES = 1024  # Harness input cap, not the native 256-byte host scan.
MAX_INSTRUCTIONS = 100000
_TEST_MODE = 0x803db5b8
_CALLBACK_POINTER = 0x803db5f4
_FLAGS = 0x803db5f8  # HTTPS, access allowed, trusted page.


def verify_origin_access(source, *, protocol, hostname, port, current_url,
                         callback_present=True):
    """Return flags/counts only after original native checks and guard validation.

    Missing and NULL-returning URL callbacks are distinct fixtures. No input URL
    or hostname is returned. A result does not establish browser canonicalization,
    global/method exposure, commerce authorization or a complete origin policy.
    """
    if not isinstance(source, bytes) or hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Shop v21 executable fingerprint mismatch')
    if (type(port) is not int or not -(1 << 31) <= port < (1 << 31)
            or type(callback_present) is not bool
            or (not callback_present and current_url is not None)):
        raise ValueError('Expected bounded synthetic callback fields')
    for value in (protocol, hostname):
        if not isinstance(value, bytes) or len(value) > MAX_STRING_BYTES or b'\0' in value:
            raise ValueError('Expected bounded synthetic strings without embedded NULs')
    if current_url is not None and (not isinstance(current_url, bytes)
            or len(current_url) > MAX_STRING_BYTES or b'\0' in current_url):
        raise ValueError('Expected bounded synthetic callback URL without embedded NULs')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    stop, callback = 0x817ff000, 0x817ff100
    cpu.mem_write(callback, b'\x4e\x80\x00\x20')  # Synthetic callback return instruction.
    guard = b'!'*32
    strings = ((0x81000100, protocol), (0x81001000, hostname),
               (0x81002000, current_url if current_url is not None else b''))
    for address, value in strings:
        cpu.mem_write(address-32, guard)
        cpu.mem_write(address, value+b'\0'*8)
        cpu.mem_write(address+len(value)+8, guard)
    cpu.mem_write(_TEST_MODE, bytes(4))
    cpu.mem_write(_CALLBACK_POINTER, struct.pack('>I', callback if callback_present else 0))
    cpu.mem_write(_CALLBACK_POINTER-32, guard)
    cpu.mem_write(_FLAGS, b'\xa5'*3)
    cpu.mem_write(_FLAGS+3, guard)
    cpu.mem_write(0x817dc000-32, guard)
    cpu.mem_write(0x817e1000, guard)
    count = callbacks = logs = 0
    visits = set()

    def return_from_stub(value=0):
        cpu.reg_write(UC_PPC_REG_0+3, value)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def instruction(_cpu, address, _size, _data):
        nonlocal count, callbacks, logs
        count += 1
        visits.add(address)
        if address == callback:
            callbacks += 1
            if callbacks > 1:
                raise ValueError('Unexpected repeated synthetic URL callback')
            return_from_stub(0x81002000 if current_url is not None else 0)
            return
        if address == 0x80078610:
            logs += 1
            return_from_stub()
            return
        allowed = ((ENTRY, 0x800912fc), (HOST_PREDICATE, 0x800a6e50),
                   (0x802b5160, 0x802b517c), (0x802becf8, 0x802bee18),
                   (0x802b5920, 0x802b5ac8))
        if not any(begin <= address < end for begin, end in allowed):
            raise ValueError('Unexpected native origin control flow')

    def memory_write(_cpu, _access, address, size, _value, _data):
        if not ((0x817dc000 <= address < address+size <= 0x817e1000)
                or (_FLAGS <= address < address+size <= _FLAGS+3)):
            raise ValueError('Unexpected native origin write')

    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)
    for index, value in {1: 0x817e0000, 2: 0x80369460, 13: 0x803674e0,
                         3: 0x81000100, 4: 0x81001000, 5: port & 0xffffffff}.items():
        cpu.reg_write(UC_PPC_REG_0+index, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(ENTRY, stop, count=MAX_INSTRUCTIONS)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native origin routine did not return within instruction cap')
    native_return = cpu.reg_read(UC_PPC_REG_0+3)
    flags = bytes(cpu.mem_read(_FLAGS, 3))
    if any(flag not in (0, 1) for flag in flags) or native_return != flags[1]:
        raise ValueError('Native origin flags and return differ')
    checks = ((_CALLBACK_POINTER-32, guard), (_FLAGS+3, guard),
              (0x817dc000-32, guard), (0x817e1000, guard), (_TEST_MODE, bytes(4)),
              (_CALLBACK_POINTER, struct.pack('>I', callback if callback_present else 0)))
    for address, expected in checks:
        if bytes(cpu.mem_read(address, len(expected))) != expected:
            raise ValueError('Native origin fixture guard or callback pointer changed')
    for address, value in strings:
        if (bytes(cpu.mem_read(address-32, 32)) != guard
                or bytes(cpu.mem_read(address, len(value)+8)) != value+b'\0'*8
                or bytes(cpu.mem_read(address+len(value)+8, 32)) != guard):
            raise ValueError('Native origin input string or guard changed')
    if callbacks != int(callback_present) or HOST_PREDICATE not in visits:
        raise ValueError('Native origin did not exercise expected callback/check boundaries')
    return {'access_allowed': bool(flags[1]), 'page_https': bool(flags[0]),
            'trusted_page': bool(flags[2]), 'native_return': native_return,
            'current_url_callback_present': callback_present,
            'current_url_callback_calls': callbacks,
            'current_url_callback_returns_null': callback_present and current_url is None,
            'logging_calls_stubbed': logs, 'native_instructions': count,
            'native_instruction_addresses_visited': len(visits),
            'native_hostname_predicate_executed': True,
            'native_strlen_executed': 0x802b5160 in visits,
            'native_strcmp_executed': 0x802becf8 in visits,
            'native_origin_or_string_helpers_stubbed': False,
            'native_test_mode_forced_off': True,
            'input_and_stack_guards_verified': True, 'native_write_ranges_checked': True,
            'browser_fields_are_synthetic_preparsed_values': True,
            'current_url_is_independent_synthetic_callback_output': True,
            'browser_url_parsing_or_canonicalization_verified': False,
            'global_or_method_access_verified': False,
            'browser_network_or_account_invoked': False}
