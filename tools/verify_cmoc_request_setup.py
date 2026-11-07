"""Run original CMOC cached worker/configured setup against synthetic RAM.

The lower SDK record constructor and runtime/resource boundaries are mocked;
this does not validate cryptographic material or a network transaction.
"""
import hashlib
import struct

from jwc24.cmoc_request_setup import project_request_setup
from tools.verify_cmoc_framing import SOURCE_SHA256


def verify_request_setup(source, **inputs):
    expected = project_request_setup(**inputs)
    if type(inputs['cached_prefix']) is not bytes or len(inputs['cached_prefix']) != 12:
        raise ValueError('Concrete cached worker requires its twelve-byte descriptor prefix')
    if (type(source) is not bytes or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    layout = sections(source)
    for _, offset, address, size in layout:
        cpu.mem_write(address, source[offset:offset + size])
    worker, request, singleton, resource = 0x81000000, 0x81100000, 0x81110000, 0x81120000
    prefix, cached, app, context = 0x81130000, 0x81140000, 0x81150000, 0x81160000
    sdk, record, response = 0x81200000, 0x81210000, 0x81220000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'CMOC-SETUP-GUARD!' * 2
    objects = []

    def put(pointer, value, mutable=False):
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, bytes(value))
        cpu.mem_write(pointer + len(value), guard)
        objects.append((pointer, bytes(value), mutable))

    def word(pointer, value):
        cpu.mem_write(pointer, struct.pack('>I', value & 0xFFFFFFFF))

    def getword(pointer):
        return struct.unpack('>I', bytes(cpu.mem_read(pointer, 4)))[0]

    config = inputs['configuration']
    req = bytearray(0x3DB4)
    struct.pack_into('>HBBII', req, 0, 0x4644, 1, 2, 3, 4)
    req[:12] = inputs['cached_prefix']
    struct.pack_into('>III', req, 0x20, 0, inputs['native_method_word'], int(inputs['timestamp_present']))
    req[0x2E:0x2E + len(inputs['url']) + 1] = inputs['url'].encode() + b'\0'
    # Empty native request-header queue: original queue consumer still runs.
    struct.pack_into('>I', req, 0xB4, 1)
    put(worker, bytes(0xC0000), True)
    put(request, req)
    put(singleton, bytes(0x100), True)
    raw_config = bytearray(0x30)
    if config:
        struct.pack_into('>8I', raw_config, 0x10,
                         len(config.wire_prefix or b''), prefix if config.wire_prefix is not None else 0,
                         config.hash_span_size, 0, 0, 0, 0, config.decompression_word)
    put(resource, raw_config)
    put(prefix, (config.wire_prefix or b'') if config else b'')
    put(cached, inputs['cached_prefix'] or b'')
    appdata = bytearray(0x100)
    if inputs['appver_header_value'] is not None:
        appdata[0x18:0x18 + len(inputs['appver_header_value']) + 1] = inputs['appver_header_value'] + b'\0'
        appdata[0x58] = 1
    put(app, appdata)
    put(context, bytes(0x200))
    put(sdk, bytes(0x8060), True)
    recdata = bytearray(0x254)
    struct.pack_into('>I', recdata, 0x2C, response)
    put(record, recdata)
    put(response, bytes(0x43C))
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'worker_calls': 0, 'setup_calls': 0,
              'configured_constructor_calls': 0, 'sdk_constructor_calls': 0,
              'sdk_lower_record_boundary_calls': 0, 'header_calls': 0,
              'hash_setup_boundaries': 0, 'cipher_setup_boundaries': 0,
              'decompression_setup_boundaries': 0}
    headers = []
    observed = {}

    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0 + n)

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def string(pointer):
        if not pointer:
            return None
        value = bytearray()
        for i in range(128):
            c = cpu.mem_read(pointer + i, 1)[0]
            if not c:
                return bytes(value)
            value.append(c)
        raise ValueError('Unbounded native CMOC setup string')

    def code(_cpu, address, _size, _ctx):
        counts['instructions'] += 1
        for addr, name in ((0x80072500, 'worker_calls'), (0x80073E58, 'setup_calls'),
                           (0x8019C7C4, 'sdk_constructor_calls')):
            if address == addr:
                counts[name] += 1
        if address == 0x8007F10C and reg(6):
            counts['configured_constructor_calls'] += 1
        if address == 0x800721F8:
            ret(request)
        elif address == 0x8007282C:
            # Concrete resource-selection predicate is isolated from global config.
            ret(int(config is not None))
        elif address == 0x80064EF4:
            ret(singleton)
        elif address == 0x80064F80:
            ret(resource)
        elif address in (0x802880E0, 0x8019D7DC):
            ret()
        elif address == 0x800650A4:
            ret(0)  # Timer configuration unavailable; no retry timer update.
        elif address == 0x80079FF8:
            counts['hash_setup_boundaries'] += 1
            word(worker + 0xC8, config.hash_span_size)
            ret()
        elif address == 0x8006924C:
            counts['cipher_setup_boundaries'] += 1
            ret()
        elif address == 0x80069428:
            counts['decompression_setup_boundaries'] += 1
            observed['decompression'] = bool(reg(6))
            ret()
        elif address in (0x8019E0E8, 0x8019E150, 0x8019E16C):
            ret(context)
        elif address == 0x80196958:
            if reg(3) != 0x8060 or reg(4) != 32:
                raise ValueError('Unexpected CMOC SDK allocation')
            ret(sdk)
        elif address == 0x80197C64:
            counts['sdk_lower_record_boundary_calls'] += 1
            observed.update(url=string(reg(4)), method=reg(5), capacity=reg(7),
                            callback_argument=reg(8))
            # r8 is user context here; callback function remains in SDK object.
            ret(record)
        elif address == 0x8019DBE8:
            word(sdk, 77)
            ret(77)
        elif address == 0x8003794C:
            value = inputs['date_header_value'] or b''
            cpu.mem_write(reg(3), value + bytes(0x4C - len(value)))
            ret(reg(3))
        elif address == 0x800526C4:
            ret(app)
        elif address == 0x8019D0F4:
            headers.append((string(reg(4)).decode('ascii'), string(reg(5))))
            counts['header_calls'] += 1
            ret()
        elif address in (0x8019D904, 0x8019D964, 0x8019D610, 0x8019CAA8):
            # Async SDK options/start scheduling are separate from construction.
            ret()
        else:
            allowed = ((0x80004000, 0x80004134), (0x80068B98, 0x80068D34),
                       (0x800697F4, 0x8006980C), (0x8006C16C, 0x8006C174),
                       (0x8006D5BC, 0x8006D5C4), (0x80072500, 0x80072850),
                       (0x80073804, 0x80073808), (0x80073E58, 0x800741A4),
                       (0x8007A154, 0x8007A184), (0x8007A27C, 0x8007A334),
                       (0x8007F0D4, 0x8007F3F0), (0x800D64D0, 0x800D6580),
                       (0x800DE0A8, 0x800DE164), (0x801951EC, 0x801951F8),
                       (0x801992FC, 0x80199308), (0x8019C7C4, 0x8019C90C),
                       (0x8019E174, 0x8019E184))
            if not any(lo <= address < hi for lo, hi in allowed):
                raise ValueError(f'Unexpected CMOC setup control flow at {address:#x}')

    def read(_cpu, _access, address, size, _value, _ctx):
        allowed = [(p, p + len(v)) for p, v, _ in objects]
        allowed += [(a, a + n) for i, _, a, n in layout if i >= 7]
        allowed.append((stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC setup read at {address:#x}')

    def write(_cpu, _access, address, size, _value, _ctx):
        allowed = [(p, p + len(v)) for p, v, mutable in objects if mutable]
        allowed.append((stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC setup write at {address:#x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for n, value in {1: stack, 2: 0x80435BE0, 13: 0x80432BA0, 3: worker}.items():
        cpu.reg_write(UC_PPC_REG_0 + n, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x80072500, stop, count=500000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('CMOC setup instruction cap reached')
    if (observed.get('url') != inputs['url'].encode()
            or observed.get('method') != expected.native_method_word
            or observed.get('capacity') != expected.receive_capacity
            or observed.get('callback_argument') != worker
            or tuple(headers) != expected.requested_headers
            or getword(worker + 0x204) != sdk
            or getword(sdk + 0x1C) != 0x8007F3F0
            or getword(worker + 0x20C) != len(expected.retained_wire_prefix)
            or bytes(cpu.mem_read(worker + 0x210, len(expected.retained_wire_prefix))) != expected.retained_wire_prefix
            or getword(worker + 0x250) != len(expected.retained_cached_prefix)
            or bytes(cpu.mem_read(worker + 0x254, len(expected.retained_cached_prefix))) != expected.retained_cached_prefix
            or (config is not None and observed.get('decompression') != expected.decompression_requested)):
        raise ValueError('Original CMOC setup differs from independent projection')
    for pointer, value, mutable in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard
                or (not mutable and bytes(cpu.mem_read(pointer, len(value))) != value)):
            raise ValueError('CMOC setup fixture or boundary guards changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('CMOC setup stack guards changed')
    return {**expected.metadata(), 'counts': counts,
            'complete_cached_worker_and_setup_executed': True,
            'complete_sdk_outer_constructor_executed': True,
            'resource_crypto_and_sdk_lower_record_boundaries_mocked': True,
            'input_and_stack_guards_verified': True}
