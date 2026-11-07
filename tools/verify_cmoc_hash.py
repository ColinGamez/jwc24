"""Unmodified CMOC SDK HMAC/SHA1 and application wrappers on synthetic bytes."""
import hashlib
import hmac
import struct

from jwc24.cmoc_hash import hmac_sha1_digest, inspect_application_hash
from tools.verify_cmoc_framing import SOURCE_SHA256


class _DigestOverread(ValueError):
    pass


def _execute(source, *, key, key_size, chunks, expected, application, overlong_probe=False):
    if (type(source) is not bytes or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    if (key is not None and (type(key) is not bytes or len(key) > 4096)
            or type(chunks) is not tuple or len(chunks) > 64
            or any(type(c) is not bytes for c in chunks)
            or sum(map(len, chunks)) > 4096 or type(expected) is not bytes
            or len(expected) > 4096):
        raise ValueError('Expected bounded synthetic native CMOC hash inputs')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    layout = sections(source)
    for _, offset, address, size in layout:
        cpu.mem_write(address, source[offset:offset + size])
    worker, key_pointer, expected_pointer, output = 0x81000000, 0x81100000, 0x81110000, 0x81120000
    chunk_base = 0x81200000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    guard = b'CMOC-HASH-GUARD!!' * 2
    objects = []

    def put(pointer, value, mutable=False):
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
        objects.append((pointer, value, mutable))

    put(worker, b'\xA5' * 0xD0, True)
    put(key_pointer, key or b'')  # String-mode terminator must be supplied in key.
    put(expected_pointer, expected)
    put(output, b'\xA5' * 20, True)
    for index, chunk in enumerate(chunks):
        put(chunk_base + index * 0x2000, chunk)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_lo, b'\xA5' * (stack_hi - stack_lo))
    cpu.mem_write(stack_hi, guard)
    # Original SHA1 finalization reads at most seven bytes from this loader-zero
    # BSS padding span. Only this exact pinned span is admitted, not arbitrary
    # mapped RAM; it falls inside the original DOL's declared BSS interval.
    zero_padding_start, zero_padding_end = 0x80430770, 0x80430778
    bss_start, bss_size = struct.unpack_from('>II', source, 0xD8)
    if not bss_start <= zero_padding_start < zero_padding_end <= bss_start + bss_size:
        raise ValueError('CMOC SHA1 zero-padding span exceeds original loader BSS')
    if bytes(cpu.mem_read(zero_padding_start, 8)) != bytes(8):
        raise ValueError('CMOC SHA1 loader zero-padding span changed')
    captured = {}
    counts = dict(instructions=0, sdk_setups=0, sdk_updates=0, sdk_finals=0,
                  sha1_initializers=0, sha1_updates=0, sha1_finals=0,
                  sha1_compressions=0, native_string_comparisons=0,
                  compared_bytes=0, stubs=0)

    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0 + n)

    def code(_cpu, address, _size, _ctx):
        counts['instructions'] += 1
        for target, name in ((0x80195594, 'sdk_setups'), (0x801957D0, 'sdk_updates'),
                             (0x801957E0, 'sdk_finals'), (0x80194FBC, 'sha1_initializers'),
                             (0x8019500C, 'sha1_updates'), (0x801950C0, 'sha1_finals'),
                             (0x801951F8, 'sha1_compressions'), (0x800DE280, 'native_string_comparisons')):
            if address == target:
                counts[name] += 1
        if address == 0x8007A124:
            captured.update(digest=bytes(cpu.mem_read(reg(3), 20)),
                            digest_pointer=reg(3), comparison_size=reg(5))
        allowed = ((0x80004000, 0x80004134), (0x80079FF8, 0x8007A154),
                   (0x800D5EEC, 0x800D6000), (0x800D64D0, 0x800D6580),
                   (0x800DE280, 0x800DE2C0), (0x80194FBC, 0x80195984))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC hash control flow at {address:#x}')

    def read(_cpu, _access, address, size, _value, _ctx):
        pc = cpu.reg_read(UC_PPC_REG_PC)
        if 0x800DE280 <= pc < 0x800DE2C0 and captured:
            start = captured['digest_pointer']
            if start <= address < start + captured['comparison_size']:
                if address + size > start + 20:
                    raise _DigestOverread('Native CMOC string comparison exceeds twenty digest bytes')
                counts['compared_bytes'] += size
        allowed = [(p, p + len(value)) for p, value, _ in objects]
        allowed += [(a, a + size) for i, _, a, size in layout if i >= 7]
        allowed += [(stack_lo, stack_hi), (zero_padding_start, zero_padding_end)]
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC hash read at {address:#x}')

    def write(_cpu, _access, address, size, _value, _ctx):
        allowed = [(p, p + len(value)) for p, value, mutable in objects if mutable]
        allowed.append((stack_lo, stack_hi))
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC hash write at {address:#x}')

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def call(address, arguments):
        for n, value in {1: stack, 2: 0x80435BE0, 13: 0x80432BA0, **arguments}.items():
            cpu.reg_write(UC_PPC_REG_0 + n, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(address, stop, count=1000000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('CMOC hash instruction cap reached')
        return reg(3)

    descriptor = call(0x801951EC, {})
    if application:
        call(0x80079FF8, {3: worker, 4: key_pointer if key is not None else 0,
                          5: key_size, 6: descriptor})
    else:
        call(0x80195594, {3: worker, 4: descriptor, 5: key_pointer, 6: len(key)})
    resolved = struct.unpack('>I', bytes(cpu.mem_read(worker + 0xC8, 4)))[0] if application else None
    enabled = bool(cpu.mem_read(worker + 0xCC, 1)[0]) if application else True
    update_returns = []
    for index, chunk in enumerate(chunks):
        value = call(0x8007A0A4 if application else 0x801957D0,
                     {3: worker, 4: chunk_base + index * 0x2000, 5: len(chunk)})
        update_returns.append(value)
    overread = False
    native_match = None
    try:
        if application:
            native_match = bool(call(0x8007A0E8, {3: worker, 4: expected_pointer}))
            digest = captured.get('digest')
        else:
            call(0x801957E0, {3: worker, 4: output})
            digest = bytes(cpu.mem_read(output, 20))
    except _DigestOverread:
        if not overlong_probe:
            raise
        overread = True
        digest = captured['digest']
    for pointer, value, mutable in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard
                or (not mutable and bytes(cpu.mem_read(pointer, len(value))) != value)):
            raise ValueError('CMOC hash immutable input/object guard changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('CMOC hash stack guard changed')
    if bytes(cpu.mem_read(zero_padding_start, 8)) != bytes(8):
        raise ValueError('CMOC SHA1 loader zero-padding span changed')
    return dict(digest=digest, enabled=enabled, resolved_key_size=resolved,
                comparison_size=captured.get('comparison_size'),
                update_returns=tuple(update_returns), native_match=native_match,
                digest_overread_trapped=overread, counts=counts)


def verify_hmac_sha1(source, *, key, chunks):
    expected = hmac_sha1_digest(key, chunks)
    result = _execute(source, key=key, key_size=len(key), chunks=chunks,
                      expected=b'', application=False)
    if result['digest'] != expected:
        raise ValueError('Original CMOC SDK output differs from standard HMAC-SHA1')
    return dict(algorithm='HMAC-SHA1', key_size=len(key), message_size=sum(map(len, chunks)),
                chunk_count=len(chunks), full_twenty_byte_digest_matches=True,
                original_sha1_and_hmac_functions_executed=True, stubs_used=False,
                input_and_stack_guards_verified=True, counts=result['counts'])


def verify_application_hash(source, **inputs):
    expected = inspect_application_hash(**inputs)
    result = _execute(source, **inputs, application=True)
    if (result['digest'] != expected.digest or result['enabled'] != expected.enabled
            or result['resolved_key_size'] != expected.resolved_key_size
            or result['native_match'] != expected.native_match
            or result['update_returns'] != expected.update_returns
            or result['counts']['compared_bytes'] != expected.native_compared_bytes
            or (expected.enabled and result['comparison_size'] != expected.resolved_key_size)):
        raise ValueError('Original CMOC hash wrapper differs from independent inspection')
    return {**expected.metadata(), 'counts': result['counts'],
            'original_sha1_hmac_string_comparison_executed': True,
            'stubs_used': False, 'input_and_stack_guards_verified': True}


def probe_overlong_comparison(source, *, key, chunks):
    if type(key) is not bytes or not 21 <= len(key) <= 64:
        raise ValueError('Expected a bounded overlong synthetic CMOC key')
    digest = hmac_sha1_digest(key, chunks)
    if b'\0' in digest:
        raise ValueError('Overlong probe requires no early NUL in the actual digest')
    result = _execute(source, key=key, key_size=len(key), chunks=chunks,
                      expected=digest + bytes(len(key) - 20), application=True,
                      overlong_probe=True)
    if (not result['digest_overread_trapped'] or result['digest'] != digest
            or result['resolved_key_size'] != len(key) or result['comparison_size'] != len(key)):
        raise ValueError('CMOC overlong comparison did not reach its guarded digest boundary')
    return dict(resolved_key_size=result['resolved_key_size'],
                comparison_size=result['comparison_size'],
                full_twenty_byte_digest_matches_standard=True,
                digest_overread_trapped=True, unrelated_stack_byte_not_read=True,
                stubs_used=False, input_and_stack_guards_verified=True,
                counts=result['counts'])
