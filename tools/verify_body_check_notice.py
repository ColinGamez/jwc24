"""Bound original HFNJ gate/transition/message selection and private BMG lookup.

No renderer, asynchronous service or device operation is run. Private original
resources stay in memory and reports contain only hashes, counts and scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jwc24.body_check_completion import evaluate_header_pair_gate
from jwc24.body_check_notice import (BodyCheckNoticeUnsupported, NoticeContext,
                                     UPDATE_NOTICE_MESSAGE_ID, plan_header_notice)
from tools.verify_body_check_completion import _cpu
from tools.verify_body_check_header_crc import SOURCE_BYTES, SOURCE_SHA256

BMG_BYTES = 24160
BMG_SHA256 = '22049c1e62a52e1d0d6ba3000aca6d4c07aed50128a476ee1818bc6e784a7b27'
WAD_BYTES = 19900928
WAD_SHA256 = 'e5801c74cfaad8e52c47b0b7ba043b3b75ee05e8ccd995264ba9840a7f7da245'
CONTENT_SHA256 = '7dd4a3bdf7e7f4968798217e358317b798564f84d34c5ae08cd953fe1d62f5a5'
CARC_SHA256 = 'f0692bf83490827182fe9122ab3b7011e6f855041980b47b654955390b4bf202'


def _identity(data, size, digest):
    if type(data) is not bytes or len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Body Check notice input fingerprint differs')


def fixture_context(**changes):
    values = dict(gate_context_word8=0, secondary_context_word8=0,
                  manager_latched_flag=False, transition_dialog_busy=False,
                  advance_selector=True, selector_dialog_busy=False)
    values.update(changes)
    return NoticeContext(**values)


def verify_notice_path(source, first_u16, second_u16, *, context):
    """Execute the complete selected caller and an explicit later selector phase.

    UI request/close and secondary asynchronous-entry calls are intercepted.
    The separate alternate context/error handler is observed only as a selected
    boundary and remains unsupported by the independent inspection handoff.
    """
    gate = evaluate_header_pair_gate(first_u16, second_u16)
    try:
        expected = plan_header_notice(gate, context=context)
    except BodyCheckNoticeUnsupported:
        expected = None
    cpu = _cpu(source)
    from tools.inspect_demae_references import sections
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    reg0, lr, pc = UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    obj, manager, gate_ctx, secondary, dialog, messages, data = (
        0x81000000, 0x81001000, 0x81002000, 0x81003000, 0x81004000, 0x81005000, 0x81006000)
    stack_lo, stack_hi, stack, stop, sda = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000, 0x805A0840
    guard = b'N' * 32
    state = bytearray(0x94)
    struct.pack_into('>I', state, 0, 0x803E8628)
    struct.pack_into('>I', state, 0x44, 0x17)  # Explicit synthetic prior state, not a restored screen.
    for offset, value in ((0x4C, gate_ctx), (0x50, dialog), (0x58, messages)):
        struct.pack_into('>I', state, offset, value)
    manager_bytes = bytearray(0x68)
    struct.pack_into('>I', manager_bytes, 0, 0x803E88B8)
    manager_bytes[0x20] = int(context.manager_latched_flag)
    gate_bytes, secondary_bytes, dialog_bytes = bytearray(12), bytearray(12), bytearray(0x98)
    struct.pack_into('>I', gate_bytes, 8, context.gate_context_word8)
    struct.pack_into('>I', secondary_bytes, 8, context.secondary_context_word8)
    struct.pack_into('>I', dialog_bytes, 0x90, int(context.transition_dialog_busy))
    raw_data = b'OBJ!' + bytes(12) + struct.pack('>HH', first_u16, second_u16)
    objects = {obj: bytes(state), manager: bytes(manager_bytes), gate_ctx: bytes(gate_bytes),
               secondary: bytes(secondary_bytes), dialog: bytes(dialog_bytes),
               messages: bytes(32), data: raw_data}
    for pointer, value in objects.items():
        cpu.mem_write(pointer - 32, guard); cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
    globals_ = {sda - 0x5DF0: struct.pack('>I', manager), sda - 0x6020: struct.pack('>I', secondary),
                sda - 0x6028: struct.pack('>I', data)}
    for pointer, value in globals_.items():
        cpu.mem_write(pointer, value)
    cpu.mem_write(stack_lo - 32, guard); cpu.mem_write(stack_hi, guard)
    counts = {'instructions': 0, 'original_pair_gate': 0, 'original_transition': 0,
              'original_selector': 0, 'original_message_request': 0,
              'ui_message_boundary': 0, 'ui_close_boundary': 0,
              'secondary_async_boundary': 0, 'alternate_handler_boundary': 0}
    reads = set()
    native_message = None

    def reg(index):
        return cpu.reg_read(reg0 + index)

    def ret():
        cpu.reg_write(reg0 + 3, 0)
        cpu.reg_write(pc, cpu.reg_read(lr))

    def code(_cpu, address, _size, _context):
        nonlocal native_message
        counts['instructions'] += 1
        entries = {0x802BBB10: 'original_pair_gate', 0x802B6880: 'original_transition',
                   0x802B6DE8: 'original_selector', 0x802B8920: 'original_message_request'}
        if address in entries:
            counts[entries[address]] += 1
        if address == 0x802478FC:
            if (reg(3), reg(4), reg(6)) != (dialog, 0, messages):
                raise ValueError('Unexpected original notice message arguments')
            native_message = reg(5), reg(7)
            counts['ui_message_boundary'] += 1
            ret(); return
        if address == 0x802476F0:
            if reg(3) != dialog:
                raise ValueError('Unexpected original dialog-close object')
            counts['ui_close_boundary'] += 1
            ret(); return
        if address == 0x80230DA8:
            if reg(3) != secondary:
                raise ValueError('Unexpected original secondary-context object')
            counts['secondary_async_boundary'] += 1
            ret(); return
        if address == 0x802B6520:
            if reg(3) != obj:
                raise ValueError('Unexpected original alternate-handler object')
            counts['alternate_handler_boundary'] += 1
            ret(); return
        allowed = ((0x802B63B0, 0x802B6470), (0x802B6880, 0x802B68B4),
                   (0x802B67D8, 0x802B67E8), (0x802B6DE8, 0x802B7200),
                   (0x802B8920, 0x802B8948), (0x802BBB10, 0x802BBB90),
                   (0x802BE1D0, 0x802BE1D8), (0x80230974, 0x80230994),
                   (0x80230A14, 0x80230A34), (0x80004000, 0x8000429C))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError('Unexpected original notice control flow')

    static = [(base, base + size) for index, _, base, size in sections(source) if index >= 7]

    def read(_cpu, _access, address, size, _value, _context):
        if data <= address < address + size <= data + len(raw_data):
            if not data + 16 <= address < address + size <= data + 20:
                raise ValueError('Original notice path read beyond its opaque pair')
            reads.update(range(address - data - 4, address + size - data - 4))
        ranges = [(pointer, pointer + len(value)) for pointer, value in objects.items()]
        ranges += [(pointer, pointer + len(value)) for pointer, value in globals_.items()]
        ranges += static + [(stack_lo, stack_hi)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError('Original notice read exceeds fixture/static bounds')

    def write(_cpu, _access, address, size, _value, _context):
        if not (stack_lo <= address < address + size <= stack_hi
                or obj + 0x44 <= address < address + size <= obj + 0x48
                or obj + 0x70 <= address < address + size <= obj + 0x78):
            raise ValueError('Unexpected original notice state write')

    hooks = [cpu.hook_add(UC_HOOK_CODE, code), cpu.hook_add(UC_HOOK_MEM_READ, read),
             cpu.hook_add(UC_HOOK_MEM_WRITE, write)]

    def run(entry):
        for index, value in {1: stack, 2: 0x805A2B20, 13: sda, 3: obj}.items():
            cpu.reg_write(reg0 + index, value)
        cpu.reg_write(lr, stop)
        cpu.emu_start(entry, stop, count=20000, timeout=500000)
        if cpu.reg_read(pc) != stop:
            raise ValueError('Original notice instruction/runtime budget exceeded')

    run(0x802B63B0)
    if expected is not None and gate and expected.header_gate_evaluated and context.advance_selector:
        struct.pack_into('>I', dialog_bytes, 0x90, int(context.selector_dialog_busy))
        cpu.mem_write(dialog, bytes(dialog_bytes))
        objects[dialog] = bytes(dialog_bytes)  # Explicit independent later-phase fixture sample.
        run(0x802B6DE8)
    if expected is None:
        if counts['alternate_handler_boundary'] != 1 or reads:
            raise ValueError('Original alternate notice path differs from explicit unsupported scope')
    else:
        if expected.next_state is not None:
            struct.pack_into('>I', state, 0x44, expected.next_state)
        if expected.selector is not None:
            struct.pack_into('>II', state, 0x70, expected.selector, expected.control)
        if (counts['original_pair_gate'] != int(expected.header_gate_evaluated)
                or reads != ({12, 13, 14, 15} if expected.header_gate_evaluated else set())
                or counts['original_transition'] != int(expected.selector is not None)
                or counts['original_selector'] != int(expected.selector_advanced)
                or counts['ui_close_boundary'] != int(expected.dialog_close_requested)
                or counts['secondary_async_boundary'] != int(expected.secondary_context_call_requested)
                or native_message != (None if expected.message_id is None else
                                      (expected.message_id, expected.message_variant))):
            raise ValueError('Original notice decisions differ from independent handoff')
    objects[obj] = bytes(state)
    for pointer, value in objects.items():
        if (bytes(cpu.mem_read(pointer, len(value))) != value
                or bytes(cpu.mem_read(pointer - 32, 32)) != guard
                or bytes(cpu.mem_read(pointer + len(value), 32)) != guard):
            raise ValueError('Original notice input/state guard changed')
    if (bytes(cpu.mem_read(stack_lo - 32, 32)) != guard or bytes(cpu.mem_read(stack_hi, 32)) != guard
            or any(bytes(cpu.mem_read(pointer, len(value))) != value for pointer, value in globals_.items())):
        raise ValueError('Original notice stack/global guard changed')
    for hook in hooks:
        cpu.hook_del(hook)
    return {'counts': counts, 'independent_handoff_supported': expected is not None,
            'decision': expected.metadata() if expected is not None else None,
            'original_header_transition_selector_branches_stubbed': False,
            'ui_close_message_and_secondary_async_boundaries_mocked': True,
            'alternate_error_handler_executed': False,
            'immutable_input_state_stack_and_global_guards_verified': True,
            'original_ui_rendered': False, 'header_word_meanings_verified': False}


def verify_message_binding(source, bmg):
    """Run the original BMG constructor and lookup on a pinned private resource."""
    _identity(bmg, BMG_BYTES, BMG_SHA256)
    cpu = _cpu(source)
    from tools.inspect_demae_references import sections
    from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    reg0, lr, pc = UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    resource, obj, stack_lo, stack_hi, stack, stop = 0x81000000, 0x81100000, 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'M' * 32
    for pointer, value in ((resource, bmg), (obj, bytes(32))):
        cpu.mem_write(pointer - 32, guard); cpu.mem_write(pointer, value); cpu.mem_write(pointer + len(value), guard)
    cpu.mem_write(stack_lo - 32, guard); cpu.mem_write(stack_hi, guard)
    static = [(base, base + size) for index, _, base, size in sections(source) if index >= 7]
    instructions = 0

    def code(_cpu, address, _size, _context):
        nonlocal instructions
        instructions += 1
        if not (0x800C1ED4 <= address < 0x800C2210 or 0x8023522C <= address < 0x80235230):
            raise ValueError('Unexpected original BMG lookup control flow')

    def read(_cpu, _access, address, size, _value, _context):
        ranges = static + [(resource, resource + len(bmg)), (obj, obj + 32), (stack_lo, stack_hi)]
        if not any(lo <= address < address + size <= hi for lo, hi in ranges):
            raise ValueError('Original BMG lookup read exceeds pinned resource bounds')

    def write(_cpu, _access, address, size, _value, _context):
        if not (obj <= address < address + size <= obj + 32 or stack_lo <= address < address + size <= stack_hi):
            raise ValueError('Original BMG lookup changed an immutable input')

    hooks = [cpu.hook_add(UC_HOOK_CODE, code), cpu.hook_add(UC_HOOK_MEM_READ, read),
             cpu.hook_add(UC_HOOK_MEM_WRITE, write)]
    for entry, arguments in ((0x800C1ED4, (obj, resource)),
                             (0x8023522C, (obj, UPDATE_NOTICE_MESSAGE_ID, 0))):
        for index, value in {1: stack, 2: 0x805A2B20, 13: 0x805A0840}.items():
            cpu.reg_write(reg0 + index, value)
        for index, value in enumerate(arguments, 3):
            cpu.reg_write(reg0 + index, value)
        cpu.reg_write(lr, stop); cpu.emu_start(entry, stop, count=20000, timeout=500000)
        if cpu.reg_read(pc) != stop:
            raise ValueError('Original BMG lookup execution budget exceeded')
    # Independently parse the pinned MID/INF/DAT entry; publish no message text.
    count, stride = struct.unpack_from('>HH', bmg, 32 + 8)
    ids = struct.unpack_from('>' + str(count) + 'I', bmg, 22432 + 16)
    index = ids.index(UPDATE_NOTICE_MESSAGE_ID << 8)
    offset = struct.unpack_from('>I', bmg, 32 + 16 + index * stride)[0]
    expected_offset = 5152 + 8 + offset
    if cpu.reg_read(reg0 + 3) != resource + expected_offset:
        raise ValueError('Original BMG getter selected a different message record')
    if (bytes(cpu.mem_read(resource, len(bmg))) != bmg
            or any(bytes(cpu.mem_read(pointer - 32, 32)) != guard or
                   bytes(cpu.mem_read(pointer + size, 32)) != guard
                   for pointer, size in ((resource, len(bmg)), (obj, 32), (stack_lo, stack_hi - stack_lo)))):
        raise ValueError('Original BMG lookup guard or resource changed')
    for hook in hooks:
        cpu.hook_del(hook)
    return {'bmg_sha256': BMG_SHA256, 'bmg_bytes': BMG_BYTES, 'message_id': UPDATE_NOTICE_MESSAGE_ID,
            'variant': 0, 'selected_mid': UPDATE_NOTICE_MESSAGE_ID << 8,
            'selected_resource_offset': expected_offset, 'instructions': instructions,
            'original_bmg_constructor_and_getter_executed': True, 'lookup_or_service_boundaries_stubbed': False,
            'resource_and_guards_unchanged': True, 'message_text_published': False,
            'native_ui_rendered': False}


def _yaz0(data):
    if (type(data) is not bytes or not 16 <= len(data) <= 16384 or data[:4] != b'Yaz0'
            or struct.unpack_from('>I', data, 4)[0] != 30912):
        raise ValueError('Unexpected bounded message archive framing')
    result, cursor, flags, bits = bytearray(), 16, 0, 0
    while len(result) < 30912:
        if not bits:
            if cursor >= len(data): raise ValueError('Truncated message archive')
            flags, bits = data[cursor], 8; cursor += 1
        if flags & 0x80:
            if cursor >= len(data): raise ValueError('Truncated message archive')
            result.append(data[cursor]); cursor += 1
        else:
            if cursor + 2 > len(data): raise ValueError('Truncated message archive')
            pair = int.from_bytes(data[cursor:cursor + 2], 'big'); cursor += 2
            distance, length = (pair & 0xFFF) + 1, pair >> 12
            if not length:
                if cursor >= len(data): raise ValueError('Truncated message archive')
                length = data[cursor] + 0x12; cursor += 1
            else: length += 2
            if distance > len(result) or len(result) + length > 30912:
                raise ValueError('Message archive copy exceeds its bounds')
            for _ in range(length): result.append(result[-distance])
        flags <<= 1; bits -= 1
    return bytes(result)


def audit_message_membership(wad_bytes, bmg):
    """Verify exact resource membership from the pinned local WAD, in memory."""
    _identity(wad_bytes, WAD_BYTES, WAD_SHA256); _identity(bmg, BMG_BYTES, BMG_SHA256)
    from libWiiPy.title.wad import WAD
    from libWiiPy.title.ticket import Ticket
    from libWiiPy.title.tmd import TMD
    from libWiiPy.title.content import ContentRegion
    from libWiiPy.archive import U8Archive
    wad, ticket, tmd, region = WAD(), Ticket(), TMD(), ContentRegion()
    wad.load(wad_bytes); ticket.load(wad.get_ticket_data()); tmd.load(wad.get_tmd_data())
    if ticket.title_id.hex().upper() != '0001000148464E4A' or tmd.title_id.upper() != '0001000148464E4A' or tmd.title_version != 256:
        raise ValueError('Pinned message title identity differs')
    region.load(wad.get_content_data(), tmd.content_records)
    content = region.get_content_by_index(2, ticket.get_title_key())
    record = tmd.content_records[2]
    if (record.index != 2 or len(content) != record.content_size
            or hashlib.sha1(content).hexdigest() != record.content_hash.decode('ascii')
            or hashlib.sha256(content).hexdigest() != CONTENT_SHA256):
        raise ValueError('Message resource differs from pinned content/TMD')

    def member(archive, basename):
        if len(archive.file_name_list) > 10000:
            raise ValueError('Message archive member count exceeds bound')
        matches = [(name, value) for name, value in zip(archive.file_name_list, archive.file_data_list)
                   if PurePosixPath(name).name == basename]
        if len(matches) != 1 or PurePosixPath(matches[0][0]).is_absolute() or '..' in PurePosixPath(matches[0][0]).parts:
            raise ValueError('Exact message member is missing or ambiguous')
        return matches[0][1]

    outer = U8Archive(); outer.load(content)
    compressed = member(outer, 'message.carc')
    if len(compressed) != 11079 or hashlib.sha256(compressed).hexdigest() != CARC_SHA256:
        raise ValueError('Message archive differs from pinned member')
    archive = _yaz0(compressed)
    nested = U8Archive(); nested.load(archive)
    if member(nested, 'health_message.bmg') != bmg:
        raise ValueError('Retained BMG differs from the pinned archive member')
    return {'wad_sha256': WAD_SHA256, 'title_id': '0001000148464E4A', 'title_version': 256,
            'content_index': 2, 'content_sha256': CONTENT_SHA256, 'content_matches_tmd_hash_and_size': True,
            'message_carc_sha256': CARC_SHA256, 'message_archive_sha256': hashlib.sha256(archive).hexdigest(),
            'bmg_sha256': BMG_SHA256, 'exact_resource_membership_verified': True,
            'nintendo_signature_or_independent_archive_provenance_verified': False,
            'original_bytes_keys_or_message_text_published': False, 'profile_or_backup_modified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('message_bmg', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.source.open('rb') as stream: source = stream.read(SOURCE_BYTES + 1)
        with args.message_bmg.open('rb') as stream: bmg = stream.read(BMG_BYTES + 1)
        report = {'notice': verify_notice_path(source, 2, 0, context=fixture_context()),
                  'message_binding': verify_message_binding(source, bmg)}
    except (OSError, ValueError, ImportError):
        print('Body Check notice comparison input or optional dependency unavailable', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
