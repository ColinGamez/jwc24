"""Full original CMOC event-2/event-4 dispatcher on guarded synthetic RAM."""
import hashlib
import struct

from jwc24.cmoc_callback import CallbackState, process_body_event, finish_callback
from tools.verify_cmoc_framing import SOURCE_SHA256


def verify_callback_lifecycle(source, *, initial_state, initial_wire_storage, events):
    if (type(source) is not bytes or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    if type(initial_state) is not CallbackState or type(initial_wire_storage) is not bytes or len(initial_wire_storage) > 0x440:
        raise ValueError('Expected explicit initial CMOC callback storage')
    if type(events) is not tuple or not 1 <= len(events) <= 8:
        raise ValueError('Expected bounded explicit CMOC callback event sequence')
    expected = []
    state = initial_state
    for event in events:
        if type(event) is not dict or event.get('kind') not in ('body', 'finish'):
            raise ValueError('Invalid CMOC callback event')
        args = {k: v for k, v in event.items() if k != 'kind'}
        step = process_body_event(state, **args) if event['kind'] == 'body' else finish_callback(state, **args)
        expected.append(step)
        state = step.state
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    worker, descriptor = 0x81000000, 0x81100000
    wire_base, intermediate_base, decoded_base = worker + 0x298, worker + 0x6DC, worker + 0xAE0
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'CMOC-CALLBACK-GUARD' * 2
    cpu.mem_write(worker - len(guard), guard)
    cpu.mem_write(worker, bytes(0x30AE0))
    cpu.mem_write(worker + 0x30AE0, guard)
    cpu.mem_write(descriptor - len(guard), guard)
    cpu.mem_write(descriptor + 12, guard)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_hi, guard)

    def word(address, value):
        cpu.mem_write(address, struct.pack('>I', value))

    def getword(address):
        return struct.unpack('>I', bytes(cpu.mem_read(address, 4)))[0]

    word(worker + 0xC8, initial_state.hash_span_size)
    cpu.mem_write(worker + 0xCC, bytes([initial_state.hash_enabled]))
    cpu.mem_write(worker + 0x208, bytes([initial_state.response_flags]))
    for offset, value in ((0x20C, initial_state.expected_wire_prefix),
                          (0x250, initial_state.expected_cached_prefix),
                          (0xADC, initial_state.decoded_body)):
        word(worker + offset, len(value))
        cpu.mem_write(worker + offset + 4, value)
    immutable = ((worker + 0xC8, bytes(cpu.mem_read(worker + 0xC8, 5))),
                 (worker + 0x20C, bytes(cpu.mem_read(worker + 0x20C, 4 + len(initial_state.expected_wire_prefix)))),
                 (worker + 0x250, bytes(cpu.mem_read(worker + 0x250, 4 + len(initial_state.expected_cached_prefix)))))
    live = {'wire': initial_wire_storage, 'body': initial_state.decoded_body,
            'intermediate': b'', 'event': None, 'step': None}
    cpu.mem_write(wire_base, initial_wire_storage)
    counts = dict(instructions=0, dispatches=0, body_callbacks=0, finalizers=0,
                  native_prefix_comparisons=0, hash_update_boundaries=0,
                  cipher_boundaries=0, decompressor_boundaries=0,
                  digest_boundaries=0, sdk_context_boundaries=0)

    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0 + n)

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _ctx):
        counts['instructions'] += 1
        for target, label in ((0x8007F3F0, 'dispatches'), (0x8007F468, 'body_callbacks'),
                              (0x8007F720, 'finalizers'), (0x800D9EB8, 'native_prefix_comparisons')):
            if address == target:
                counts[label] += 1
        if address == 0x8019CC44:
            counts['sdk_context_boundaries'] += 1
            ret(worker)
        elif address == 0x8007A0A4:
            counts['hash_update_boundaries'] += 1
            offset = initial_state.hash_span_size + len(initial_state.expected_wire_prefix)
            size = live['step'].padded_transform_size
            if reg(3) != worker or reg(4) != wire_base + offset or reg(5) != size:
                raise ValueError('Unexpected configured CMOC hash-update arguments')
            ret(size)
        elif address == 0x80069388:
            counts['cipher_boundaries'] += 1
            offset = initial_state.hash_span_size + len(initial_state.expected_wire_prefix)
            size = live['step'].padded_transform_size
            if (reg(3) != worker + 0xD0 or reg(4) != intermediate_base
                    or reg(5) != wire_base + offset or reg(6) != size):
                raise ValueError('Unexpected configured CMOC cipher arguments')
            live['intermediate'] = live['wire'][offset:offset + size]
            cpu.mem_write(intermediate_base, live['intermediate'])
            ret(size)  # Explicit synthetic identity intermediate, not decryption.
        elif address == 0x800694EC:
            counts['decompressor_boundaries'] += 1
            if (reg(3) != worker + 0x1E0 or reg(4) != intermediate_base
                    or reg(5) != len(live['intermediate'])):
                raise ValueError('Unexpected configured CMOC decompressor arguments')
            chunk = live['event']['decoded_chunk']
            cpu.mem_write(decoded_base + len(live['body']), chunk)
            live['body'] += chunk
            ret(len(chunk))
        elif address == 0x8007A0E8:
            counts['digest_boundaries'] += 1
            offset = len(initial_state.expected_wire_prefix)
            if (reg(3) != worker or reg(4) != wire_base + offset
                    or offset + initial_state.hash_span_size > len(live['wire'])):
                raise ValueError('Digest boundary lacks explicit CMOC backing bytes')
            ret(int(live['event']['digest_matches']))
        else:
            allowed = ((0x8007F28C, 0x8007F2A8), (0x8007F3F0, 0x8007F7E0),
                       (0x800730A4, 0x800730AC), (0x800D9EB8, 0x800D9F04))
            if not any(lo <= address < hi for lo, hi in allowed):
                raise ValueError(f'Unexpected CMOC callback control flow at {address:#x}')

    def read(_cpu, _access, address, size, _value, _ctx):
        allowed = [(p, p + len(v)) for p, v in immutable]
        allowed += [(worker + 0x208, worker + 0x209), (worker + 0x294, wire_base + len(live['wire'])),
                    (worker + 0x6D8, intermediate_base + len(live['intermediate'])),
                    (worker + 0xADC, decoded_base + len(live['body'])),
                    (descriptor, descriptor + 12), (stack_lo, stack_hi)]
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'CMOC callback read lacks captured backing at {address:#x}')

    def write(_cpu, _access, address, size, _value, _ctx):
        allowed = ((worker + 0x208, worker + 0x209), (worker + 0x6D8, worker + 0x6DC),
                   (worker + 0xADC, worker + 0xAE0), (descriptor, descriptor + 12),
                   (stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC callback write at {address:#x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    outputs = []
    for event, step in zip(events, expected):
        live.update(event=event, step=step)
        old_flags = cpu.mem_read(worker + 0x208, 1)[0]
        if event['kind'] == 'body':
            live['wire'] = event['wire_storage']
            cpu.mem_write(wire_base, live['wire'])
            if old_flags & 0x80:
                live['body'] = event['raw_body']
                cpu.mem_write(decoded_base, live['body'])
            cpu.mem_write(descriptor, struct.pack('>III',
                          decoded_base if old_flags & 0x80 else wire_base,
                          0x30000 if old_flags & 0x80 else 0x400,
                          event['receive_end_offset']))
        descriptor_before = bytes(cpu.mem_read(descriptor, 12))
        for n, value in {1: stack, 2: 0x80435BE0, 13: 0x80432BA0,
                         3: 77, 4: 2 if event['kind'] == 'body' else 4, 5: descriptor}.items():
            cpu.reg_write(UC_PPC_REG_0 + n, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(0x8007F3F0, stop, count=20000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop or cpu.reg_read(UC_PPC_REG_0 + 3) != 0:
            raise ValueError('CMOC callback instruction cap or dispatcher return mismatch')
        if (cpu.mem_read(worker + 0x208, 1)[0] != step.state.response_flags
                or getword(worker + 0xADC) != len(step.state.decoded_body)
                or bytes(cpu.mem_read(decoded_base, len(step.state.decoded_body))) != step.state.decoded_body):
            raise ValueError('Original CMOC callback differs from independent projection')
        wanted_descriptor = descriptor_before
        if event['kind'] == 'body' and not old_flags & 0x80:
            offset = initial_state.hash_span_size + len(initial_state.expected_wire_prefix)
            wanted_descriptor = struct.pack('>III', wire_base + offset, 0x400, 0)
        if bytes(cpu.mem_read(descriptor, 12)) != wanted_descriptor:
            raise ValueError('CMOC callback SDK descriptor mutation differs')
        for pointer, value in immutable:
            if bytes(cpu.mem_read(pointer, len(value))) != value:
                raise ValueError('CMOC callback immutable input changed')
        for pointer in (worker - len(guard), worker + 0x30AE0,
                        descriptor - len(guard), descriptor + 12,
                        stack_lo - len(guard), stack_hi):
            if bytes(cpu.mem_read(pointer, len(guard))) != guard:
                raise ValueError('CMOC callback object/stack guards changed')
        outputs.append(step.metadata())
    return dict(events=outputs, counts=counts,
                complete_original_dispatcher_body_and_finalizer_selected=True,
                native_prefix_comparison_stubbed=False,
                configured_transform_and_digest_boundaries_mocked=True,
                input_backing_and_stack_guards_verified=True,
                network_or_profile_access=False,
                cryptography_or_authentication_verified=False)
