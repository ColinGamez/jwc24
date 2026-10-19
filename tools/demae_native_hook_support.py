"""Guarded private DOL patch primitives; not a complete native phone hook.

Reserved-region use still requires boot/lifetime review and cheats disabled.
"""
import hashlib
import struct
from tools.inspect_demae_references import sections

RESERVED_START = 0x80001800
RESERVED_END = 0x80003000
OWNED_PADDING_START = 0x800058C0
OWNED_PADDING_END = 0x80005D80


def branch_instruction(source, target, *, link=False):
    if type(source) is not int or type(target) is not int or source % 4 or target % 4:
        raise ValueError('PowerPC branch addresses must be aligned integers')
    displacement = target - source
    if not -0x2000000 <= displacement < 0x2000000:
        raise ValueError('PowerPC relative branch is out of range')
    return struct.pack('>I', 0x48000000 | (displacement & 0x03fffffc) | int(link))


def append_reserved_text(source, payload, *, expected_sha256):
    if hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError('DOL fingerprint mismatch')
    if not payload or len(payload) % 4 or len(payload) > RESERVED_END - RESERVED_START:
        raise ValueError('Invalid reserved text payload size')
    # Dolphin's DOL loader requires text sizes aligned to its 32-byte cache line.
    section_payload = payload + bytes((-len(payload)) % 32)
    layout = sections(source)
    end = RESERVED_START + len(section_payload)
    bss, bss_size = struct.unpack_from('>II', source, 0xd8)
    ranges = [(address, address + size) for _, _, address, size in layout]
    ranges.append((bss, bss + bss_size))
    if any(RESERVED_START < stop and start < end for start, stop in ranges):
        raise ValueError('Reserved text overlaps an existing DOL range')
    offsets = struct.unpack_from('>7I', source)
    addresses = struct.unpack_from('>7I', source, 0x48)
    sizes = struct.unpack_from('>7I', source, 0x90)
    slots = [i for i in range(7) if offsets[i] == addresses[i] == sizes[i] == 0]
    if not slots:
        raise ValueError('No unused DOL text slot')
    result = bytearray(source)
    result.extend(bytes((-len(result)) % 32))
    file_offset = len(result)
    result.extend(section_payload)
    slot = slots[0]
    struct.pack_into('>I', result, slot * 4, file_offset)
    struct.pack_into('>I', result, 0x48 + slot * 4, RESERVED_START)
    struct.pack_into('>I', result, 0x90 + slot * 4, len(section_payload))
    verified = sections(result)
    if (slot, file_offset, RESERVED_START, len(section_payload)) not in verified:
        raise ValueError('Reserved text section verification failed')
    return bytes(result)


def replace_text_instruction(source, address, *, expected, replacement):
    if len(expected) != 4 or len(replacement) != 4 or address % 4:
        raise ValueError('Expected one aligned PowerPC instruction')
    for index, offset, base, size in sections(source):
        if index < 7 and base <= address <= base + size - 4:
            position = offset + address - base
            if source[position:position+4] != expected:
                raise ValueError('Native hook instruction mismatch')
            return source[:position] + replacement + source[position+4:]
    raise ValueError('Native hook is not in a text section')


def fill_owned_text_padding(source, payload, *, expected_sha256):
    """Use verified empty bytes in the existing section; retain the DOL header."""
    if hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError('DOL fingerprint mismatch')
    if not payload or len(payload) % 4 or len(payload) > OWNED_PADDING_END - OWNED_PADDING_START:
        raise ValueError('Invalid owned text payload size')
    for index, offset, base, size in sections(source):
        if index == 0 and base <= OWNED_PADDING_START and OWNED_PADDING_END <= base + size:
            position = offset + OWNED_PADDING_START - base
            capacity = OWNED_PADDING_END - OWNED_PADDING_START
            if any(source[position:position+capacity]):
                raise ValueError('Owned text padding is not empty')
            return source[:position] + payload + source[position+len(payload):]
    raise ValueError('Owned padding is outside the expected text section')
