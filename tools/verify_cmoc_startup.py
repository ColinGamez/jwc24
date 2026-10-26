"""Original HAPJ FD record/state consumer on explicit synthetic object storage.

Cached-record retrieval, singleton lookup and UI transition are intercepted.
Record constructor/type/copy/field-update code executes without field stubs.
This harness neither authenticates a response nor runs a startup/menu UI.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.cmoc import CMOCFormatError
from jwc24.cmoc_startup import decode_first_data_record, encode_first_data_record
from tools.verify_cmoc_framing import SOURCE_SHA256


def verify_first_data_consumer(source: bytes, record: bytes | None):
    if (not isinstance(source, bytes) or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    if record is not None and (not isinstance(record, bytes) or not 4 <= len(record) <= 128):
        raise ValueError('Expected a bounded synthetic FD record or missing record')
    expected = None
    if record is not None:
        try:
            expected = decode_first_data_record(record)
        except CMOCFormatError:
            pass
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('CMOC executable section exceeds the emulation map')
        cpu.mem_write(address, source[offset:offset + size])
    obj, constructor, data = 0x81001000, 0x81002000, 0x81100000
    manager, settings, singleton = 0x81003000, 0x81004000, 0x81005000
    stack_lo, stack_hi, stop = 0x817D0000, 0x817E1000, 0x817FF000
    guard = b'FD-GUARD!' * 4
    obj_initial = bytearray(b'\xA5' * 0xD0)
    struct.pack_into('>I', obj_initial, 0xC0, manager)
    manager_initial = bytearray(b'\xA5' * 0x10)
    struct.pack_into('>I', manager_initial, 0x0C, settings)
    initial = ((obj, bytes(obj_initial)), (constructor, b'\xA5' * 12),
               (manager, bytes(manager_initial)), (settings, b'\xA5' * 0x40),
               (singleton, b'\xA5' * 0x40), (data, record or b''))
    for address, value in initial:
        cpu.mem_write(address - len(guard), guard)
        cpu.mem_write(address, value)
        cpu.mem_write(address + len(value), guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'cached_record_lookups_stubbed': 0,
              'singleton_lookups_stubbed': 0, 'ui_transitions_intercepted': 0}
    visited = set()
    transition = None
    code_ranges = ((0x80004050, 0x80004134), (0x8005377C, 0x800537DC),
                   (0x80037504, 0x80037514), (0x80053A4C, 0x80053EB8),
                   (0x80011DE8, 0x80011DF8), (0x80036018, 0x8003602C))

    def return_stub(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        nonlocal transition
        counts['instructions'] += 1
        visited.add(address)
        if address == 0x8006F6C4:
            counts['cached_record_lookups_stubbed'] += 1
            return_stub(data if record is not None else 0)
            return
        if address == 0x8001187C:
            counts['singleton_lookups_stubbed'] += 1
            return_stub(singleton)
            return
        if address == 0x8027494C:
            counts['ui_transitions_intercepted'] += 1
            if cpu.reg_read(UC_PPC_REG_0 + 3) != obj + 0x64:
                raise ValueError('Unexpected CMOC synthetic UI-transition object')
            transition = cpu.reg_read(UC_PPC_REG_0 + 4)
            return_stub()
            return
        if counts['instructions'] > 100000 or not any(lo <= address < hi for lo, hi in code_ranges):
            raise ValueError('Unexpected or excessive native FD consumer control flow')

    readable = [(address, address + len(value)) for address, value in initial]
    readable.append((stack_lo, stack_hi))

    def read(_cpu, _access, address, size, _value, _context):
        if not any(lo <= address < address + size <= hi for lo, hi in readable):
            raise ValueError('Native FD consumer read exceeds synthetic record or object bounds')

    def write(_cpu, _access, address, size, _value, _context):
        allowed = ((constructor, constructor + 12), (obj + 0x9C, obj + 0xA8),
                   (settings + 0x1B, settings + 0x1C),
                   (singleton + 0x14, singleton + 0x15),
                   (singleton + 0x1C, singleton + 0x1E), (stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Unexpected native FD consumer write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def call(entry, argument):
        cpu.reg_write(UC_PPC_REG_0 + 1, 0x817E0000)
        cpu.reg_write(UC_PPC_REG_0 + 3, argument)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(entry, stop, count=10000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Native FD consumer call exceeded instruction cap')
        return cpu.reg_read(UC_PPC_REG_0 + 3)

    call(0x8005377C, constructor)
    template = encode_first_data_record(word_4=0, byte_8=0, byte_9=0, u16_a=0,
                                        evidence_ref='synthetic native constructor comparison')
    if bytes(cpu.mem_read(constructor, 12)) != template:
        raise ValueError('Native FD constructor differs from independent 12-byte framing')
    type_allowed = bool(call(0x80053E14, data)) if record is not None else False
    call(0x80053A4C, obj)
    copied = 0x80053CE8 in visited
    if copied:
        if record is None or len(record) < 12 or bytes(cpu.mem_read(obj + 0x9C, 12)) != record[:12]:
            raise ValueError('Native FD fixed record copy differs from synthetic input')
        if (bytes(cpu.mem_read(singleton + 0x14, 1)) != record[8:9]
                or bytes(cpu.mem_read(settings + 0x1B, 1)) != record[9:10]
                or bytes(cpu.mem_read(singleton + 0x1C, 2)) != record[10:12]):
            raise ValueError('Native FD state fields differ from observed record fields')
    for address, value in initial:
        if (bytes(cpu.mem_read(address - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(address + len(value), len(guard))) != guard):
            raise ValueError('Native FD fixture guard changed')
    for address, value in ((data, record or b''), (manager, bytes(manager_initial)),
                           (obj + 0xC0, struct.pack('>I', manager)),
                           (stack_lo - len(guard), guard), (stack_hi, guard)):
        if bytes(cpu.mem_read(address, len(value))) != value:
            raise ValueError('Native FD input, synthetic configuration or stack guard changed')
    if not copied and (bytes(cpu.mem_read(obj, 0xD0)) != bytes(obj_initial)
                       or bytes(cpu.mem_read(singleton, 0x40)) != b'\xA5' * 0x40
                       or bytes(cpu.mem_read(settings, 0x40)) != b'\xA5' * 0x40):
        raise ValueError('Rejected or missing FD record modified synthetic state')
    return {'native_constructor_matches_12_byte_encoder': True,
            'native_type_predicate_allows_record': type_allowed,
            'strict_record_subset_accepted': expected is not None,
            'native_fixed_record_copy_and_state_updates_executed': copied,
            'native_state_fields_match_record': copied,
            'intercepted_ui_transition_value': transition,
            'counts': counts, 'input_and_stack_guards_verified': True,
            'cached_retrieval_and_ui_services_stubbed': True,
            'http_auth_crypto_or_native_menu_verified': False}
