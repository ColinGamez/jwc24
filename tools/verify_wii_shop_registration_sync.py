"""Run retail v21 registration sync with synthetic signing and transport only.

The original caller, sync setup, run, SOAP, XML, assignment and token derivation
execute. Signing supplies explicit synthetic bytes. Transport supplies explicit
response bytes; config, title-removal and shop-log boundaries only count calls.
No HTTP, credentials, browser, NAND, cryptographic proof or persistence is used.
Returned values echo synthetic fixtures and must never log real service data.
"""
from dataclasses import dataclass, field, fields
import hashlib
import struct

from tools.verify_wii_shop_ec_config_request import SyntheticRequestEnvironment
from tools.verify_wii_shop_url import SOURCE_SHA


@dataclass(frozen=True)
class SyntheticRegistrationEnvironment(SyntheticRequestEnvironment):
    account_country: str = field(default='old-country', repr=False)
    ext_account_id: str = field(default='old-ext', repr=False)
    account_device_code: str = field(default='old-code', repr=False)
    use_ecdk_sync_registration: bool = True
    need_ticket_sync: bool = False
    import_all: bool = False
    force_sync_time: int = 11
    ext_ticket_time: int = 22
    sync_time: int = 33
    last_ticket_sync_time: int = 44


@dataclass(frozen=True)
class SyntheticRegistrationProof:
    challenge: str = field(repr=False)
    device_cert: str = field(repr=False)
    signature: str = field(repr=False)
    cert_chain: str = field(repr=False)


