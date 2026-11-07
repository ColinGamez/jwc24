"""Actual configured CMOC callbacks with synthetic HMAC/AES/LZ composition.

The SDK's object lookup and IOS open/close are explicit synthetic boundaries.
No hash, cipher, decoder, prefix comparison or final comparison is replaced.
"""
import hashlib
import struct

from jwc24.cmoc_callback import CallbackState, process_body_event, finish_callback
from jwc24.cmoc_cipher import decrypt_aes_cbc
from jwc24.cmoc_compression import inspect_compression
from jwc24.cmoc_hash import inspect_application_hash
from tools.verify_cmoc_framing import SOURCE_SHA256


def verify_transform_pipeline(source, *, hash_key, cipher_key, iv, ciphertext_chunks,
                              receive_sizes, expected_digest, expected_wire_prefix,
                              wire_prefix, cached_prefix, decompression_enabled,
                              initial_flags=0):
    if (type(source) is not bytes or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    if (type(hash_key) is not bytes or len(hash_key) != 20
            or type(expected_digest) is not bytes or len(expected_digest) != 20
            or type(ciphertext_chunks) is not tuple or not 1 <= len(ciphertext_chunks) <= 4
            or any(type(c) is not bytes or not 16 <= len(c) <= 1024 or len(c) % 16
                   for c in ciphertext_chunks)
            or type(receive_sizes) is not tuple or len(receive_sizes) != len(ciphertext_chunks)
            or any(type(n) is not int or not 1 <= n <= len(c) or (n + 15) // 16 * 16 != len(c)
                   for n, c in zip(receive_sizes, ciphertext_chunks))
            or type(expected_wire_prefix) is not bytes or len(expected_wire_prefix) > 44
            or type(wire_prefix) is not bytes or len(wire_prefix) != len(expected_wire_prefix)
            or type(cached_prefix) is not bytes or len(cached_prefix) > 64
            or type(decompression_enabled) is not bool or type(initial_flags) is not int
            or not 0 <= initial_flags <= 255 or initial_flags & 0x80):
        raise ValueError('Expected bounded explicit configured CMOC transform inputs')
    plaintext = decrypt_aes_cbc(key=cipher_key, iv=iv, chunks=ciphertext_chunks)
    compression = inspect_compression(chunks=plaintext, enabled=decompression_enabled,
                                     output_limit=0, output_capacity=4096)
    if any(s.sdk_return is not None and s.sdk_return < 0
           or s.return_value != len(s.written) for s in compression.steps):
        raise ValueError('Composed CMOC probe requires nonnegative consistent decoder counts')
    hashed = inspect_application_hash(key=hash_key, key_size=20,
                                       chunks=ciphertext_chunks, expected=expected_digest)
    state = CallbackState(initial_flags, expected_wire_prefix, cached_prefix, b'', 20, True)
    frames, expected = [], []
    for cipher, received, decoded in zip(ciphertext_chunks, receive_sizes, compression.steps):
        frame = wire_prefix + expected_digest + cipher
        step = process_body_event(state, wire_storage=frame,
            receive_end_offset=len(wire_prefix) + 20 + received,
            decoded_chunk=decoded.written, raw_body=None)
        frames.append(frame)
        expected.append(step)
        state = step.state
    expected.append(finish_callback(state, digest_matches=hashed.native_match))
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    worker, descriptor = 0x81000000, 0x81100000
    hp, kp, vp = 0x81110000, 0x81120000, 0x81130000
    wire, intermediate, decoded = worker + 0x298, worker + 0x6DC, worker + 0xAE0
    slo, shi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    handle, bss = 0x8042B730, 0x80430770
    bss_start, bss_size = struct.unpack_from('>II', source, 0xD8)
    if not bss_start <= bss < bss + 8 <= bss_start + bss_size:
        raise ValueError('Original SHA1 padding span exceeds declared loader BSS')
    guard = b'CMOC-TRANSFORM-GUARD' * 2
    objects = []

    def put(pointer, value, mutable=False):
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
        objects.append((pointer, value, mutable))

    put(worker, bytes(0x1AE0), True)
    put(descriptor, bytes(12), True)
    for pointer, value in ((hp, hash_key), (kp, cipher_key), (vp, iv)):
        put(pointer, value)
    cpu.mem_write(slo - len(guard), guard)
    cpu.mem_write(slo, b'\xA5' * (shi - slo))
    cpu.mem_write(shi, guard)
    cpu.mem_write(decoded, b'\xA5' * 4096)
    cpu.mem_write(handle, b'\xFF' * 4)
    if bytes(cpu.mem_read(bss, 8)) != bytes(8):
        raise ValueError('Original SHA1 padding span is not loader zero backing')
    if bytes(cpu.mem_read(0x8042F000, 1)) != b'\x80':
        raise ValueError('Original SHA1 finalization byte differs from standard padding')

    def word(pointer, value):
        cpu.mem_write(pointer, struct.pack('>I', value))

    def getword(pointer):
        return int.from_bytes(cpu.mem_read(pointer, 4), 'big')

    counts = dict(instructions=0, dispatches=0, hash_updates=0, cipher_updates=0,
                  decompressor_updates=0, hash_finals=0, aes_blocks=0,
                  sha1_compressions=0, sdk_lookups=0, ios_opens=0, ios_closes=0)
    live = dict(event=None, frame=b'', digest=None, digest_pointer=None,
                native_hash_match=None, compared_digest_bytes=0,
                intermediate_writes=set(), decoded_writes=set(), current_decoded=set(),
                call_order=[])

    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0 + n)

    def ret(value):
        cpu.reg_write(UC_PPC_REG_0 + 3, value)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _ctx):
        counts['instructions'] += 1
        targets = ((0x8007F3F0, 'dispatches'), (0x8007A0A4, 'hash_updates'),
                   (0x80069388, 'cipher_updates'), (0x800694EC, 'decompressor_updates'),
                   (0x8007A0E8, 'hash_finals'), (0x80196890, 'aes_blocks'),
                   (0x801951F8, 'sha1_compressions'))
        for target, name in targets:
            if address == target:
                counts[name] += 1
        if address in (0x8007A0A4, 0x80069388, 0x800694EC):
            live['call_order'].append(address)
        if address == 0x8019CC44:
            counts['sdk_lookups'] += 1
            ret(worker)
            return
        if address in (0x8010DC0C, 0x8010DDEC):
            counts['ios_opens' if address == 0x8010DC0C else 'ios_closes'] += 1
            ret(7 if address == 0x8010DC0C else 0)
            return
        if address == 0x8007A124:
            pointer = reg(3)
            if not any(lo <= pointer < pointer + 20 <= hi
                       for lo, hi in ((worker, worker + 0x204), (slo, shi))):
                raise ValueError('Original digest snapshot lacks explicit mutable output backing')
            live['digest'] = bytes(cpu.mem_read(pointer, 20))
            live['digest_pointer'] = pointer
        if address == 0x8007F79C:
            live['native_hash_match'] = bool(reg(3))
        if live['event'] is not None:
            i = live['event']
            if address == 0x8007A0A4:
                if (reg(3), reg(4), reg(5)) != (worker, wire + 20 + len(wire_prefix), len(ciphertext_chunks[i])):
                    raise ValueError('Original callback hashes a different supplied wire span')
            elif address == 0x80069388:
                if (reg(3), reg(4), reg(5), reg(6)) != (worker + 0xD0, intermediate,
                    wire + 20 + len(wire_prefix), len(ciphertext_chunks[i])):
                    raise ValueError('Original callback cipher arguments differ')
            elif address == 0x8007F508:
                if (reg(3) != len(plaintext[i])
                        or live['intermediate_writes'] != set(range(len(plaintext[i])))
                        or bytes(cpu.mem_read(intermediate, len(plaintext[i]))) != plaintext[i]
                        or bytes(cpu.mem_read(intermediate + len(plaintext[i]), 1024 - len(plaintext[i])))
                           != b'\xA5' * (1024 - len(plaintext[i]))):
                    raise ValueError('Actual cipher bytes/write extent/return differ from AES-CBC')
            elif address == 0x800694EC:
                if (reg(3), reg(4), reg(5)) != (worker + 0x1E0, intermediate, len(plaintext[i])):
                    raise ValueError('Original callback decompressor arguments differ')
            elif address == 0x8007F53C and reg(3) != compression.steps[i].return_value:
                raise ValueError('Original callback decompressor count differs')
        allowed = ((0x80004000, 0x80004134), (0x8006924C, 0x800695D0),
                   (0x80079FF8, 0x8007A154), (0x8007F28C, 0x8007F2A8),
                   (0x8007F3F0, 0x8007F7E0), (0x800730A4, 0x800730AC),
                   (0x800D64D0, 0x800D6580), (0x800D9EB8, 0x800D9F04),
                   (0x800DE280, 0x800DE2C0), (0x80194FBC, 0x80195984),
                   (0x80195DFC, 0x80196924), (0x80177BE4, 0x80178014),
                   (0x801783D0, 0x80178410))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC transform control flow at {address:#x}')

    def read(_cpu, _access, address, size, _value, _ctx):
        pc = cpu.reg_read(UC_PPC_REG_PC)
        if pc == 0x80177F50 and not all(
                a - decoded in live['decoded_writes'] for a in range(address, address + size)):
            raise ValueError('Original LZ reference lacks actual decoded output history')
        start = live['digest_pointer']
        if start is not None and 0x800DE280 <= pc < 0x800DE2C0 and start <= address < start + 20:
            if address + size > start + 20:
                raise ValueError('Original digest comparison exceeds its actual backing')
            live['compared_digest_bytes'] += size
        allowed = [(hp, hp + len(hash_key)), (kp, kp + len(cipher_key)), (vp, vp + 16),
                   (worker, worker + 0x204), (worker + 0x208, worker + 0x209),
                   (worker + 0x20C, worker + 0x210 + len(expected_wire_prefix)),
                   (worker + 0x250, worker + 0x254 + len(cached_prefix)),
                   (worker + 0x294, wire + len(live['frame'])),
                   (worker + 0x6D8, intermediate), (worker + 0xADC, decoded),
                   (descriptor, descriptor + 12), (slo, shi), (handle, handle + 4),
                   (0x802DDB78, 0x802DDB94), (0x802DDB98, 0x802DDDB8),
                   (0x802DE1B8, 0x802DE5B8), (0x8042F000, 0x8042F001),
                   (0x8042F008, 0x8042F010), (bss, bss + 8)]
        if any(lo <= address < address + size <= hi for lo, hi in allowed):
            return
        if intermediate <= address < address + size <= intermediate + 1024:
            if all(a - intermediate in live['intermediate_writes'] for a in range(address, address + size)):
                return
        if decoded <= address < address + size <= decoded + 4096:
            if all(a - decoded in live['decoded_writes'] for a in range(address, address + size)):
                return
        raise ValueError(f'CMOC transform read lacks explicit backing at {address:#x}, PC {cpu.reg_read(UC_PPC_REG_PC):#x}')

    def write(_cpu, _access, address, size, _value, _ctx):
        allowed = ((worker, worker + 0x204), (worker + 0x208, worker + 0x209),
                   (worker + 0x6D8, intermediate), (worker + 0xADC, decoded),
                   (descriptor, descriptor + 12), (slo, shi), (handle, handle + 4))
        if intermediate <= address < address + size <= intermediate + 1024:
            live['intermediate_writes'].update(range(address - intermediate, address + size - intermediate))
            return
        if decoded <= address < address + size <= decoded + 4096:
            span = range(address - decoded, address + size - decoded)
            live['decoded_writes'].update(span)
            live['current_decoded'].update(span)
            return
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC transform write at {address:#x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def call(address, args):
        for n, value in {1: stack, 2: 0x80435BE0, 13: 0x80432BA0, **args}.items():
            cpu.reg_write(UC_PPC_REG_0 + n, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(address, stop, count=1000000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('CMOC transform instruction cap reached')
        return reg(3)

    hash_descriptor = call(0x801951EC, {})
    call(0x80079FF8, {3: worker, 4: hp, 5: 20, 6: hash_descriptor})
    call(0x8006924C, {3: worker + 0xD0, 4: kp, 5: len(cipher_key), 6: vp})
    call(0x80069428, {3: worker + 0x1E0, 4: decoded, 5: 0, 6: int(decompression_enabled)})
    if getword(worker + 0xC8) != 20 or cpu.mem_read(worker + 0xCC, 1)[0] != 1:
        raise ValueError('Original hash setup differs from explicit fixture')
    if getword(worker + 0x1D8) != len(cipher_key) or cpu.mem_read(worker + 0x1DC, 1)[0] != 1:
        raise ValueError('Original cipher setup differs from explicit fixture')
    cpu.mem_write(worker + 0x208, bytes([initial_flags]))
    for offset, value in ((0x20C, expected_wire_prefix), (0x250, cached_prefix)):
        word(worker + offset, len(value))
        cpu.mem_write(worker + offset + 4, value)
    previous = 0
    for i, step in enumerate(expected):
        if i < len(frames):
            live.update(event=i, frame=frames[i], intermediate_writes=set(), current_decoded=set(), call_order=[])
            cpu.mem_write(wire, frames[i])
            cpu.mem_write(intermediate, b'\xA5' * 1024)
            word(descriptor, wire)
            word(descriptor + 4, 0x400)
            word(descriptor + 8, 20 + len(wire_prefix) + receive_sizes[i])
        else:
            live.update(event=None, call_order=[])
        before = bytes(cpu.mem_read(descriptor, 12))
        if call(0x8007F3F0, {3: 77, 4: 2 if i < len(frames) else 4, 5: descriptor}) != 0:
            raise ValueError('Original CMOC dispatcher return differs')
        body = step.state.decoded_body
        if (cpu.mem_read(worker + 0x208, 1)[0] != step.state.response_flags
                or getword(worker + 0xC8) != 20 or cpu.mem_read(worker + 0xCC, 1)[0] != 1
                or getword(worker + 0x1D8) != len(cipher_key) or cpu.mem_read(worker + 0x1DC, 1)[0] != 1
                or getword(worker + 0xADC) != len(body)
                or bytes(cpu.mem_read(decoded, len(body))) != body
                or bytes(cpu.mem_read(decoded + len(body), 4096 - len(body))) != b'\xA5' * (4096 - len(body))):
            raise ValueError('Actual configured callback flags/body/count/backing differ')
        if i < len(frames):
            if (live['call_order'] != [0x8007A0A4, 0x80069388, 0x800694EC]
                    or live['current_decoded'] != set(range(previous, len(body)))
                    or bytes(cpu.mem_read(descriptor, 12)) != struct.pack('>III', wire + 20 + len(wire_prefix), 0x400, 0)
                    or getword(worker + 0x6D8) != len(plaintext[i])
                    or bytes(cpu.mem_read(worker + 0xD0, 16)) != ciphertext_chunks[i][-16:]):
                raise ValueError('Original transform order/state/write span/descriptor differ')
            raw = bytes(cpu.mem_read(worker + 0x1E0, 0x24))
            d = compression.steps[i]
            if (int.from_bytes(raw[4:8], 'big') != d.remaining
                    or int.from_bytes(raw[0x1c:0x20], 'big') != d.cached_remaining
                    or raw[0x13] != d.header_remaining or raw[0x14] != d.variant
                    or raw[0x10] != d.reference_state or raw[0x11] != d.flag_byte
                    or raw[0x12] != d.flag_bits_remaining
                    or int.from_bytes(raw[0xc:0x10], 'big') != d.reference_word):
                raise ValueError('Original composed decoder streaming state differs')
            previous = len(body)
        elif bytes(cpu.mem_read(descriptor, 12)) != before:
            raise ValueError('Original finalizer unexpectedly changed SDK descriptor')
        for pointer, value, mutable in objects:
            if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                    or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard
                    or not mutable and bytes(cpu.mem_read(pointer, len(value))) != value):
                raise ValueError('CMOC transform object/input guards changed')
        if (bytes(cpu.mem_read(slo - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(shi, len(guard))) != guard):
            raise ValueError('CMOC transform stack guards changed')
    if (live['digest'] != hashed.digest or live['native_hash_match'] != hashed.native_match
            or live['compared_digest_bytes'] != hashed.native_compared_bytes):
        raise ValueError('Actual composed original HMAC differs from standard SHA1-HMAC')
    return dict(counts=counts, body_size=len(compression.output), events=len(expected),
                final_flags=expected[-1].state.response_flags,
                native_digest_match=hashed.native_match,
                full_digest_binary_match=hashed.full_span_binary_match,
                native_compared_digest_bytes=live['compared_digest_bytes'],
                actual_hash_cipher_decoder_and_callbacks_executed=True,
                transform_or_digest_stubs_used=False,
                ios_and_sdk_object_lookup_are_synthetic_boundaries=True,
                exact_write_spans_and_backing_verified=True,
                resource_envelope_or_service_authentication_established=False)
