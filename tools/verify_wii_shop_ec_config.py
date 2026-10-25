"""Execute original v21 SOAP parsing on bounded synthetic response/state only.

No browser/network/IOS/account state is available. Returned strings echo only
the caller's synthetic fixture and are not suitable as redacted real captures.
Original instruction/data fingerprints are required; no source/disassembly is
embedded or exported. Heap/logging boundaries are explicit synthetic stubs.
"""
import hashlib
import struct

from tools.verify_wii_shop_url import SOURCE_SHA

FIELDS = ('ContentPrefixURL', 'UncachedContentPrefixURL', 'EcsURL', 'IasURL', 'CasURL')
MAX_RESPONSE = 16384


def verify_ec_config_response(source, response):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Shop v21 executable fingerprint mismatch')
    if not isinstance(response, bytes) or not 0 < len(response) <= MAX_RESPONSE or b'\0' in response:
        raise ValueError('Expected bounded synthetic XML bytes without NUL')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    heap, heap_end, stop = 0x81200000, 0x81600000, 0x817ff000
    allocations, frees, logs, visits, heap_guards = [], [], [], set(), []
    ticks, mutexes = [], []
    env, stack, config_stack = 0x81001000, 0x817e0000, 0x817dc000
    soap = config_stack + 0xc0
    url_setter_calls, field_attempts, common_simple_fields = [], [], []
    phase = 'common'
    namespace_checks = []

    def reg(index):
        return cpu.reg_read(UC_PPC_REG_0 + index)

    def word(address):
        return int.from_bytes(cpu.mem_read(address, 4), 'big')

    def put(address, value):
        cpu.mem_write(address, struct.pack('>I', value & 0xffffffff))

    def allocate(size):
        nonlocal heap
        if not 0 < size <= 1024 * 1024:
            raise ValueError('Native synthetic allocation outside bounds')
        address = heap + 32
        heap += (size + 95) & ~31
        if heap > heap_end:
            raise ValueError('Native synthetic heap exhausted')
        allocations.append(size)
        cpu.mem_write(address - 32, b'!' * 32)
        cpu.mem_write(address + size, b'!' * 32)
        heap_guards.append((address, size))
        return address

    def string(address, value):
        pointer = allocate(len(value) + 1)
        cpu.mem_write(pointer, value + b'\0')
        cpu.mem_write(address, struct.pack('>III', 0x80000000 | len(value), len(value), pointer))

    def read_string(address):
        ranges = ((0x817c0000, 0x817e1000), (env, env + 0x200),
                  (0x81002000, 0x81002100), (0x81200000, heap))
        if not any(begin <= address < address + 12 <= end for begin, end in ranges):
            raise ValueError('Native string object outside synthetic memory')
        if word(address) & 0x80000000:
            size, pointer = word(address + 4), word(address + 8)
            if not any(begin <= pointer < pointer + size + 1 <= begin + length
                       for begin, length in heap_guards):
                raise ValueError('Native string storage outside synthetic allocations')
        else:
            size, pointer = cpu.mem_read(address, 1)[0] & 0x7f, address + 1
            if pointer + size + 1 > address + 12:
                raise ValueError('Native inline string exceeds synthetic object capacity')
        if size > MAX_RESPONSE:
            raise ValueError('Native synthetic string outside bounds')
        return bytes(cpu.mem_read(pointer, size))

    def stub_return(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xffffffff)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def hook(_cpu, address, _size, _data):
        visits.add(address)
        if phase == 'common' and address == 0x8007e470:
            common_simple_fields.append(read_string(reg(4)).decode('ascii'))
        if phase == 'common' and address == 0x8007de98:
            expected = read_string(reg(1) + 0x40)
            if expected != b'xmlns="urn:ecs.wsapi.broadon.com"':
                raise ValueError('Native common parser expected namespace differs')
            namespace_checks.append(bool(reg(30)))
        if phase == 'urls' and address == 0x8007e470:
            field_attempts.append(read_string(reg(4)).decode('ascii'))
        if phase == 'urls' and address in (0x800766d0, 0x80076810):
            url_setter_calls.append(address)
        if address in (0x8007c710, 0x8007c5e0):
            stub_return(allocate(reg(3)))
            return
        if address == 0x80078610:
            logs.append(address)
            stub_return()
            return
        if address == 0x8007c5f0:
            if reg(3) and not 0x81200000 <= reg(3) < heap:
                raise ValueError('Native free outside synthetic heap')
            frees.append(reg(3))
            stub_return()
            return
        if address == 0x80073380:
            ticks.append(address)
            cpu.reg_write(UC_PPC_REG_0 + 4, 123)
            stub_return(0)
            return
        if address in (0x80073090, 0x80073110):
            mutexes.append(address)
            stub_return()
            return
        allowed = ((0x800043c4, 0x80004800),
                   (0x80020410, 0x80020444),
                   (0x80073500, 0x800785c0), (0x8007dd10, 0x8007eb50),
                   (0x80081a00, 0x80082430), (0x802b5000, 0x802b5200),
                   (0x80082770, 0x80082b00),
                   (0x800838a0, 0x80084800),
                   (0x802ba988, 0x802bae80),
                   (0x802c0570, 0x802c11b0),
                   (0x802b5920, 0x802b5ac8), (0x802be000, 0x802bf000),
                   (0x80088bfc, 0x80088d8c))
        if not any(begin <= address < end for begin, end in allowed):
            raise ValueError(f'Unexpected native parser control flow: {address:08x}')

    def memory_write(_cpu, _access, address, size, _value, _data):
        allowed = ((0x817c0000, 0x817e1000), (env, env + 0x200),
                   (0x81002000, 0x81002100), (0x81200000, heap_end),
                   (0x803613c8, 0x803613cc))  # native strto* errno, synthetic RAM
        if not any(begin <= address < address + size <= end for begin, end in allowed):
            raise ValueError(f'Unexpected native parser write: {address:08x}')

    cpu.hook_add(UC_HOOK_CODE, hook)
    object_guards = ((soap, 0xd0), (env, 0x200), (0x81002000, 0x100))
    for address, size in object_guards:
        cpu.mem_write(address - 16, b'!' * 16)
        cpu.mem_write(address + size, b'!' * 16)
    for index, value in {1: stack, 2: 0x80369460, 13: 0x803674e0}.items():
        cpu.reg_write(UC_PPC_REG_0 + index, value)
    put(soap, env)
    put(env + 4, 0x81002000)
    string(soap + 0x28, response)
    string(soap + 0xb0, b'GetECConfigResponse')
    service = allocate(4)
    cpu.mem_write(service, b'ecs\0')
    put(soap + 0x88, service)
    put(soap + 0x90, 0xffffffff)
    put(soap + 0x94, 0)
    cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)
    cpu.reg_write(UC_PPC_REG_0 + 3, soap)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x8007dd20, stop, count=2000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native SOAP common parser did not return')
    common_status = word(soap + 0x44)
    urls, extracted = {}, {}
    if common_status == 0:
        phase = 'urls'
        for index, value in {1: config_stack, 30: env, 31: 0x80322020}.items():
            cpu.reg_write(UC_PPC_REG_0 + index, value)
        # Stop before destruction and the subsequent account/device-status flow.
        cpu.emu_start(0x80088bfc, 0x80088d8c, count=2000000)
        if cpu.reg_read(UC_PPC_REG_PC) != 0x80088d8c:
            raise ValueError('Native GetECConfig extraction did not reach bounded exit')
        for name, offset in zip(FIELDS, (0x20, 0x2c, 0x38, 0x44, 0x50)):
            extracted[name] = read_string(config_stack + offset).decode('utf-8')
        if url_setter_calls:
            for name, offset in zip(FIELDS, (0x34, 0x40, 0x10, 0x1c, 0x28)):
                urls[name] = read_string(env + offset).decode('utf-8')
    status = word(soap + 0x44)
    for address, size in object_guards:
        if bytes(cpu.mem_read(address - 16, 16)) != b'!' * 16 or bytes(cpu.mem_read(address + size, 16)) != b'!' * 16:
            raise ValueError('Native synthetic object guard changed')
    for address, size in heap_guards:
        if bytes(cpu.mem_read(address - 32, 32)) != b'!' * 32 or bytes(cpu.mem_read(address + size, 32)) != b'!' * 32:
            raise ValueError('Native synthetic heap guard changed')
    return {'status': status - 0x100000000 if status & 0x80000000 else status,
            'common_status': common_status - 0x100000000 if common_status & 0x80000000 else common_status,
            'timestamp': read_string(soap + 0x50).decode('utf-8'),
            'error_code': read_string(soap + 0x5c).decode('utf-8'),
            'error_message': read_string(soap + 0x68).decode('utf-8'),
            'urls': urls, 'extracted_urls': extracted,
            'field_attempts': field_attempts, 'native_url_setter_calls': len(url_setter_calls),
            'common_simple_fields': common_simple_fields,
            'namespace_comparison_equal': namespace_checks[0] if namespace_checks else None,
            'native_instruction_addresses_visited': len(visits),
            'synthetic_allocation_count': len(allocations), 'logging_calls_stubbed': len(logs),
            'synthetic_free_calls_stubbed': len(frees),
            'synthetic_tick_calls_stubbed': len(ticks), 'mutex_calls_stubbed': len(mutexes),
            'native_error_setter_executed': 0x800769a0 in visits,
            'server_timestamp': str((word(env + 0x58) << 32) | word(env + 0x5c)),
            'reported_error_record_code': word(0x81002000 + 0x38),
            'synthetic_heap_bytes_used': heap - 0x81200000,
            'object_and_heap_guards_verified': True, 'native_write_ranges_checked': True,
            'native_url_setters_stubbed': False, 'response_bytes': len(response),
            'native_xml_entry_points_executed': [f'0x{address:08x}' for address in (
                0x8007dd20, 0x8007e100, 0x8007e420, 0x8007e470, 0x8007e740, 0x80083ab0)
                if address in visits],
            'native_xml_lookup_helpers_stubbed': False, 'browser_or_network_invoked': False,
            'full_connection_or_account_verified': False, 'request_builder_executed': False}