def verify_registration_sync(source, response, *, proof, environment=None,
                             transport_status=0, sign_status=0, save_status=0,
                             remove_titles_status=-999):
    if (not isinstance(source, bytes) or not 0 < len(source) <= 4*1024*1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Expected fingerprinted original v21 executable')
    if (not isinstance(response, bytes) or not 0 < len(response) <= 16384 or b'\0' in response
            or any(type(v) is not int or not -(1 << 31) <= v <= 0
                   for v in (transport_status, sign_status, save_status, remove_titles_status))):
        raise ValueError('Expected bounded synthetic registration/transport fixture')
    environment = SyntheticRegistrationEnvironment() if environment is None else environment
    if type(environment) is not SyntheticRegistrationEnvironment:
        raise ValueError('Expected explicitly synthetic request environment')
    bool_fields = ('key_pair_confirmed', 'use_ecdk_sync_registration', 'need_ticket_sync', 'import_all')
    int_fields = ('force_sync_time', 'ext_ticket_time', 'sync_time', 'last_ticket_sync_time')
    try:
        invalid = any(not isinstance(v := getattr(environment, f.name), str)
                      or len(v.encode('utf-8')) > 96 or '\0' in v
                      for f in fields(environment) if f.name not in (*bool_fields, *int_fields))
        invalid = invalid or type(proof) is not SyntheticRegistrationProof or any(
            not isinstance(v := getattr(proof, f.name), str)
            or len(v.encode('utf-8')) > (512 if f.name in ('device_cert', 'cert_chain') else 96)
            or '\0' in v for f in fields(proof))
    except (UnicodeError, TypeError):
        raise ValueError('Expected bounded synthetic UTF-8 environment and proof strings') from None
    if (invalid or any(type(getattr(environment, f)) is not bool for f in bool_fields)
            or any(type(v := getattr(environment, f)) is not int or not -(1 << 63) <= v < (1 << 63)
                   for f in int_fields)):
        raise ValueError('Expected explicitly synthetic environment and proof values')
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    env, wrapper, current = 0x81001000, 0x81000000, 0x81002000
    stack, stop = 0x817df000, 0x80088e70
    soap = stack-0x138
    heap, heap_end = 0x81200000, 0x81600000
    allocations, visits, stubs = [], set(), {}
    captured, side_effects = {}, []
    signed_payload = None
    registration_reader_executed = False

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
        if not value:
            cpu.mem_write(address, bytes(12))
            return
        pointer = cvalue(value)
        cpu.mem_write(address, struct.pack('>III', 0x80000000 | len(value), len(value), pointer))

    def read_string(address):
        ranges = ((env, env+0x400), (current, current+0x100), (wrapper, wrapper+0x130),
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
        nonlocal registration_reader_executed, signed_payload
        visits.add(address)
        if address == 0x80088480:
            registration_reader_executed = True
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
        if address == 0x80078570:
            if signed_payload is not None:
                raise ValueError('Unexpected repeated synthetic signing boundary')
            signed_payload = read_string(reg(3))
            if sign_status == 0:
                string(reg(4), proof.signature.encode('utf-8'))
                string(reg(5), proof.cert_chain.encode('utf-8'))
            stubs[address] = stubs.get(address, 0)+1
            ret(sign_status)
            return
        if address in (0x80075270, 0x800a60f0, 0x8009ef10):
            side_effects.append((address, reg(3)))
            stubs[address] = stubs.get(address, 0)+1
            ret(save_status if address == 0x80075270 else remove_titles_status if address == 0x8009ef10 else 0)
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
            if captured or reg(3) != soap or read_string(reg(4)) != b'https://synthetic.invalid/ias':
                raise ValueError('Unexpected synthetic IAS transport handoff')
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
                   (0x80072400, 0x80073080), (0x80073500, 0x800785c0), (0x8007ad80, 0x8007ade4),
                   (0x8007b280, 0x8007c5e0),
                   (0x8007c950, 0x8007eb50), (0x80081850, 0x80084800),
                   (0x80087470, 0x800886b4), (0x80088e58, 0x80088e70), (0x802b5000, 0x802b5244),
                   (0x802b5920, 0x802b5d00), (0x802ba988, 0x802bf000),
                   (0x802c0570, 0x802c11b0))
        if not any(b <= address < e for b, e in allowed):
            raise ValueError(f'Unexpected native IAS control flow: {address:08x}')

    def write(_cpu, _access, address, size, _value, _data):
        ranges = ((env, env+0x400), (current, current+0x100), (wrapper, wrapper+0x130), (wrapper, wrapper+0x130),
                  (stack-0x4000, stack+0x100), (0x81200000, heap_end),
                  (0x803d3100, 0x803d3180), (0x803613c8, 0x803613cc))
        if not any(b <= address < address+size <= e for b, e in ranges):
            raise ValueError(f'Unexpected native IAS write: {address:08x}')

    for name, offset in (('device_id', 0x1b0), ('serial_no', 0x230), ('account_id', 0xc0),
                         ('token', 0xcc), ('strong_token', 0xd8), ('weak_token', 0xf0),
                         ('application_id', 0x178), ('tin', 0x184), ('region', 0x1d0),
                         ('country', 0x120), ('language', 0x144), ('postal_code', 0x260)):
        string(env+offset, getattr(environment, name).encode('utf-8'))
    string(env+0x1c, b'https://synthetic.invalid/ias')
    string(env+0x68, proof.challenge.encode('utf-8'))
    string(env+0x224, proof.device_cert.encode('utf-8'))
    for name, offset in (('account_country', 0x12c), ('ext_account_id', 0x114), ('account_device_code', 0x138)):
        string(env+offset, getattr(environment, name).encode('utf-8'))
    for offset, name in ((0x150, 'force_sync_time'), (0x158, 'ext_ticket_time'),
                         (0x160, 'sync_time'), (0x168, 'last_ticket_sync_time')):
        cpu.mem_write(env+offset, struct.pack('>q', getattr(environment, name)))
    for offset, name in ((0x170, 'need_ticket_sync'), (0x171, 'import_all'),
                         (0x25d, 'use_ecdk_sync_registration')):
        cpu.mem_write(env+offset, bytes([getattr(environment, name)]))
    cpu.mem_write(env+0x1a8, bytes([environment.key_pair_confirmed]))
    put(wrapper, env)
    put(wrapper+0xc0, 0x80321ba0)
    put(0x803d35a0, wrapper)
    put(env+4, current)
    put(0x80322654, cvalue(b'synthetic-prefix'))
    guards = ((env, 0x400), (current, 0x100), (wrapper, 0x130), (stack-0x4000, 0x4100))
    for address, size in guards:
        cpu.mem_write(address-16, b'!'*16)
        cpu.mem_write(address+size, b'!'*16)
    for i, value in {1: stack, 2: 0x80369460, 13: 0x803674e0, 3: wrapper, 28: wrapper, 29: 0x803d0000}.items():
        cpu.reg_write(UC_PPC_REG_0+i, value)
    cpu.reg_write(UC_PPC_REG_MSR, cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.emu_start(0x80088e58, stop, count=3000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError(f'Native IAS registration operation did not finish within instruction bound: {cpu.reg_read(UC_PPC_REG_PC):08x}')
    for address, size in (*guards, *allocations):
        padding = 32 if (address, size) in allocations else 16
        if (bytes(cpu.mem_read(address-padding, padding)) != b'!'*padding
                or bytes(cpu.mem_read(address+size, padding)) != b'!'*padding):
            raise ValueError('Synthetic IAS object or allocation guard changed')
    status = reg(3)
    return {'status': status-0x100000000 if status & 0x80000000 else status,
            'request_bytes': captured.get('request_bytes'), 'headers': captured.get('headers'),
            'signed_payload_bytes': signed_payload,
            'account_id_bytes': read_string(env+0xc0), 'device_token_bytes': read_string(env+0xcc),
            'strong_token_bytes': read_string(env+0xd8), 'weak_token_bytes': read_string(env+0xf0),
            'account_country_bytes': read_string(env+0x12c), 'ext_account_id_bytes': read_string(env+0x114),
            'account_device_code_bytes': read_string(env+0x138),
            'response_account_id_bytes': read_string(wrapper+0xec),
            'response_device_token_bytes': read_string(wrapper+0xf8),
            'token_expired': bool(word(wrapper+0x128)),
            'unregistered': bool(cpu.mem_read(wrapper+0x12c, 1)[0]),
            'need_ticket_sync': bool(cpu.mem_read(env+0x170, 1)[0]),
            'import_all': bool(cpu.mem_read(env+0x171, 1)[0]),
            'sync_times': [struct.unpack('>q', bytes(cpu.mem_read(env+o, 8)))[0]
                           for o in (0x150, 0x158, 0x160, 0x168)],
            'save_config_calls': stubs.get(0x80075270, 0),
            'remove_titles_calls': stubs.get(0x8009ef10, 0),
            'shop_log_actions': [value for address, value in side_effects if address == 0x800a60f0],
            'native_sync_entry_executed': 0x80088620 in visits,
            'native_registration_run_executed': 0x80087500 in visits,
            'native_account_assignment_executed': 0x800875fc in visits,
            'native_worker_sync_caller_executed': 0x80088e6c in visits,
            'native_token_derivation_executed': 0x800749c0 in visits,
            'native_md5_executed': 0x80072400 in visits and 0x80072520 in visits,
            'connected_flag': bool(cpu.mem_read(env+0x174, 1)[0]),
            'complete_connection_worker_executed': False,
            'signing_signature_check_or_persistence_executed': False,
            'native_request_builder_executed': 0x80088230 in visits,
            'native_common_response_parser_executed': 0x8007dd20 in visits,
            'native_registration_reader_executed': registration_reader_executed,
            'native_xml_helpers_stubbed': False,
            'native_token_setter_and_md5_stubbed': False,
            'native_instruction_addresses_visited': len(visits),
            'object_heap_stack_and_write_bounds_verified': True,
            'stub_call_counts': {f'0x{k:08x}': v for k, v in stubs.items()},
            'transport_executed': False, 'account_or_device_authorized': False}
