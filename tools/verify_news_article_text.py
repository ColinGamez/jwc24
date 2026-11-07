"""Guarded HAGJ article text-pointer handoff and original UTF-16 glyph setup.

This executes no renderer, hyperlink action, provider story or console profile.
The layout suffix uses explicit synthetic register context; font metrics and
layout-to-formatter calls are observed boundaries, not native UI verification.
"""
from __future__ import annotations

import hashlib
import struct

SOURCE_SHA256 = "8c7328c94ed44f916f104e254d07eddbaed7c0f236539a4fe4e70d893b72e852"
MAX_RAW_BYTES = 65536
MAX_TEXT_UNITS = 4096


def verify_news_article_text(source, raw, *, expected_title, expected_body,
                             expected_source_name, expected_copyright,
                             glyph_width, font_height, glyph_capacity=None):
    """Compare explicit synthetic plain text against original pointer/unit paths.

    Full constructor runs. The selected article-layout suffix and formatter
    prefix/character loop are bounded original regions, not whole UI methods.
    Font metrics are explicit synthetic integers; they prove no font appearance.
    """
    if (type(source) is not bytes or len(source) > 4 * 1024 * 1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError("Japanese News v7 executable fingerprint mismatch")
    if type(raw) is not bytes or not 104 <= len(raw) <= MAX_RAW_BYTES:
        raise ValueError("Bounded synthetic News buffer required")
    for value in (expected_title, expected_body, expected_source_name, expected_copyright):
        if value is None:
            continue
        if type(value) is not str or "\0" in value:
            raise ValueError("Explicit bounded synthetic text required")
        try:
            encoded = value.encode("utf-16-be")
        except UnicodeError:
            raise ValueError("Valid synthetic UTF-16 text required") from None
        if len(encoded) // 2 > MAX_TEXT_UNITS:
            raise ValueError("Synthetic text exceeds harness bound")
    if expected_title is None or expected_body is None:
        raise ValueError("Explicit synthetic title and body required")
    if (expected_source_name is None) != (expected_copyright is None):
        raise ValueError("Source name and copyright expectations must agree on absence")
    if any(type(value) is not int or not 1 <= value <= 1024 for value in (glyph_width, font_height)):
        raise ValueError("Explicit bounded synthetic font metrics required")
    body_bytes = expected_body.encode("utf-16-be")
    units = len(body_bytes) // 2
    capacity = units + 1 if glyph_capacity is None else glyph_capacity
    if type(capacity) is not int or not 1 <= capacity <= MAX_TEXT_UNITS + 1:
        raise ValueError("Bounded synthetic glyph capacity required")
    count, offset = struct.unpack_from(">II", raw, 60)
    if count != 1 or offset < 104 or offset + 44 > len(raw):
        raise ValueError("Harness requires one bounded explicit article")
    source_index = struct.unpack_from(">I", raw, offset + 4)[0]
    source_count, source_offset = struct.unpack_from(">II", raw, 68)
    if source_index != 0xFFFFFFFF and (source_index >= source_count or source_offset < 104
                                      or source_offset + source_count * 28 > len(raw)):
        raise ValueError("Synthetic source table outside bounds")
    if (source_index == 0xFFFFFFFF) != (expected_source_name is None):
        raise ValueError("Synthetic source selection differs from explicit expectation")

    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC, UC_PPC_REG_FPR0, UC_PPC_REG_MSR

    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.reg_write(UC_PPC_REG_MSR, cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
    cpu.mem_map(0x80000000, 0x1800000)
    original_ranges = []
    for _, position, address, size in sections(source):
        cpu.mem_write(address, source[position:position + size])
        original_ranges.append((address, address + size))
    raw_base, link, model = 0x81000000, 0x81100000, 0x81101000
    heap_start, heap_end = 0x81200000, 0x81300000
    title_object, body_object, credit_object = 0x81310000, 0x81310200, 0x81310400
    glyphs, font, vtable, position = 0x81400000, 0x81510000, 0x81511000, 0x81512000
    width_call, height_call = 0x817FE100, 0x817FE200
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b"N" * 32
    fixed = [(raw_base, len(raw)), (link, 8), (model, 100), (stack_lo, stack_hi - stack_lo),
             (title_object, 0xD0), (body_object, 0xD0), (credit_object, 0xD0),
             (glyphs, capacity * 0x70), (font, 4), (vtable, 0x50), (position, 8),
             (0x8035E740 - 0x71D8, 12), (0x8035E740 - 0x7214, 4),
             (0x8035E740 - 0x709A, 1), (0x8035E740 - 0x7174, 4)]
    for address, size in fixed:
        cpu.mem_write(address - 32, guard)
        cpu.mem_write(address, bytes(size))
        cpu.mem_write(address + size, guard)
    cpu.mem_write(raw_base, raw)
    cpu.mem_write(link, struct.pack(">II", struct.unpack_from(">I", raw, 12)[0], struct.unpack_from(">I", raw, offset)[0]))
    allocations = []
    cursor = heap_start
    phase = "constructor"
    handoffs = []
    counts = dict(instructions=0, allocations=0, original_wcslen_calls=0,
                  glyph_unit_iterations=0, line_feed_dispatches=0,
                  nonbreaking_space_conversions=0, font_width_calls=0, font_height_calls=0)

    def word(address):
        return struct.unpack(">I", cpu.mem_read(address, 4))[0]

    def put(address, value):
        cpu.mem_write(address, struct.pack(">I", value))

    def reg(number, value=None):
        if value is None:
            return cpu.reg_read(UC_PPC_REG_0 + number)
        cpu.reg_write(UC_PPC_REG_0 + number, value)

    def code(_cpu, address, _size, _context):
        nonlocal cursor
        counts["instructions"] += 1
        if phase == "constructor" and address == 0x80040A48:
            size = reg(3)
            if not 0 < size <= MAX_RAW_BYTES or len(allocations) >= 4:
                raise ValueError("Unexpected original article allocation")
            pointer = (cursor + 63) & ~31
            if pointer + size + 32 > heap_end:
                raise ValueError("Synthetic article heap exhausted")
            cpu.mem_write(pointer - 32, guard)
            cpu.mem_write(pointer, bytes(size))
            cpu.mem_write(pointer + size, guard)
            allocations.append((pointer, size))
            cursor = pointer + size + 32
            counts["allocations"] += 1
            reg(3, pointer)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if phase == "handoff" and address == 0x80027F94:
            handoffs.append((reg(3), reg(4), reg(5)))
            reg(3, 1)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        if phase == "units" and address in (width_call, height_call):
            counts["font_width_calls" if address == width_call else "font_height_calls"] += 1
            reg(3, glyph_width if address == width_call else font_height)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        allowed = ({"constructor": ((0x8000FA38, 0x8000FD00), (0x801881BC, 0x80188264)),
                    "handoff": ((0x800331CC, 0x8003327C),),
                    "units": ((0x80028000, 0x80028250), (0x800278A0, 0x80027F94),
                              (0x801881BC, 0x801881D8))})[phase]
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError("Unexpected original article text control flow")
        if address == 0x801881BC:
            counts["original_wcslen_calls"] += 1
        if phase == "units":
            for at, name in ((0x800280D0, "glyph_unit_iterations"), (0x80028150, "line_feed_dispatches"),
                             (0x80028140, "nonbreaking_space_conversions")):
                if address == at:
                    counts[name] += 1

    def read(_cpu, _access, address, size, _value, _context):
        ranges = [(a, a + n) for a, n in fixed + allocations] + original_ranges
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError("Original article text read exceeds fixture bounds")

    def write(_cpu, _access, address, size, _value, _context):
        ranges = [(a, a + n) for a, n in fixed + allocations if a != raw_base]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError("Original article text write exceeds fixture bounds")

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    for number, value in {1: stack, 2: 0x80360460, 13: 0x8035E740,
                           3: model, 4: raw_base, 5: link, 6: 0, 7: 0, 8: 1}.items():
        reg(number, value)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.emu_start(0x8000FA38, stop, count=100000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop or reg(3) != model or word(model + 0x10) != raw_base + offset:
        raise ValueError("Original article constructor did not resolve selected record")
    title_pointer, body_pointer, copyright_pointer = (word(model + x) for x in (0x20, 0x24, 0x2C))
    expected_pointers = [raw_base + struct.unpack_from(">I", raw, offset + 32)[0],
                         raw_base + struct.unpack_from(">I", raw, offset + 40)[0],
                         (0 if source_index == 0xFFFFFFFF else raw_base + struct.unpack_from(
                             ">I", raw, source_offset + source_index * 28 + 24)[0])]
    if [title_pointer, body_pointer, copyright_pointer] != expected_pointers:
        raise ValueError("Original article title/body/copyright pointers differ from wire offsets")
    for pointer, expected in zip(expected_pointers, (expected_title, expected_body, expected_copyright)):
        if expected is None:
            continue
        encoded = expected.encode("utf-16-be") + bytes(2)
        if not raw_base <= pointer < pointer + len(encoded) <= raw_base + len(raw):
            raise ValueError("Explicit original text span outside synthetic input")
        if bytes(cpu.mem_read(pointer, len(encoded))) != encoded:
            raise ValueError("Original text pointer differs from explicit synthetic expectation")
    if expected_source_name is not None:
        pointer = word(model + 0x28)
        wire_name_pointer = raw_base + struct.unpack_from(
            ">I", raw, source_offset + source_index * 28 + 16)[0]
        if pointer != wire_name_pointer:
            raise ValueError("Original source name pointer differs from its wire source row")
        encoded = expected_source_name.encode("utf-16-be") + bytes(2)
        if not raw_base <= pointer < pointer + len(encoded) <= raw_base + len(raw) or bytes(cpu.mem_read(pointer, len(encoded))) != encoded:
            raise ValueError("Original source name pointer differs from explicit expectation")

    # Execute the actual three-call article layout suffix with explicit synthetic
    # text objects, registers and floats. Do not execute its broader UI caller.
    phase = "handoff"
    for displacement, pointer in ((-0x71D8, title_object), (-0x71D4, body_object), (-0x71D0, credit_object)):
        put(0x8035E740 + displacement, pointer)
    for number, value in {24: model, 25: 0, 26: position, 27: position, 28: position,
                           29: position, 30: 0, 31: 0}.items():
        reg(number, value)
    cpu.reg_write(UC_PPC_REG_FPR0 + 31, struct.unpack(">Q", struct.pack(">d", 1.0))[0])
    cpu.emu_start(0x800331CC, 0x8003327C, count=10000)
    expected_handoffs = [(title_object, title_pointer, 0), (body_object, body_pointer, 0),
                         (credit_object, copyright_pointer, 0)]
    if cpu.reg_read(UC_PPC_REG_PC) != 0x8003327C or handoffs != expected_handoffs:
        raise ValueError("Original article layout suffix text handoff mismatch")

    # Run original formatter pointer/length setup, every UTF-16 unit, original
    # grouping helper, LF and NBSP branches, and final zero-unit row. Broader
    # layout/width aggregation and actual font methods are outside this scope.
    phase = "units"
    put(body_object + 8, font)
    put(body_object + 12, glyphs)
    put(body_object + 0x98, capacity)
    put(font, vtable)
    put(vtable + 0x48, width_call)
    put(vtable + 0x10, height_call)
    cpu.mem_write(0x8035E740 - 0x709A, bytes(1))  # Explicit synthetic grouping mode.
    for number, value in {0: 0, 3: body_object, 4: body_pointer, 5: 0, 9: position,
                           19: 0, 20: body_object, 21: 0, 26: 0}.items():
        reg(number, value)
    for number in (2, 31):
        cpu.reg_write(UC_PPC_REG_FPR0 + number, struct.unpack(">Q", struct.pack(">d", 1.0))[0])
    cpu.emu_start(0x80028000, 0x80028250, count=8000000)
    if cpu.reg_read(UC_PPC_REG_PC) != 0x80028250 or counts["glyph_unit_iterations"] != units:
        raise ValueError("Original UTF-16 unit walk did not finish")
    actual_units = b"".join(bytes(cpu.mem_read(glyphs + index * 0x70, 2)) for index in range(units + 1))
    expected_units = expected_body.replace("\u00a0", " ").encode("utf-16-be") + bytes(2)
    if actual_units != expected_units or word(body_object + 0x14) != body_pointer or word(body_object + 0x9C) != units + 1:
        raise ValueError("Original UTF-16 glyph rows differ from explicit expectation")
    for address, size in fixed + allocations:
        if bytes(cpu.mem_read(address - 32, 32)) != guard or bytes(cpu.mem_read(address + size, 32)) != guard:
            raise ValueError("Original article text fixture guard changed")
    if bytes(cpu.mem_read(raw_base, len(raw))) != raw:
        raise ValueError("Synthetic article input changed")
    return dict(complete_constructor_finished=True, title_body_copyright_wire_pointers_verified=True,
                three_original_layout_suffix_handoffs_verified=True,
                original_formatter_prefix_and_utf16_unit_walk_verified=True,
                exact_units_except_original_nbsp_conversion_verified=True, counts=counts,
                fixture_guards_and_unchanged_input_verified=True,
                allocation_and_font_metric_services_mocked=True, layout_formatter_calls_observed_not_executed=True,
                complete_ui_or_formatter_method_executed=False, real_font_metrics_or_rendering_verified=False,
                literal_url_clickability_verified=False, html_or_rich_article_support_verified=False,
                provider_attribution_or_rights_compliance_verified=False,
                signature_or_delivery_or_profile_execution_verified=False)
