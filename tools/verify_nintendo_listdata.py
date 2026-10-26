"""Guarded HATJ ListData constructor, validator and selected record consumers.

Synthetic buffers only. No original catalog sample, I/O, transport, profile or
native screen is used. The original routines execute without SDK helper stubs.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_listdata import ListDataFormatError, decode_listdata, inspect_listdata
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA


def verify_listdata_native(source: bytes, payload: bytes):
    if (not isinstance(source, bytes) or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    raw, _compression = decode_listdata(payload)
    if not 0x5E8 <= len(raw) <= 65536:
        raise ValueError('Synthetic native ListData fixture exceeds local harness bounds')
    try:
        expected = inspect_listdata(payload)
    except ListDataFormatError:
        expected = None
    if expected is not None and len(expected.software_rows) + len(expected.linked_rows) > 64:
        raise ValueError('Synthetic native ListData row count exceeds local harness bounds')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Nintendo Channel DOL section exceeds emulation bounds')
        cpu.mem_write(address, source[offset:offset + size])
    obj, data, output, sda = 0x81001000, 0x81100000, 0x81040000, 0x81008000
    global_slot = sda - 0x4DF8
    stack_lo, stack_hi, stop = 0x817D0000, 0x817E1000, 0x817FF000
    guard = b'LISTDATA-GUARD!' * 3
    cpu.mem_write(obj, bytes(0x84))
    cpu.mem_write(data, raw)
    cpu.mem_write(output, bytes(1000))
    cpu.mem_write(global_slot, bytes(4))
    for address, size in ((obj, 0x84), (data, len(raw)), (output, 1000),
                          (global_slot, 4), (stack_lo, stack_hi - stack_lo)):
        cpu.mem_write(address - len(guard), guard)
        cpu.mem_write(address + size, guard)
    counts = {'instructions': 0, 'software_records_compared': 0,
              'native_titles_copied': 0, 'linked_records_compared': 0}
    visited = set()
    ranges = ((0x800329A0, 0x80032DBC), (0x80032DC0, 0x80032EB4),
              (0x80032EC0, 0x80032F8C), (0x8002EFB0, 0x8002EFCC),
              (0x8002EC90, 0x8002ECA4), (0x80025110, 0x80025160),
              (0x80025260, 0x800252E0), (0x8002F600, 0x8002F678),
              (0x8002F750, 0x8002F764), (0x80340460, 0x803404D0))

    def code(_cpu, address, _size, _context):
        counts['instructions'] += 1
        visited.add(address)
        if counts['instructions'] > 3000000 or not any(lo <= address < hi for lo, hi in ranges):
            raise ValueError('Unexpected or excessive native ListData control flow')

    read_ranges = ((obj, obj + 0x84), (data, data + len(raw)), (output, output + 1000),
                   (global_slot, global_slot + 4), (stack_lo, stack_hi))

    def read(_cpu, _access, address, size, _value, _context):
        if not any(lo <= address < address + size <= hi for lo, hi in read_ranges):
            raise ValueError('Native ListData read exceeds synthetic bounds')

    def write(_cpu, _access, address, size, _value, _context):
        allowed = ((obj, obj + 0x84), (output, output + 1000),
                   (global_slot, global_slot + 4), (stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Unexpected native ListData write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def call(entry, arguments):
        for index in range(3, 11):
            cpu.reg_write(UC_PPC_REG_0 + index, 0)
        for index, value in {1: 0x817E0000, 13: sda, **arguments}.items():
            cpu.reg_write(UC_PPC_REG_0 + index, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(entry, stop, count=1000000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Native ListData call exceeded instruction cap')
        return cpu.reg_read(UC_PPC_REG_0 + 3)

    call(0x80032DC0, {3: obj, 4: data})
    status = call(0x80032EC0, {3: obj})
    if status == 0 and expected is not None:
        for row in expected.software_rows:
            address = call(0x8002EFB0, {3: obj + 0x1C, 4: row.index})
            if address != data + row.file_offset:
                raise ValueError('Native software-row pointer differs from independent decoder')
            counts['software_records_compared'] += 1
            if row.title is not None:
                title_pointer = call(0x8002EC90, {3: address})
                if title_pointer != data + row.title_reference:
                    raise ValueError('Native software-title reference differs from independent decoder')
                call(0x80025260, {3: output, 4: 500, 5: title_pointer + 4})
                encoded = row.title.encode('utf-16-be') + bytes(2)
                if bytes(cpu.mem_read(output, len(encoded))) != encoded:
                    raise ValueError('Native UTF-16 title copy differs from independent decoder')
                counts['native_titles_copied'] += 1
        linked_table = expected.tables[5]
        software_table = expected.tables[3]
        for row in expected.linked_rows:
            address = data + linked_table.offset + row.index * 0x116
            if row.software_index is not None:
                pointer = call(0x8002F600, {3: address})
                if pointer != data + software_table.offset + row.software_index * 0xEC:
                    raise ValueError('Native linked software pointer differs from independent decoder')
            comparisons = ((0x8002F620, row.u32_field_06), (0x8002F640, row.byte_field_0a),
                           (0x8002F650, int(row.byte_field_0b != 0)),
                           (0x8002F670, row.byte_field_1a), (0x8002F750, int(row.flag_field_1b)))
            for entry, value in comparisons:
                if call(entry, {3: address}) != value:
                    raise ValueError('Native linked-row field differs from independent decoder')
            counts['linked_records_compared'] += 1
    for address, size in ((obj, 0x84), (data, len(raw)), (output, 1000),
                          (global_slot, 4), (stack_lo, stack_hi - stack_lo)):
        if (bytes(cpu.mem_read(address - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(address + size, len(guard))) != guard):
            raise ValueError('Native ListData fixture guard changed')
    if bytes(cpu.mem_read(data, len(raw))) != raw or bytes(cpu.mem_read(global_slot, 4)) != struct.pack('>I', obj):
        raise ValueError('Native ListData source bytes or published synthetic pointer changed')
    return {'native_validator_status': status,
            'independent_subset_accepted': expected is not None,
            'native_constructor_executed': 0x80032DC0 in visited,
            'native_validator_executed': 0x80032EC0 in visited,
            'counts': counts, 'sdk_helpers_stubbed': False,
            'input_and_stack_guards_verified': True,
            'crc_or_signature_checked': False,
            'catalog_sample_or_native_browsing_verified': False}
