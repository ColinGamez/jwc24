"""Execute the original HAGJ v7 article display-model constructor offline.

This does not execute the separate ticker table, text rendering or delivery.
Only allocation is stubbed; original title/source lookup and UTF-16 routines run.
"""
from __future__ import annotations

import hashlib
import struct

SOURCE_SHA256 = '8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852'
ENTRY = 0x8000FA38
MAX_BODY_BYTES = 65536
MAX_INSTRUCTIONS = 100000


def verify_news_headline_model(source, raw, *, expected_title,
                               expected_source_name, article_index=0):
    """Verify exact caller-supplied synthetic title/display text without returning it.

    The selected article reference is synthetic. This deliberately does not run
    the buffer validator: malformed ticker fields can be negative controls for
    this constructor's access scope, not accepted publication/news payloads.
    """
    if (type(source) is not bytes or len(source) > 4 * 1024 * 1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('Japanese News v7 executable fingerprint mismatch')
    if type(raw) is not bytes or not 104 <= len(raw) <= MAX_BODY_BYTES:
        raise ValueError('Expected bounded synthetic News buffer')
    if type(article_index) is not int or not 0 <= article_index < 4096:
        raise ValueError('Expected bounded synthetic article index')
    expected_values = [expected_title]
    if expected_source_name is not None:
        expected_values.append(expected_source_name)
    for value in expected_values:
        if type(value) is not str or '\0' in value or len(value) > MAX_BODY_BYTES // 2:
            raise ValueError('Expected bounded explicit synthetic text')
        try:
            value.encode('utf-16-be')
        except UnicodeError:
            raise ValueError('Expected valid explicit synthetic text') from None
    count, offset = struct.unpack_from('>II', raw, 60)
    if (count > 4096 or article_index >= count or offset < 104
            or count * 44 > len(raw) - offset):
        raise ValueError('Synthetic article table is outside input bounds')
    article_offset = offset + article_index * 44
    identifier = struct.unpack_from('>I', raw, article_offset)[0]
    title_offset = struct.unpack_from('>I', raw, article_offset + 32)[0]
    ticker_count, ticker_offset = struct.unpack_from('>II', raw, 96)

    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC

    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, position, address, size in sections(source):
        cpu.mem_write(address, source[position:position + size])
    body, link, model = 0x81000000, 0x81100000, 0x81101000
    heap_start, heap_end = 0x81200000, 0x81300000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'H' * 32
    fixed = ((body, len(raw)), (link, 8), (model, 100), (stack_lo, stack_hi - stack_lo))
    for address, size in fixed:
        cpu.mem_write(address - 32, guard)
        cpu.mem_write(address + size, guard)
    cpu.mem_write(body, raw)
    cpu.mem_write(link, struct.pack('>II', struct.unpack_from('>I', raw, 12)[0], identifier))
    cpu.mem_write(model, b'\xDD' * 100)
    allocations = []
    cursor = heap_start
    counts = {'instructions': 0, 'allocations': 0, 'native_wcslen_calls': 0,
              'native_wcscpy_calls': 0, 'native_wcscat_calls': 0,
              'ticker_header_reads': 0, 'ticker_table_reads': 0}

    def code(_cpu, address, _size, _context):
        nonlocal cursor
        counts['instructions'] += 1
        if address == 0x80040A48:
            size = cpu.reg_read(UC_PPC_REG_0 + 3)
            if not 0 < size <= MAX_BODY_BYTES or len(allocations) >= 4:
                raise ValueError('Unexpected News display-model allocation')
            pointer = (cursor + 63) & ~31
            if pointer + size + 32 > heap_end:
                raise ValueError('Synthetic News display-model heap exhausted')
            cpu.mem_write(pointer - 32, guard)
            cpu.mem_write(pointer, b'\xDD' * size)
            cpu.mem_write(pointer + size, guard)
            allocations.append((pointer, size))
            cursor = pointer + size + 32
            counts['allocations'] += 1
            cpu.reg_write(UC_PPC_REG_0 + 3, pointer)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        allowed = ((ENTRY, 0x8000FD00), (0x801881BC, 0x80188264))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError('Unexpected native News display-model control flow')
        for entry, name in ((0x801881BC, 'native_wcslen_calls'),
                            (0x801881D8, 'native_wcscpy_calls'),
                            (0x80188238, 'native_wcscat_calls')):
            if address == entry:
                counts[name] += 1

    def read(_cpu, _access, address, size, _value, _context):
        allowed = [(body, body + len(raw)), (link, link + 8), (model, model + 100),
                   (stack_lo, stack_hi), (0x803567D0, 0x803567D4)]
        allowed.extend((pointer, pointer + length) for pointer, length in allocations)
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Native News display-model read exceeds fixture bounds')
        if address < body + 104 and address + size > body + 96:
            counts['ticker_header_reads'] += 1
        if (ticker_count and ticker_offset >= 104
                and ticker_count * 8 <= len(raw) - ticker_offset
                and address < body + ticker_offset + ticker_count * 8
                and address + size > body + ticker_offset):
            counts['ticker_table_reads'] += 1

    def write(_cpu, _access, address, size, _value, _context):
        allowed = [(model, model + 100), (stack_lo, stack_hi)]
        allowed.extend((pointer, pointer + length) for pointer, length in allocations)
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError('Unexpected native News display-model write')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for register, value in {1: stack, 2: 0x80360460, 13: 0x8035E740,
                            3: model, 4: body, 5: link, 6: 0, 7: 0, 8: 1}.items():
        cpu.reg_write(UC_PPC_REG_0 + register, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(ENTRY, stop, count=MAX_INSTRUCTIONS)
    if cpu.reg_read(UC_PPC_REG_PC) != stop or cpu.reg_read(UC_PPC_REG_0 + 3) != model:
        raise ValueError('Native News display-model constructor did not finish')
    for address, size in list(fixed) + allocations:
        if (bytes(cpu.mem_read(address - 32, 32)) != guard
                or bytes(cpu.mem_read(address + size, 32)) != guard):
            raise ValueError('Native News display-model fixture guard changed')
    if bytes(cpu.mem_read(body, len(raw))) != raw:
        raise ValueError('Native News display-model input changed')
    word = lambda position: struct.unpack('>I', cpu.mem_read(model + position, 4))[0]
    if word(0x10) != body + article_offset or word(0x20) != body + title_offset:
        raise ValueError('Native News display-model article/title reference mismatch')
    expected = expected_title
    if expected_source_name is not None:
        expected += ' ' + expected_source_name  # Original pinned UTF-16 separator.
    encoded = expected.encode('utf-16-be') + bytes(2)
    display = word(0x34)
    allocation = next((size for pointer, size in allocations if pointer == display), None)
    if (allocation is None or len(encoded) > allocation
            or bytes(cpu.mem_read(display, len(encoded))) != encoded):
        raise ValueError('Native News display text differs from explicit expectation')
    return {'constructor_finished': True, 'exact_display_text_verified': True,
            'article_title_reference_verified': True,
            'source_name_appended': expected_source_name is not None,
            'counts': counts, 'input_and_output_guards_verified': True,
            'allocation_service_stubbed': True, 'native_constructor_or_strings_stubbed': False,
            'ticker_table_consumer_verified': False,
            'buffer_validation_signatures_delivery_or_rendering_verified': False}
