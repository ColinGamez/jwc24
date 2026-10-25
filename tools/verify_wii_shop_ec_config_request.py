"""Execute pinned v21 request construction using synthetic identity strings only.

The original constructor/start/add/end run; transport stops at getWsResponse.
Returned wire/state echo synthetic inputs and are not a real-capture log API.
"""
from dataclasses import dataclass, field, fields
import hashlib
import struct

from tools.verify_wii_shop_url import SOURCE_SHA


@dataclass(frozen=True)
class SyntheticRequestEnvironment:
    device_id: str = field(default='synthetic-device', repr=False)
    serial_no: str = field(default='synthetic-serial', repr=False)
    region: str = 'SYN'
    country: str = 'ZZ'
    language: str = 'zz'
    account_id: str = field(default='', repr=False)
    token: str = field(default='', repr=False)
    strong_token: str = field(default='', repr=False)
    weak_token: str = field(default='', repr=False)
    application_id: str = field(default='', repr=False)
    tin: str = field(default='', repr=False)
    postal_code: str = field(default='', repr=False)
    key_pair_confirmed: bool = False


def verify_ec_config_request(source, *, environment=None, product_version='synthetic-product-version'):
    if not isinstance(source, bytes) or not 0 < len(source) <= 4 * 1024 * 1024:
        raise ValueError('Expected bounded original v21 executable bytes')
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Shop v21 executable fingerprint mismatch')
    environment = SyntheticRequestEnvironment() if environment is None else environment
    if type(environment) is not SyntheticRequestEnvironment:
        raise ValueError('Expected explicitly synthetic request environment')
    values = [getattr(environment, f.name) for f in fields(environment) if f.name != 'key_pair_confirmed']
    values.append(product_version)
    try:
        invalid_strings = any(not isinstance(v, str) or len(v) > 96
                              or len(v.encode('utf-8')) > 96 or '\0' in v for v in values)
    except UnicodeError:
        raise ValueError('Expected valid synthetic UTF-8 strings') from None
    if type(environment.key_pair_confirmed) is not bool or invalid_strings:
        raise ValueError('Expected bounded synthetic request strings/flag')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    env, wrapper, stack, stop = 0x81001000, 0x81000000, 0x817dc000, 0x817ff000
    soap = stack + 0xc0
    heap, heap_end = 0x81200000, 0x81600000
    allocations, visits, stubs = [], set(), {}
    soap_guard_set = False
    handoff = None
    constructor_version = None

    def reg(i):
        return cpu.reg_read(UC_PPC_REG_0 + i)

    def put(a, v):
        cpu.mem_write(a, struct.pack('>I', v & 0xffffffff))

    def word(a):
        return int.from_bytes(cpu.mem_read(a, 4), 'big')

    def alloc(n):
        nonlocal heap
        if not 0 < n <= 1024 * 1024:
            raise ValueError('Synthetic native allocation outside bounds')
        a = heap + 32
        heap += (n + 95) & ~31
        if heap > heap_end:
            raise ValueError('Synthetic native heap exhausted')
        cpu.mem_write(a - 32, b'!' * 32)
        cpu.mem_write(a + n, b'!' * 32)
        allocations.append((a, n))
        return a

    def cvalue(value):
        raw = value.encode('utf-8')
        a = alloc(len(raw) + 1)
        cpu.mem_write(a, raw + b'\0')
        return a

    def string(a, value):
        raw = value.encode('utf-8')
        p = cvalue(value)
        cpu.mem_write(a, struct.pack('>III', 0x80000000 | len(raw), len(raw), p))

    def read_string(a):
        ranges = ((env, env + 0x400), (stack - 0x2000, stack + 0x200), (0x81200000, heap))
        if not any(b <= a < a + 12 <= e for b, e in ranges):
            raise ValueError('String object outside synthetic memory')
        if word(a) & 0x80000000:
            n, p = word(a + 4), word(a + 8)
            if not any(b <= p < p + n + 1 <= b + z for b, z in allocations):
                raise ValueError('String storage outside synthetic allocations')
        else:
            n, p = cpu.mem_read(a, 1)[0] & 0x7f, a + 1
            if p + n + 1 > a + 12:
                raise ValueError('Inline native string exceeds object capacity')
        if n > 16384:
            raise ValueError('Native request output exceeds bounds')
        return bytes(cpu.mem_read(p, n))

    def ret(v=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, v & 0xffffffff)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def hook(_cpu, address, _size, _data):
        nonlocal soap_guard_set, handoff, constructor_version
        visits.add(address)
        if address == 0x80088bcc:
            # Earlier constructor temporaries legitimately occupy the preceding bytes.
            cpu.mem_write(soap - 16, b'!' * 16)
            cpu.mem_write(soap + 0xd0, b'!' * 16)
            soap_guard_set = True
            # This pointer was just written by the executed original constructor.
            pointer = word(soap + 0x8c)
            if pointer != 0x8031f5cc or bytes(cpu.mem_read(pointer, 4)) != b'2.0\0':
                raise ValueError('Original SOAP constructor default version differs')
            constructor_version = '2.0'
        if address in (0x8007c5e0, 0x8007c710):
            stubs[address] = stubs.get(address, 0) + 1
            ret(alloc(reg(3)))
            return
        if address == 0x8007c5f0:
            if reg(3) and not any(a <= reg(3) < a + n for a, n in allocations):
                raise ValueError('Free outside synthetic allocations')
            stubs[address] = stubs.get(address, 0) + 1
            ret()
            return
        if address in (0x80078610, 0x80074340):
            stubs[address] = stubs.get(address, 0) + 1
            ret()
            return
        if address == 0x80073380:
            stubs[address] = stubs.get(address, 0) + 1
            cpu.reg_write(UC_PPC_REG_0 + 4, 123)
            ret(0)
            return
        if address == 0x800a74a0:
            if reg(3) != soap:
                raise ValueError('Unexpected native transport object')
            handoff = read_string(reg(4))
            cpu.reg_write(UC_PPC_REG_PC, stop)
            return
        allowed = ((0x800043c4, 0x80004800), (0x80020410, 0x80020444),
                   (0x80073500, 0x800785c0), (0x8007b580, 0x8007ba50),
                   (0x8007c950, 0x8007db58), (0x80081850, 0x80084800),
                   (0x80088968, 0x80088bfc),
                   (0x802b5000, 0x802b5244), (0x802b5920, 0x802b5d00),
                   (0x802ba988, 0x802be000),
                   (0x802be000, 0x802bf000))
        if not any(b <= address < e for b, e in allowed):
            raise ValueError(f'Unexpected native request control flow: {address:08x}')

    def writes(_cpu, _access, a, n, _value, _data):
        ranges = ((env, env + 0x400), (stack - 0x3000, stack + 0x200),
                  (0x81200000, heap_end), (0x803d3100, 0x803d3180))
        if not any(b <= a < a + n <= e for b, e in ranges):
            raise ValueError(f'Unexpected native request write: {a:08x}')

    # Fixed build metadata from the fingerprinted executable, never identity state.
    original_product_pointer = word(0x80322658)
    if original_product_pointer != 0x803225e0:
        raise ValueError('Original ECVersion product pointer differs')
    original_product = bytes(cpu.mem_read(original_product_pointer, 64)).split(b'\0', 1)[0]
    if original_product != b'ECSHOP 4.8.0 Jul 27 2012 16:52:03':
        raise ValueError('Original ECVersion build metadata differs')
    # Only synthetic identities are installed. No environment is loaded from NAND.
    for name, offset in (('device_id', 0x1b0), ('serial_no', 0x230), ('account_id', 0xc0),
                         ('token', 0xcc), ('strong_token', 0xd8), ('weak_token', 0xf0),
                         ('application_id', 0x178), ('tin', 0x184), ('region', 0x1d0),
                         ('country', 0x120), ('language', 0x144), ('postal_code', 0x260)):
        string(env + offset, getattr(environment, name))
    cpu.mem_write(env + 0x1a8, bytes([environment.key_pair_confirmed]))
    put(wrapper, env)
    put(0x80322654, cvalue('synthetic-prefix'))
    put(0x80322658, cvalue(product_version))
    # Native getNetConfig writes this embedded initial URL into env.ecsUrl.
    endpoint = b'https://synthetic.invalid/ecs'
    cpu.mem_write(0x80322020, endpoint + b'\0')
    for a, n in ((env, 0x400), (wrapper, 16)):
        cpu.mem_write(a - 16, b'!' * 16)
        cpu.mem_write(a + n, b'!' * 16)
    for i, value in {1: stack, 2: 0x80369460, 13: 0x803674e0,
                     27: 0, 28: wrapper, 31: 0x80322020}.items():
        cpu.reg_write(UC_PPC_REG_0 + i, value)
    cpu.reg_write(UC_PPC_REG_MSR, cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
    cpu.hook_add(UC_HOOK_CODE, hook)
    cpu.hook_add(UC_HOOK_MEM_WRITE, writes)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80088968, stop, count=3000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop or handoff != endpoint:
        raise ValueError('Native request did not reach synthetic transport boundary')
    for a, n in ((env, 0x400), (wrapper, 16), (soap, 0xd0)):
        if bytes(cpu.mem_read(a - 16, 16)) != b'!' * 16 or bytes(cpu.mem_read(a + n, 16)) != b'!' * 16:
            raise ValueError('Synthetic native request object guard changed')
    for a, n in allocations:
        if bytes(cpu.mem_read(a - 32, 32)) != b'!' * 32 or bytes(cpu.mem_read(a + n, 32)) != b'!' * 32:
            raise ValueError('Synthetic native request allocation guard changed')
    begin, count, capacity = word(soap + 4), word(soap + 8), word(soap + 12)
    end = begin + 24 * count
    if (not 0 < count <= capacity <= 16
            or not any(a <= begin < end <= a + n for a, n in allocations)):
        raise ValueError('Unexpected native header vector layout/count')
    headers = [(read_string(a).decode('ascii'), read_string(a + 12).decode('ascii'))
               for a in range(begin, end, 24)]
    return {'request_bytes': read_string(soap + 0x1c), 'headers': headers,
            'header_text': read_string(soap + 0x10).decode('ascii'),
            'soap_action': next(v for k, v in headers if k == 'SOAPAction'),
            'http_handoff_endpoint': handoff.decode('ascii'), 'http_handoff_address': '0x800a74a0',
            'native_constructor_executed': True, 'native_xml_builder_stubbed': False,
            'native_default_version': constructor_version,
            'soap_object_guards_verified': soap_guard_set,
            'object_heap_and_write_bounds_verified': True,
            'native_instruction_addresses_visited': len(visits), 'heap_bytes_used': heap - 0x81200000,
            'stub_call_counts': {f'0x{k:08x}': v for k, v in stubs.items()},
            'synthetic_global_product_version_substituted': True,
            'original_product_version_build_metadata': original_product.decode('ascii'),
            'product_version_source_pointer_slot': '0x80322658',
            'synthetic_endpoint_and_message_prefix_substituted': True,
            'transport_executed': False, 'account_or_key_pair_verified': False}
