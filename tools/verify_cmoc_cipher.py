"""Execute unchanged Japanese CMOC AES/core wrappers on bounded synthetic data.

Only IOS open/close and diagnostic boundaries are supplied; AES tables, key
expansion, block core, copies, wrapper flags and acquire/release helpers execute
from the caller's exact pinned private executable. No source file is discovered
or fetched by this module.
"""
import hashlib

from jwc24.cmoc_cipher import decrypt_aes_cbc, inspect_application_cipher
from tools.verify_cmoc_framing import SOURCE_SHA256


def _execute(source, *, key, key_size, iv, chunks, application, inplace=False,
             open_results=(), close_results=(), release=False):
    if (type(source) is not bytes or len(source) != 3410304
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('CMOC Japanese v512 executable fingerprint mismatch')
    if (key is not None and (type(key) is not bytes or len(key) > 64)
            or type(key_size) is not int or not 0 <= key_size <= 64
            or key_size > len(key or b'')
            or iv is not None and (type(iv) is not bytes or len(iv) != 16)
            or type(chunks) is not tuple or len(chunks) > 64
            or any(type(c) is not bytes for c in chunks)
            or sum(map(len, chunks)) > 4096
            or any(type(v) is not bool for v in (application, inplace, release))):
        raise ValueError('Expected bounded explicit synthetic CMOC cipher inputs')
    for results in (open_results, close_results):
        if (type(results) is not tuple or len(results) > 128
                or any(type(v) is not int or not -(2**31) <= v < 2**31 for v in results)):
            raise ValueError('Expected bounded explicit IOS boundary results')
    if not application and (key is None or iv is None or release):
        raise ValueError('Direct SDK fixture requires an explicit key and IV')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset + size])
    context, kp, vp, data, output = 0x81000000, 0x81100000, 0x81110000, 0x81200000, 0x81300000
    stack_lo, stack_hi, stack, stop = 0x817D0000, 0x817E1000, 0x817E0000, 0x817FF000
    handle = 0x8042B730
    guard = b'CMOC-CIPHER-GUARD' * 2
    objects = []
    cipher = b''.join(chunks)

    def put(pointer, value, mutable=False):
        cpu.mem_write(pointer - len(guard), guard)
        cpu.mem_write(pointer, value)
        cpu.mem_write(pointer + len(value), guard)
        objects.append((pointer, value, mutable))

    put(context, bytes(0x110), True)
    put(kp, key or b'')
    put(vp, iv if iv is not None else bytes(16))
    put(data, cipher, inplace)
    if inplace:
        output = data
    else:
        put(output, b'\xA5' * len(cipher), True)
    cpu.mem_write(stack_lo - len(guard), guard)
    cpu.mem_write(stack_lo, b'\xA5' * (stack_hi - stack_lo))
    cpu.mem_write(stack_hi, guard)
    # Explicit initial private-memory fixture, not a device or live IOS handle.
    cpu.mem_write(handle, b'\xFF' * 4)
    counts = dict(instructions=0, native_blocks=0, acquire_calls=0,
                  release_calls=0, open_boundaries=0, close_boundaries=0,
                  diagnostic_boundaries=0)
    acquisitions, sdk_returns, output_writes = [], [], set()

    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0 + n)

    def code(_cpu, address, _size, _ctx):
        counts['instructions'] += 1
        for target, name in ((0x80196890, 'native_blocks'), (0x80195DFC, 'acquire_calls'),
                             (0x80195E8C, 'release_calls')):
            if address == target:
                counts[name] += 1
        if address == 0x80195E88:
            acquisitions.append(bool(reg(3)))
        if address == 0x801967F0:
            sdk_returns.append(reg(3))
        boundaries = {0x8010DC0C: ('open_boundaries', open_results, 7),
                      0x8010DDEC: ('close_boundaries', close_results, 0),
                      0x8027DC04: ('diagnostic_boundaries', (), 0)}
        if address in boundaries:
            name, supplied, default = boundaries[address]
            index = counts[name]
            counts[name] += 1
            value = supplied[index] if index < len(supplied) else default
            cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
            cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
            return
        allowed = ((0x80004000, 0x80004134), (0x8006924C, 0x80069428),
                   (0x800D5EEC, 0x800D6000), (0x800D64D0, 0x800D6580),
                   (0x80195DFC, 0x80196924))
        if not any(lo <= address < hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC cipher control flow at {address:#x}')

    def read(_cpu, _access, address, size, _value, _ctx):
        allowed = [(p, p + len(value)) for p, value, _ in objects]
        # Exact original static AES S-box/round-constant, inverse-table and SDK
        # descriptor spans. Unrelated original resources are not admitted.
        allowed += [(0x802DDB98, 0x802DDDB8), (0x802DE1B8, 0x802DE5B8),
                    (0x8042F008, 0x8042F010), (stack_lo, stack_hi), (handle, handle + 4)]
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC cipher read at {address:#x}')

    def write(_cpu, _access, address, size, _value, _ctx):
        allowed = [(p, p + len(value)) for p, value, mutable in objects if mutable]
        allowed += [(stack_lo, stack_hi), (handle, handle + 4)]
        if not any(lo <= address < address + size <= hi for lo, hi in allowed):
            raise ValueError(f'Unexpected CMOC cipher write at {address:#x}')
        if output <= address < address + size <= output + len(cipher):
            output_writes.update(range(address, address + size))

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)

    def call(address, arguments):
        for n, value in {1: stack, 2: 0x80435BE0, 13: 0x80432BA0, **arguments}.items():
            cpu.reg_write(UC_PPC_REG_0 + n, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)
        cpu.emu_start(address, stop, count=1000000)
        if cpu.reg_read(UC_PPC_REG_PC) != stop:
            raise ValueError('CMOC cipher instruction cap reached')
        return reg(3)

    setup_return = call(0x8006924C if application else 0x80196730,
                        {3: context, 4: kp if key is not None else 0,
                         5: key_size, 6: vp if iv is not None else 0})
    setup_enabled = bool(cpu.mem_read(context + 0x10C, 1)[0])
    setup_size = int.from_bytes(cpu.mem_read(context + 0x108, 4), 'big')
    setup_acquired = acquisitions[-1] if acquisitions else None
    offset, rows = 0, []
    for chunk in chunks:
        before = bytes(cpu.mem_read(output + offset, len(chunk)))
        output_writes.clear()
        first_acquire, first_sdk = len(acquisitions), len(sdk_returns)
        result = call(0x80069388 if application else 0x8019673C,
                      {3: context, 4: output + offset, 5: data + offset, 6: len(chunk)})
        rows.append(dict(return_size=result,
                         acquired=acquisitions[-1] if len(acquisitions) > first_acquire else None,
                         sdk_accepted=bool(sdk_returns[-1]) if len(sdk_returns) > first_sdk else None,
                         before=before, after=bytes(cpu.mem_read(output + offset, len(chunk))),
                         written_size=len(output_writes)))
        offset += len(chunk)
    first_acquire = len(acquisitions)
    if release:
        call(0x80069330, {3: context})
    release_acquired = acquisitions[-1] if len(acquisitions) > first_acquire else None
    for pointer, value, mutable in objects:
        if (bytes(cpu.mem_read(pointer - len(guard), len(guard))) != guard
                or bytes(cpu.mem_read(pointer + len(value), len(guard))) != guard
                or not mutable and bytes(cpu.mem_read(pointer, len(value))) != value):
            raise ValueError('CMOC cipher explicit backing or guard changed')
    if (bytes(cpu.mem_read(stack_lo - len(guard), len(guard))) != guard
            or bytes(cpu.mem_read(stack_hi, len(guard))) != guard):
        raise ValueError('CMOC cipher stack guard changed')
    if len(open_results) > counts['open_boundaries'] or len(close_results) > counts['close_boundaries']:
        raise ValueError('Unused explicit CMOC IOS boundary results')
    return dict(setup_return=setup_return, setup_enabled=setup_enabled,
                setup_key_size=setup_size, setup_acquired=setup_acquired,
                enabled=bool(cpu.mem_read(context + 0x10C, 1)[0]),
                resolved_key_size=int.from_bytes(cpu.mem_read(context + 0x108, 4), 'big'),
                release_acquired=release_acquired, rows=rows,
                final_chain=bytes(cpu.mem_read(context, 16)), counts=counts,
                final_handle=int.from_bytes(cpu.mem_read(handle, 4), 'big', signed=True))


def verify_application_cipher(source, *, key, key_size, iv, chunks, inplace=False,
                              open_results=(), close_results=(), release=False):
    actual = _execute(source, key=key, key_size=key_size, iv=iv, chunks=chunks,
                      application=True, inplace=inplace, open_results=open_results,
                      close_results=close_results, release=release)
    projection = inspect_application_cipher(
        key=key, key_size=key_size, iv=iv, chunks=chunks,
        setup_acquired=actual['setup_acquired'],
        chunk_acquired=tuple(row['acquired'] for row in actual['rows']),
        release=release, release_acquired=actual['release_acquired'])
    if (projection.setup_enabled != actual['setup_enabled']
            or projection.setup_key_size != actual['setup_key_size']
            or projection.enabled != actual['enabled']
            or projection.resolved_key_size != actual['resolved_key_size']
            or projection.final_chain is not None and projection.final_chain != actual['final_chain']):
        raise ValueError('Original CMOC cipher context disagrees with independent projection')
    for expected, row in zip(projection.chunks, actual['rows']):
        if (expected.return_size != row['return_size'] or expected.sdk_accepted != row['sdk_accepted']
                or expected.written is None and (row['after'] != row['before'] or row['written_size'])
                or expected.written is not None and (row['after'] != expected.written
                                                     or row['written_size'] != len(expected.written))):
            raise ValueError('Original CMOC cipher return/write disagrees with independent projection')
    return dict(**projection.metadata(), counts=actual['counts'],
                acquisition_results_observed_from_original_helper=True,
                input_and_stack_guards_verified=True,
                original_cipher_and_wrappers_executed=True,
                ios_and_diagnostics_are_explicit_boundaries=True,
                final_synthetic_handle=actual['final_handle'])


def verify_sdk_cipher(source, *, key, iv, chunks, inplace=False):
    expected = decrypt_aes_cbc(key=key, iv=iv, chunks=chunks)
    actual = _execute(source, key=key, key_size=len(key), iv=iv, chunks=chunks,
                      application=False, inplace=inplace)
    chain = next((chunk[-16:] for chunk in reversed(chunks) if chunk), iv)
    if (actual['setup_return'] != 1 or actual['final_chain'] != chain
            or any(row['return_size'] != 1 or row['after'] != value
                   or row['written_size'] != len(value) for row, value in zip(actual['rows'], expected))):
        raise ValueError('Original CMOC SDK cipher disagrees with independent AES-CBC')
    return dict(algorithm='AES-CBC', counts=actual['counts'],
                plaintext_and_final_chain_match=True,
                input_and_stack_guards_verified=True,
                cipher_or_key_expansion_stubbed=False,
                source_authentication_established=False)
