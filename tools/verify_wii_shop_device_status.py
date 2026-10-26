"""Run retail v21 ECS CheckDeviceStatus using synthetic transport and identity only.

The original virtual dispatch, operation, SOAP construction, XML parser,
balance/sync reader and sync decision execute. The transport boundary supplies
caller-provided synthetic bytes; no HTTP, credentials, browser, NAND, signing
or account operation is available. Config-save and shop-log requests are counted
at stubbed boundaries without performing their side effects.
Returned values echo synthetic fixtures and must never log real service data.
"""
from dataclasses import fields
import hashlib
import struct

from tools.verify_wii_shop_ec_config_request import SyntheticRequestEnvironment
from tools.verify_wii_shop_url import SOURCE_SHA


def verify_device_status(source, response, *, state, environment=None,
                         transport_status=0, save_status=0,
                         worker_dispatch='before_registration'):
    if (not isinstance(source, bytes) or not 0 < len(source) <= 4*1024*1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Expected fingerprinted original v21 executable')
    if (not isinstance(response, bytes) or not 0 < len(response) <= 16384 or b'\0' in response
            or type(transport_status) is not int or not -(1 << 31) <= transport_status <= 0
            or type(save_status) is not int or not -(1 << 31) <= save_status <= 0):
        raise ValueError('Expected bounded synthetic status/transport fixture')
    from jwc24.wii_shop_device_status import validate_sync_state
    validate_sync_state(state)
    dispatches = {'before_registration': (0x80088df0, 0x80088e08),
                  'after_registration': (0x80088eb8, 0x80088ed0)}
    if not isinstance(worker_dispatch, str) or worker_dispatch not in dispatches:
        raise ValueError('Expected a reviewed synthetic worker-dispatch boundary')
    environment = SyntheticRequestEnvironment() if environment is None else environment
    if type(environment) is not SyntheticRequestEnvironment:
        raise ValueError('Expected explicitly synthetic request environment')
    try:
        invalid = any(not isinstance(v := getattr(environment, f.name), str)
                      or len(v) > 96 or len(v.encode('utf-8')) > 96 or '\0' in v
                      for f in fields(environment) if f.name != 'key_pair_confirmed')
    except UnicodeError:
        raise ValueError('Expected bounded synthetic UTF-8 request strings') from None
    if invalid or type(environment.key_pair_confirmed) is not bool:
        raise ValueError('Expected bounded synthetic request strings and flag')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    env, wrapper, current = 0x81001000, 0x81000000, 0x81002000
    stack = 0x817df000
    entry, stop = dispatches[worker_dispatch]
    soap = stack-0x140
    heap, heap_end = 0x81200000, 0x81600000
    allocations, visits, stubs = [], set(), {}
    captured = {}
    response_reader_executed = False

    def reg(i):
        return cpu.reg_read(UC_PPC_REG_0+i)

    def put(address, value):
        cpu.mem_write(address, struct.pack('>I', value & 0xffffffff))

    def word(address):
        return int.from_bytes(cpu.mem_read(address, 4), 'big')

    def allocate(size):
        nonlocal heap
        if not 0 < size <= 1024*1024:
            raise ValueError('Synthetic native allocation outside bound')
        address = heap+32
        heap += (size+95) & ~31
        if heap > heap_end:
            raise ValueError('Synthetic native heap exhausted')
        cpu.mem_write(address-32, b'!'*32)
        cpu.mem_write(address+size, b'!'*32)
        allocations.append((address, size))
        return address

    def cvalue(value):
        address = allocate(len(value)+1)
        cpu.mem_write(address, value+b'\0')
        return address

    def string(address, value):
        pointer = cvalue(value)
        cpu.mem_write(address, struct.pack('>III', 0x80000000 | len(value), len(value), pointer))

    def read_string(address):
        ranges = ((env, env+0x400), (current, current+0x100),
                  (stack-0x4000, stack+0x100), (0x81200000, heap))
        if not any(b <= address < address+12 <= e for b, e in ranges):
            raise ValueError('Native string object outside synthetic memory')
        if word(address) & 0x80000000:
            size, pointer = word(address+4), word(address+8)
            if not any(b <= pointer < pointer+size+1 <= b+n for b, n in allocations):
                raise ValueError('Native string storage outside synthetic allocation')
        else:
            size, pointer = cpu.mem_read(address, 1)[0] & 0x7f, address+1
            if pointer+size+1 > address+12:
                raise ValueError('Native inline string exceeds object')
        if size > 16384:
            raise ValueError('Native string exceeds synthetic output bound')
        return bytes(cpu.mem_read(pointer, size))

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0+3, value & 0xffffffff)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def instruction(_cpu, address, _size, _data):
        nonlocal response_reader_executed
        visits.add(address)
        if address == 0x800870d0:
            response_reader_executed = True
        if address in (0x8007c5e0, 0x8007c710):
            stubs[address] = stubs.get(address, 0)+1
            ret(allocate(reg(3)))
            return
        if address == 0x8007c5f0:
            if reg(3) and not any(b <= reg(3) < b+n for b, n in allocations):
                raise ValueError('Native free outside synthetic allocation')
            stubs[address] = stubs.get(address, 0)+1
            ret()
            return
        if address in (0x80075270, 0x800a60f0, 0x800a6170):
            stubs[address] = stubs.get(address, 0)+1
            ret(save_status if address == 0x80075270 else 0)
            return
        if address in (0x80078610, 0x80074340, 0x80074310, 0x80073090, 0x80073110):
            stubs[address] = stubs.get(address, 0)+1
            ret()
            return
        if address == 0x80073380:
            stubs[address] = stubs.get(address, 0)+1
            cpu.reg_write(UC_PPC_REG_0+4, 123)
            ret()
            return
        if address == 0x800a74a0:
            if captured or reg(3) != soap or read_string(reg(4)) != b'https://synthetic.invalid/ecs':
                raise ValueError('Unexpected synthetic ECS transport handoff')
            begin, count, capacity = word(soap+4), word(soap+8), word(soap+12)
            if (not 0 < count <= capacity <= 16 or not any(
                    b <= begin < begin+24*count <= b+n for b, n in allocations)):
                raise ValueError('Unexpected native header vector bounds')
            headers = [(read_string(a), read_string(a+12)) for a in range(begin, begin+24*count, 24)]
            captured.update(request_bytes=read_string(soap+0x1c), headers=headers)
            string(soap+0x28, response)
            ret(transport_status)
            return
        allowed = ((0x800043c4, 0x80004800), (0x80020410, 0x80020444),
                   (0x80073500, 0x800785c0), (0x8007ad80, 0x8007ade4),
                   (0x8007b580, 0x8007c5e0),
                   (0x8007c950, 0x8007ebcc), (0x80081850, 0x80084800),
                   (0x80086be0, 0x80087410), (0x802b5000, 0x802b5244),
                   (0x80088df0, 0x80088e08), (0x80088eb8, 0x80088ed0),
                   (0x802b5920, 0x802b5d00), (0x802ba988, 0x802bf000),
                   (0x802c0570, 0x802c11b0))
        if not any(b <= address < e for b, e in allowed):
            raise ValueError(f'Unexpected native ECS control flow: {address:08x}')

    def write(_cpu, _access, address, size, _value, _data):
        ranges = ((env, env+0x400), (current, current+0x100), (wrapper, wrapper+0xe0),
                  (stack-0x4000, stack+0x100), (0x81200000, heap_end),
                  (0x803d3100, 0x803d3180), (0x803613c8, 0x803613cc))
        if not any(b <= address < address+size <= e for b, e in ranges):
            raise ValueError(f'Unexpected native ECS write: {address:08x}')

    for name, offset in (('device_id', 0x1b0), ('serial_no', 0x230), ('account_id', 0xc0),
                         ('token', 0xcc), ('strong_token', 0xd8), ('weak_token', 0xf0),
                         ('application_id', 0x178), ('tin', 0x184), ('region', 0x1d0),
                         ('country', 0x120), ('language', 0x144), ('postal_code', 0x260)):
        string(env+offset, getattr(environment, name).encode('utf-8'))
    string(env+0x10, b'https://synthetic.invalid/ecs')
    cpu.mem_write(env+0x1a8, bytes([environment.key_pair_confirmed]))
    put(wrapper, env)
    # Original worker loads this object, then its original run vtable entry.
    put(0x803d3598, wrapper)
    put(wrapper+0xc0, 0x80321340)
    put(env+4, current)
    put(env+0x4c, state.points_balance)
    for offset, name in ((0x50, 'points_cached'), (0x170, 'need_ticket_sync'),
                         (0x171, 'import_all'), (0x172, 'checked'), (0x173, 'times_match'),
                         (0x25a, 'ecdk')):
        cpu.mem_write(env+offset, bytes([getattr(state, name)]))
    for offset, name in ((0x150, 'force_sync_time'), (0x158, 'ext_ticket_time'), (0x160, 'sync_time')):
        cpu.mem_write(env+offset, struct.pack('>q', getattr(state, name)))
    for offset in (0xc8, 0xd0, 0xd8):
        cpu.mem_write(wrapper+offset, struct.pack('>q', -777))
    put(0x80322654, cvalue(b'synthetic-prefix'))
    guards = ((env, 0x400), (current, 0x100), (wrapper, 0xe0), (stack-0x4000, 0x4100))
    for address, size in guards:
        cpu.mem_write(address-16, b'!'*16)
        cpu.mem_write(address+size, b'!'*16)
    for i, value in {1: stack, 2: 0x80369460, 13: 0x803674e0, 3: wrapper}.items():
        cpu.reg_write(UC_PPC_REG_0+i, value)
    cpu.reg_write(UC_PPC_REG_MSR, cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.emu_start(entry, stop, count=3000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop or not captured:
        raise ValueError('Native ECS operation did not finish within instruction bound')
    for address, size in (*guards, *allocations):
        padding = 32 if (address, size) in allocations else 16
        if (bytes(cpu.mem_read(address-padding, padding)) != b'!'*padding
                or bytes(cpu.mem_read(address+size, padding)) != b'!'*padding):
            raise ValueError('Synthetic ECS object or allocation guard changed')
    status = reg(3)
    return {'status': status-0x100000000 if status & 0x80000000 else status,
            'request_bytes': captured['request_bytes'], 'headers': captured['headers'],
            'points_balance': struct.unpack('>i', bytes(cpu.mem_read(env+0x4c, 4)))[0],
            'points_cached': bool(cpu.mem_read(env+0x50, 1)[0]),
            'need_ticket_sync': bool(cpu.mem_read(env+0x170, 1)[0]),
            'import_all': bool(cpu.mem_read(env+0x171, 1)[0]),
            'checked': bool(cpu.mem_read(env+0x172, 1)[0]),
            'times_match': bool(cpu.mem_read(env+0x173, 1)[0]),
            'local_sync_times': [struct.unpack('>q', bytes(cpu.mem_read(env+o, 8)))[0]
                                 for o in (0x150, 0x158, 0x160)],
            'response_sync_times': [struct.unpack('>q', bytes(cpu.mem_read(wrapper+o, 8)))[0]
                                    for o in (0xc8, 0xd0, 0xd8)],
            'save_config_calls': stubs.get(0x80075270, 0),
            'shop_log_calls': stubs.get(0x800a60f0, 0),
            'clear_sync_needed_calls': stubs.get(0x800a6170, 0),
            'native_sync_decision_executed': 0x80086c14 in visits,
            'native_worker_virtual_dispatch_executed': entry in visits,
            'complete_connection_worker_executed': False,
            'connected_flag': bool(cpu.mem_read(env+0x174, 1)[0]),
            'persistence_or_shop_log_executed': False,
            'native_request_builder_executed': True,
            'native_common_response_parser_executed': 0x8007dd20 in visits,
            'native_response_reader_executed': response_reader_executed,
            'native_xml_helpers_stubbed': False,
            'native_numeric_converters_stubbed': False,
            'native_instruction_addresses_visited': len(visits),
            'object_heap_stack_and_write_bounds_verified': True,
            'stub_call_counts': {f'0x{k:08x}': v for k, v in stubs.items()},
            'transport_executed': False, 'account_or_device_authorized': False}
