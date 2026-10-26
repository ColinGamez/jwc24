"""Execute original Shop signing wrappers with synthetic ES output only.

The real allocation/copy/Base64 branches execute. ES cryptography and device
state are not run. Returned wire bytes are synthetic fixture outputs, never a
logging API for actual console material.
"""
from dataclasses import dataclass, field
import hashlib
import struct

from tools.verify_wii_shop_url import SOURCE_SHA


@dataclass(frozen=True)
class NativeSigningInspection:
    status: int
    message: bytes = field(repr=False)
    signature_base64: bytes = field(repr=False)
    certificate_base64: bytes = field(repr=False)
    counts: dict
    es_called: bool
    base64_executed: bool

    def metadata(self):
        return {'status': self.status, 'counts': self.counts,
                'native_sign_wrapper_executed': True,
                'native_sign_data_wrapper_executed': True,
                'native_es_boundary_reached': self.es_called,
                'native_base64_executed': self.base64_executed,
                'native_copy_string_and_base64_stubbed': False,
                'es_crypto_and_device_state_executed': False,
                'object_heap_stack_and_write_bounds_verified': True}


def verify_signing_wrapper(source, message, *, signature, signer_certificate, es_status=0):
    if (type(source) is not bytes or not 0 < len(source) <= 4 * 1024 * 1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA):
        raise ValueError('Expected the pinned original Shop v21 application')
    if (type(message) is not bytes or not 1 <= len(message) <= 1024
            or type(signature) is not bytes or len(signature) != 60
            or type(signer_certificate) is not bytes or len(signer_certificate) != 384
            or type(es_status) is not int or not -(1 << 31) <= es_status < 1 << 31):
        raise ValueError('Expected explicit bounded synthetic signing fixture bytes and status')
    from tools.inspect_demae_references import sections
    from unicorn import (Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN,
                         UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR, UC_PPC_REG_MSR
    layout = sections(source)
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in layout:
        cpu.mem_write(address, source[offset:offset + size])
    input_object, signature_object, certificate_object = 0x81000080, 0x81000100, 0x81000180
    stack, stack_lo, stack_hi, stop = 0x817DF000, 0x817DB000, 0x817DF100, 0x817FF000
    heap, heap_end = 0x81200000, 0x81400000
    allocations, visited = [], set()
    captured = None
    counts = {'instructions': 0, 'es_calls': 0, 'base64_calls': 0,
              'allocate_calls': 0, 'free_calls': 0, 'log_calls': 0}
    guard = b'!' * 32

    def reg(index):
        return cpu.reg_read(UC_PPC_REG_0 + index)

    def allocate(size, alignment=32):
        nonlocal heap
        if type(size) is not int or not 0 < size <= 4096 or alignment not in (4, 8, 16, 32, 64):
            raise ValueError('Original signer requested an unsupported synthetic allocation')
        pointer = (heap + 32 + alignment - 1) & ~(alignment - 1)
        heap = pointer + size + 32
        if heap > heap_end:
            raise ValueError('Original signer exceeded its bounded synthetic heap')
        cpu.mem_write(pointer - 32, guard)
        cpu.mem_write(pointer, bytes(size))
        cpu.mem_write(pointer + size, guard)
        allocations.append((pointer, size))
        return pointer

    def string(address, data):
        pointer = allocate(len(data) + 1)
        cpu.mem_write(pointer, data + b'\0')
        cpu.mem_write(address, struct.pack('>III', 0x80000000 | len(data), len(data), pointer))

    def read_string(address):
        raw = bytes(cpu.mem_read(address, 12))
        if raw[0] & 0x80:
            _, size, pointer = struct.unpack('>III', raw)
            if not any(base <= pointer < pointer + size + 1 <= base + length
                       for base, length in allocations):
                raise ValueError('Original signer string escaped its synthetic allocation')
        else:
            size, pointer = raw[0] & 0x7F, address + 1
            if size >= 12:
                raise ValueError('Original signer inline string exceeds its object')
        return bytes(cpu.mem_read(pointer, size))

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0 + 3, value & 0xFFFFFFFF)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def code(_cpu, address, _size, _context):
        nonlocal captured
        counts['instructions'] += 1
        visited.add(address)
        if address in (0x8007C550, 0x8007C5E0, 0x8007C710):
            counts['allocate_calls'] += 1
            ret(allocate(reg(3), reg(4) if address == 0x8007C550 else 32))
            return
        if address == 0x8007C5F0:
            if reg(3) and reg(3) not in [pointer for pointer, _ in allocations]:
                raise ValueError('Original signer free escaped its synthetic allocation')
            counts['free_calls'] += 1
            ret()
            return
        if address == 0x80078610:
            counts['log_calls'] += 1
            ret()
            return
        if address == 0x8025AA90:
            if captured is not None or reg(4) != len(message):
                raise ValueError('Unexpected original ES signing boundary')
            if not any(pointer <= reg(3) < reg(3) + reg(4) <= pointer + length
                       for pointer, length in allocations):
                raise ValueError('Original ES input escaped its synthetic allocation')
            captured = bytes(cpu.mem_read(reg(3), reg(4)))
            if captured != message:
                raise ValueError('Original ES signing input changed before the boundary')
            for pointer, value in ((reg(5), signature), (reg(6), signer_certificate)):
                if not any(base <= pointer < pointer + len(value) <= base + length
                           for base, length in allocations):
                    raise ValueError('Original ES output escaped its synthetic allocation')
                if es_status == 0:
                    cpu.mem_write(pointer, value)
            counts['es_calls'] += 1
            ret(es_status)
            return
        if address == 0x800830E0:
            counts['base64_calls'] += 1
        allowed = ((0x800043C4, 0x80004800), (0x80073500, 0x80078430),
                   (0x80078430, 0x80078610), (0x8007DA40, 0x8007DAB0),
                   (0x80081850, 0x80083400),
                   (0x802B5920, 0x802B5D00), (0x802BA988, 0x802BF000),
                   (0x802C0570, 0x802C11B0))
        if not any(begin <= address < end for begin, end in allowed):
            raise ValueError(f'Original signer entered unreviewed control flow: {address:08x}')

    def read(_cpu, _access, address, size, _value, _context):
        ranges = [(pointer, pointer + 12) for pointer in (input_object, signature_object, certificate_object)]
        ranges += [(pointer, pointer + length) for pointer, length in allocations]
        ranges += [(base, base + length) for index, _, base, length in layout if index >= 7]
        bss, bss_size = struct.unpack_from('>II', source, 0xD8)
        ranges += [(bss, bss + bss_size), (stack_lo, stack_hi)]
        if not any(begin <= address < address + size <= end for begin, end in ranges):
            raise ValueError(f'Original signer read escaped explicit bounds: {address:08x}')

    def write(_cpu, _access, address, size, _value, _context):
        ranges = [(pointer, pointer + 12) for pointer in (signature_object, certificate_object)]
        ranges += [(pointer, pointer + length) for pointer, length in allocations]
        ranges += [(stack_lo, stack_hi), (0x803BEEC0, 0x803BEEC1),
                   (0x803BEEC8, 0x803BF008)]
        if not any(begin <= address < address + size <= end for begin, end in ranges):
            raise ValueError(f'Original signer write escaped explicit bounds: {address:08x}')

    string(input_object, message)
    string(signature_object, b'previous-signature')
    string(certificate_object, b'previous-certificate')
    input_before = bytes(cpu.mem_read(input_object, 12))
    for pointer in (input_object, signature_object, certificate_object):
        cpu.mem_write(pointer - 32, guard)
        cpu.mem_write(pointer + 12, guard)
    cpu.mem_write(stack_lo - 32, guard)
    cpu.mem_write(stack_hi, guard)
    for index, value in {1: stack, 2: 0x80369460, 13: 0x803674E0,
                         3: input_object, 4: signature_object, 5: certificate_object}.items():
        cpu.reg_write(UC_PPC_REG_0 + index, value)
    cpu.reg_write(UC_PPC_REG_MSR, cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
    cpu.reg_write(UC_PPC_REG_LR, stop)
    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.emu_start(0x80078570, stop, count=500000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop or captured != message or counts['es_calls'] != 1:
        raise ValueError('Original signer did not complete its bounded expected ES path')
    for pointer, length in (*allocations,
                            (input_object, 12), (signature_object, 12), (certificate_object, 12),
                            (stack_lo, stack_hi - stack_lo)):
        if (bytes(cpu.mem_read(pointer - 32, 32)) != guard
                or bytes(cpu.mem_read(pointer + length, 32)) != guard):
            raise ValueError('Original signer object/heap/stack guard changed')
    if bytes(cpu.mem_read(input_object, 12)) != input_before or read_string(input_object) != message:
        raise ValueError('Original signer modified its input string')
    if not {0x80078570, 0x80078430} <= visited:
        raise ValueError('Original signer wrappers were not both executed')
    status = reg(3)
    status = status - 0x100000000 if status & 0x80000000 else status
    return NativeSigningInspection(status, captured, read_string(signature_object),
                                    read_string(certificate_object), counts,
                                    True, counts['base64_calls'] == 2)
