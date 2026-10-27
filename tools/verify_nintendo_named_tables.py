"""Guard original named-table getters, first-match lookups and Unicode copies.

Original instructions execute without service/SDK stubs. All record contents,
queries and any varied kind-byte cases are synthetic explicit fixture inputs.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import struct

from jwc24.nintendo_listdata import (DESCRIPTOR_OFFSET, KNOWN_STRIDES, ListDataFormatError,
                                     decode_listdata, inspect_listdata)
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA


def verify_named_tables_native(source, payload, *, classification_values=()):
    if (type(source) is not bytes or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    if (type(classification_values) is not tuple or len(classification_values) > 256
            or any(type(value) is not int or not 0 <= value <= 255 for value in classification_values)):
        raise ValueError('Expected bounded explicit synthetic kind-byte cases')
    raw, _compression = decode_listdata(payload)
    if not 0x5E8 <= len(raw) <= 65536:
        raise ValueError('Named-table native fixture exceeds the local body limit')
    tables = [struct.unpack_from('>II', raw, DESCRIPTOR_OFFSET + index * 8) for index in range(16)]
    for index, (count, offset) in enumerate(tables):
        if count and (index not in (1, 2, 3, 5) or count > 64
                      or not 0x5E8 <= offset < len(raw)
                      or offset + count * KNOWN_STRIDES[index] > len(raw)):
            raise ValueError('Named-table native fixture uses unsupported or unbounded table contents')
    try:
        expected = inspect_listdata(payload)
    except ListDataFormatError:
        expected = None
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Nintendo Channel image section exceeds bounded RAM')
        cpu.mem_write(address, source[offset:offset + size])
    obj, context, data, output, sda = 0x81001000, 0x81020000, 0x81100000, 0x81040000, 0x808041E0
    global_slot = sda - 0x4DF8
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'NAMED-TABLE-GUARD!' * 2
    objects = [(obj, bytes(0x84)), (context, bytes(0xB0)), (data, raw),
               (output, bytes(1000)), (global_slot, bytes(4))]
    for pointer, value in objects:
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'named_id_rows_compared': 0, 'named_code_rows_compared': 0,
              'first_match_lookups_compared': 0, 'missing_lookups_compared': 0,
              'software_id_relations_compared': 0, 'native_names_copied': 0,
              'classification_bytes_compared': 0}
    code_ranges = ((0x800329A0, 0x80032F8C), (0x8002C330, 0x8002C40C),
                   (0x8002C410, 0x8002C4CC), (0x8002C590, 0x8002C62C),
                   (0x8002C630, 0x8002C6E8), (0x8002ECB0, 0x8002EDDC),
                   (0x8002EDE0, 0x8002EE98), (0x80025110, 0x80025160),
                   (0x80025260, 0x800252E0), (0x80340460, 0x803404D0))

    def code(_cpu, address, _size, _context):
        counts['instructions'] += 1
        if counts['instructions'] > 3000000 or not any(lo <= address < hi for lo, hi in code_ranges):
            raise ValueError(f'Unexpected or excessive original named-table control flow at {address:#010x}')

    def read(_cpu, _access, address, size, _value, _context):
        ranges = [(pointer, pointer + len(value)) for pointer, value in objects]
        ranges += [(stack_lo, stack_hi), (0x8038FF58, 0x8038FF84)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError('Original named-table read exceeds synthetic fixture bounds')

    def write(_cpu, _access, address, size, _value, _context):
        ranges = [(obj, obj + 0x84), (output, output + 1000),
                  (global_slot, global_slot + 4), (stack_lo, stack_hi)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError('Original named-table consumer wrote outside its output objects')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def call(entry, args):
        for register in range(3, 11):
            cpu.reg_write(UC_PPC_REG_0 + register, 0)
        for register, value in {1: stack, 13: sda, **args}.items():
            cpu.reg_write(UC_PPC_REG_0 + register, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(entry, stop, count=100000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('Original named-table call exceeded instruction budget')
        return cpu.reg_read(UC_PPC_REG_0 + 3)

    call(0x80032DC0, {3: obj, 4: data})
    status = call(0x80032EC0, {3: obj})
    if status == 0:
        def copy_name(pointer, name):
            cpu.mem_write(output, bytes(1000))
            call(0x80025260, {3: output, 4: 500, 5: pointer})
            encoded = name.encode('utf-16-be') + bytes(2)
            if bytes(cpu.mem_read(output, len(encoded))) != encoded:
                raise ValueError('Original Unicode copy differs from independently decoded name')
            counts['native_names_copied'] += 1

        id_count, id_start = tables[1]
        code_count, code_start = tables[2]
        for index in range(id_count):
            offset = id_start + index * 0x6C
            if call(0x8002C610, {3: obj + 0x0C, 4: index}) != data + offset:
                raise ValueError('Original identifier-table stride differs from explicit rows')
            identifier = raw[offset]
            match = next(i for i in range(id_count) if raw[id_start + i * 0x6C] == identifier)
            cpu.mem_write(context + 0xA4, bytes([identifier]))
            pointer = call(0x8002C630, {3: context})
            if pointer != data + id_start + match * 0x6C + 4:
                raise ValueError('Original identifier name lookup differs from first-match order')
            if expected is not None:
                decoded = expected.find_named_id(identifier)
                if decoded.index != match:
                    raise ValueError('Independent identifier lookup differs from original match')
                copy_name(pointer, decoded.name)
            counts['named_id_rows_compared'] += 1
            counts['first_match_lookups_compared'] += 1
        for index in range(code_count):
            offset = code_start + index * 0x80
            if call(0x8002C3F0, {3: obj + 0x14, 4: index}) != data + offset:
                raise ValueError('Original code-table stride differs from explicit rows')
            key = raw[offset:offset + 4]
            match = next(i for i in range(code_count) if raw[code_start + i * 0x80:code_start + i * 0x80 + 4] == key)
            cpu.mem_write(context + 0xA5, key)
            pointer = call(0x8002C410, {3: context})
            if pointer != data + code_start + match * 0x80 + 4:
                raise ValueError('Original four-byte key lookup differs from first-match order')
            if expected is not None:
                decoded = expected.find_named_code(key)
                if decoded.index != match:
                    raise ValueError('Independent four-byte key lookup differs from original match')
                copy_name(pointer, decoded.name)
            counts['named_code_rows_compared'] += 1
            counts['first_match_lookups_compared'] += 1
        missing_id = next(value for value in range(256) if all(raw[id_start + i * 0x6C] != value for i in range(id_count)))
        cpu.mem_write(context + 0xA4, bytes([missing_id]))
        if call(0x8002C630, {3: context}) != sda - 0x7B58:
            raise ValueError('Original missing identifier does not take its observed fallback pointer')
        missing_code = next(value.to_bytes(4, 'big') for value in range(65)
                            if all(raw[code_start + i * 0x80:code_start + i * 0x80 + 4] != value.to_bytes(4, 'big')
                                   for i in range(code_count)))
        cpu.mem_write(context + 0xA5, missing_code)
        if call(0x8002C410, {3: context}) != sda - 0x7B58:
            raise ValueError('Original missing four-byte key did not take its observed fallback pointer')
        counts['missing_lookups_compared'] += 2
        software_count, software_start = tables[3]
        selected = None
        for index in range(software_count):
            pointer = data + software_start + index * 0xEC
            identifier = raw[software_start + index * 0xEC + 8]
            match = next((i for i in range(id_count) if raw[id_start + i * 0x6C] == identifier), None)
            expected_pointer = data + id_start + match * 0x6C + 1 if match is not None else 0
            if call(0x8002EDE0, {3: pointer}) != expected_pointer:
                raise ValueError('Original software byte relation differs from first matched identifier')
            if expected is not None:
                decoded = expected.named_id_for_software(index)
                if (decoded.index if decoded is not None else None) != match:
                    raise ValueError('Independent software relation differs from original match')
            if selected is None and match is not None and expected is not None:
                selected = pointer, expected.named_id_for_software(index)
            counts['software_id_relations_compared'] += 1
        if classification_values:
            if selected is None:
                raise ValueError('Explicit classification cases need a supported named software relation')
            pointer, decoded = selected
            kind_pointer = data + decoded.file_offset + 0x6A
            for value in classification_values:
                cpu.mem_write(kind_pointer, bytes([value]))
                if call(0x8002ECB0, {3: pointer}) != replace(decoded, byte_field_6a=value).classification_result():
                    raise ValueError('Original kind classification differs from preserved-byte projection')
                counts['classification_bytes_compared'] += 1
            cpu.mem_write(kind_pointer, bytes([decoded.byte_field_6a]))
    for pointer, value in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard):
            raise ValueError('Original named-table fixture guard changed')
    if (bytes(cpu.mem_read(data, len(raw))) != raw
            or bytes(cpu.mem_read(global_slot, 4)) != struct.pack('>I', obj)
            or bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('Original named-table immutable input or stack guard changed')
    return {'native_validator_status': status, 'independent_inline_name_subset_accepted': expected is not None,
            'counts': counts, 'native_getters_or_copy_helpers_stubbed': False,
            'synthetic_kind_values_explicitly_varied_by_host': bool(classification_values),
            'input_output_object_and_stack_guards_verified': True,
            'name_termination_bounds_are_stricter_local_policy': True,
            'full_catalog_semantics_or_original_ui_verified': False,
            'genuine_source_trust_or_freshness_verified': False}
