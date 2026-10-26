"""Guard selected original HATJ context, language and ListData-install slices.

No socket, file callback, scheduler, heap service or actual console is used.
The raw-input allocation is explicitly synthetic and distinct from body bytes.
"""
from __future__ import annotations

import hashlib
import struct

from jwc24.nintendo_csdata import decompress_csdata
from jwc24.nintendo_listdata import (DESCRIPTOR_OFFSET, MAX_LIST_BYTES,
                                     ListDataFormatError, decode_listdata, inspect_listdata)
from jwc24.nintendo_load import plan_japanese_list_load
from tools.verify_nintendo_csdata import SOURCE_BYTES, SOURCE_SHA


def verify_nintendo_load(source: bytes, csdata_payload: bytes, list_payload: bytes | None, *,
                         language_code: int, prior_load_result: int,
                         allocation_bytes: int = MAX_LIST_BYTES) -> dict:
    if (type(source) is not bytes or len(source) != SOURCE_BYTES
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Nintendo Channel v1792 executable fingerprint mismatch')
    if type(prior_load_result) is not int or prior_load_result not in (0, 1):
        raise ValueError('Expected the observed nonnegative normalized prior-load result')
    if type(allocation_bytes) is not int or not 0x5E8 <= allocation_bytes <= MAX_LIST_BYTES:
        raise ValueError('Synthetic allocation violates the reviewed native byte budget')
    plan = plan_japanese_list_load(csdata_payload, service_prefix=b'https://synthetic.invalid/',
                                   language_code=language_code)
    csdata, _kind = decompress_csdata(csdata_payload)
    if not plan.language_eligible and list_payload is not None:
        raise ValueError('Ineligible-language fixture must not supply downloaded list data')
    raw = None
    inspection = None
    compression = None
    if list_payload is not None:
        raw, compression = decode_listdata(list_payload)
        if not 0x5E8 <= len(raw) <= min(allocation_bytes, 65536) or len(list_payload) > allocation_bytes:
            raise ValueError('Synthetic list fixture exceeds bounded received/allocation bytes')
        if struct.unpack_from('>I', raw, 4)[0] > len(raw):
            raise ValueError('Synthetic declared list bytes exceed the supplied body')
        for index in range(16):
            count, _offset = struct.unpack_from('>II', raw, DESCRIPTOR_OFFSET + index * 8)
            if count > 64 or (count and index not in (3, 5)):
                raise ValueError('Native install fixture uses unreviewed table content or too many rows')
        try:
            inspection = inspect_listdata(list_payload)
        except ListDataFormatError:
            pass  # Native gate failures and stronger local-policy failures are separate.

    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR, UC_PPC_REG_MSR
    layout = list(sections(source))

    def word(address):
        for _index, offset, base, size in layout:
            if base <= address < address + 4 <= base + size:
                return struct.unpack_from('>I', source, offset + address - base)[0]
        raise ValueError('Expected original callsite is outside the supplied sections')

    # Read actual caller instructions rather than guessing the installed buffer
    # capacity from a previous decoder constant. Decode addis/addi and bl fields.
    high, low, branch = (word(address) for address in (0x80048298, 0x800482B8, 0x800482BC))
    if ((high >> 26, (high >> 21) & 31, (high >> 16) & 31) != (15, 10, 0)
            or (low >> 26, (low >> 21) & 31, (low >> 16) & 31) != (14, 10, 10)):
        raise ValueError('Original retail capacity instructions differ from the reviewed caller')
    low_value = low & 0xFFFF
    capacity = ((high & 0xFFFF) << 16) + (low_value - 65536 if low_value & 0x8000 else low_value)
    displacement = branch & 0x03FFFFFC
    if displacement & 0x02000000:
        displacement -= 0x04000000
    if capacity != MAX_LIST_BYTES or branch >> 26 != 18 or branch & 3 != 1 or 0x800482BC + displacement != 0x80026590:
        raise ValueError('Original retail allocation/call contract differs from the reviewed path')

    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _index, offset, address, size in layout:
        if not 0x80000000 <= address < address + size <= 0x81800000:
            raise ValueError('Nintendo Channel DOL section exceeds emulation bounds')
        cpu.mem_write(address, source[offset:offset + size])
    obj, cs_obj, cs_raw = 0x81001000, 0x81002000, 0x81010000
    src, output, context, published = 0x81100000, 0x81300000, 0x81510000, 0x81514000
    config = 0x81518000
    config_slot, global_slot = 0x8048EBCC, 0x808041E0 - 0x4DF8
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817DFF80, 0x817FF000
    guard = b'NINTENDO-LOAD-GUARD!' * 2
    initial_pair = struct.pack('>II', 0x11111111, 0x22222222)
    fixtures = [(obj, bytes(0x84)), (cs_obj, struct.pack('>I', cs_raw) + bytes(0x21C)),
                (cs_raw, csdata), (context, bytes(0x2C00)), (published, initial_pair),
                (config, bytes(0x3000)), (config_slot, struct.pack('>I', config)),
                (global_slot, bytes(4))]
    source_allocation = None
    if raw is not None:
        source_allocation = list_payload + b'\xA5' * (allocation_bytes - len(list_payload))
        fixtures += [(src, source_allocation), (output, b'\xCC' * allocation_bytes)]
    for address, value in fixtures:
        cpu.mem_write(address - len(guard), guard)
        cpu.mem_write(address, value)
        cpu.mem_write(address + len(value), guard)
    cpu.mem_write(config + 0x2EF8, bytes([language_code]))
    cpu.mem_write(context + 0x27A4, struct.pack('>I', 1))
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'error_boundaries': 0, 'scheduler_boundaries': 0,
              'temporary_frees': 0}
    errors = []
    visited = set()
    phase = 'configure'
    edge = None
    validator_status = None
    code_ranges = ((0x800265B4, 0x800265D4), (0x800266A8, 0x80026728),
                   (0x80026950, 0x800269F4), (0x80026A10, 0x80026A68),
                   (0x80018E80, 0x80018E84), (0x800350F0, 0x800350FC),
                   (0x80036E50, 0x80036E64), (0x800327F0, 0x80032874),
                   (0x800329A0, 0x80032F8C), (0x8002F600, 0x8002F678),
                   (0x8002F750, 0x8002F764), (0x80004364, 0x800046E0),
                   (0x80100A20, 0x80100BAC), (0x80340460, 0x803404D0))

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        nonlocal edge, validator_status
        counts['instructions'] += 1
        visited.add(address)
        if ((phase == 'configure' and address == 0x800265D4)
                or (phase == 'language' and address in (0x80026728, 0x800269F4))
                or (phase == 'install' and address == 0x800269F4)):
            edge = address
            cpu.emu_stop()
            return
        if address == 0x8002699C:
            validator_status = cpu.reg_read(UC_PPC_REG_0 + 3)
        if address == 0x80019ED0:
            errors.append(tuple(cpu.reg_read(UC_PPC_REG_0 + register) for register in (3, 4)))
            counts['error_boundaries'] += 1
            ret()
            return
        if address == 0x8021EF80:
            counts['scheduler_boundaries'] += 1
            ret()
            return
        if address == 0x80014070:
            if cpu.reg_read(UC_PPC_REG_0 + 3) != src:
                raise ValueError('Native temporary release names an unexpected synthetic allocation')
            counts['temporary_frees'] += 1
            ret()
            return
        if not any(lo <= address < hi for lo, hi in code_ranges):
            raise ValueError('Unexpected native Nintendo load control flow')

    def read(_cpu, _access, address, size, _value, _context):
        allowed = [(pointer, pointer + len(value)) for pointer, value in fixtures]
        allowed.append((stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Native Nintendo load read exceeds synthetic fixture bounds')

    def write(_cpu, _access, address, size, _value, _context):
        allowed = [(stack_lo, stack_hi), (context + 0x2788, context + 0x27A8),
                   (published, published + 8), (obj, obj + 0x84), (global_slot, global_slot + 4)]
        if raw is not None:
            allowed.append((output, output + allocation_bytes))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Unexpected native Nintendo load write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for register, value in {1: stack, 13: 0x808041E0, 3: context, 4: published, 5: cs_obj,
                            6: 0, 7: 0, 8: obj, 9: output, 10: allocation_bytes}.items():
        cpu.reg_write(UC_PPC_REG_0 + register, value)
    # Native memcpy uses lfd/stfd. Enable the PPC floating-point facility rather
    # than replacing those original instructions with a host memcpy stub.
    cpu.reg_write(UC_PPC_REG_MSR, 0x2000)
    cpu.emu_start(0x800265B4, stop, count=100)
    expected_context = struct.pack('>7I', published, cs_obj, 0, 0, obj, output, allocation_bytes)
    if edge != 0x800265D4 or bytes(cpu.mem_read(context + 0x2788, 28)) != expected_context:
        raise ValueError('Original context assignment differs from explicit fixture')
    phase, edge = 'language', None
    for register, value in {1: stack, 30: context, 31: prior_load_result}.items():
        cpu.reg_write(UC_PPC_REG_0 + register, value)
    cpu.emu_start(0x800266A8, stop, count=20000)
    if (edge == 0x80026728) != plan.language_eligible or edge not in (0x80026728, 0x800269F4):
        raise ValueError('Original pre-download language gate differs from independent plan')
    if plan.language_eligible and raw is not None:
        phase, edge = 'install', None
        cpu.mem_write(stack + 8, struct.pack('>II', allocation_bytes, src))
        cpu.emu_start(0x80026950, stop, count=5000000)
        if edge != 0x800269F4 or validator_status is None:
            raise ValueError('Original install slice did not reach its bounded worker exit')
        passed = validator_status == 0
        expected_pair = struct.pack('>II', cs_obj, obj) if passed else initial_pair
        if bytes(cpu.mem_read(published, 8)) != expected_pair:
            raise ValueError('Native publication decision differs from actual validator result')
        expected_bytes = source_allocation if compression == 'none' else raw + b'\xCC' * (allocation_bytes - len(raw))
        if bytes(cpu.mem_read(output, allocation_bytes)) != expected_bytes:
            raise ValueError('Original copy/decompression differs from explicit raw/allocation bytes')
        if counts['temporary_frees'] != 1 or counts['scheduler_boundaries'] != int(passed):
            raise ValueError('Original release/scheduler decisions differ from observed path')
        if counts['error_boundaries'] != int(not passed) or (not passed and errors != [(0xFFFFFF2F, 262000)]):
            raise ValueError('Original failed-list error boundary differs from observed path')
        expected_result = prior_load_result if passed else 1
        if bytes(cpu.mem_read(global_slot, 4)) != struct.pack('>I', obj):
            raise ValueError('Original constructor did not assign its synthetic global pointer')
        if cpu.reg_read(UC_PPC_REG_0 + 3) != 0:
            raise ValueError('Original worker slice exit differs from zero-return contract')
    else:
        passed = None
        expected_result = 1 if plan.language_eligible else 0
        expected_pair = initial_pair if plan.language_eligible else struct.pack('>II', cs_obj, 0)
        if bytes(cpu.mem_read(published, 8)) != expected_pair or counts['temporary_frees']:
            raise ValueError('Original no-download publication/release behavior differs')
    if bytes(cpu.mem_read(context + 0x27A4, 4)) != struct.pack('>I', expected_result):
        raise ValueError('Original context load-result store differs from the observed path')
    if bytes(cpu.mem_read(context + 0x2788, 28)) != expected_context:
        raise ValueError('Native Nintendo load changed supplied context fields')
    for pointer, value in fixtures:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard):
            raise ValueError('Native Nintendo load fixture guard changed')
        if pointer not in (obj, output, context, published, config, global_slot):
            if bytes(cpu.mem_read(pointer, len(value))) != value:
                raise ValueError('Native Nintendo load changed immutable input bytes')
    if (bytes(cpu.mem_read(config + 0x2EF8, 1)) != bytes([language_code])
            or bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('Native Nintendo configuration or stack guard changed')
    return {
        'retail_capacity_callsite_verified': True, 'retail_capacity_used': allocation_bytes == MAX_LIST_BYTES,
        'allocation_bytes': allocation_bytes, 'received_payload_bytes': len(list_payload) if list_payload is not None else 0,
        'native_context_assignment_executed': True, 'native_language_gate_executed': True,
        'language_eligible': plan.language_eligible, 'native_install_slice_executed': validator_status is not None,
        'native_validator_result': validator_status, 'native_install_publication_pair_updated': passed,
        'native_ineligible_language_published_csdata_only': not plan.language_eligible,
        'native_constructor_global_pointer_assigned_before_validation': validator_status is not None,
        'independent_record_subset_accepted': inspection is not None,
        'original_copy_decompressor_constructor_validator_stubbed': False,
        'raw_allocation_padding_is_synthetic_not_received_body': True,
        'error_scheduler_and_free_boundaries_stubbed': True,
        'input_output_context_and_stack_guards_verified': True,
        'counts': counts, 'full_async_loader_or_network_verified': False,
        'authentication_freshness_or_browsing_verified': False,
    }
