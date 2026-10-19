"""Execute HCHJ XML recursion with mocked allocation, node storage and codecs.

The parser instructions and stack frames are real; SDK scheduling/rendering
are not emulated. No Dolphin process, saves or network requests are touched.
"""
import hashlib
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.inspect_demae_references import sections


def verify_tree(source, xml):
    """Require native parsing to preserve every element, sibling and text value."""
    expected = ET.fromstring(xml)
    state = verify(source, xml)
    if not state['completed'] or state.get('return_value') != 1 or state['stack_overflow']:
        raise ValueError('Native XML parser failed or exceeded its stack')
    nodes = state['nodes']
    def compare(element, address):
        actual = nodes[address]
        if actual['name'] != element.tag.encode('cp932'):
            raise ValueError('Native XML element name differs')
        if actual['text'] != (element.text or '').encode('cp932'):
            raise ValueError('Native XML element text differs')
        if len(actual['children']) != len(element):
            raise ValueError('Native XML sibling count differs')
        for child, native_child in zip(element, actual['children']):
            compare(child, native_child)
    children = nodes[state['root']]['children']
    if len(children) != 1:
        raise ValueError('Native XML document root differs')
    compare(expected, children[0])
    return state


def verify(source, xml, *, stack_bytes=0x4000):
    if hashlib.sha256(source).hexdigest() != 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830':
        raise ValueError('Native XML source fingerprint mismatch')
    if not isinstance(xml, bytes) or len(xml) > 320 * 1024:
        raise ValueError('Expected bounded XML bytes')
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_LR, UC_PPC_REG_PC
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    def reg(n):
        return cpu.reg_read(UC_PPC_REG_0+n)
    def result(value):
        cpu.reg_write(UC_PPC_REG_0+3, value)
    def put(address, value):
        cpu.mem_write(address, struct.pack('>I', value))
    def string(address):
        return bytes(cpu.mem_read(address, 4096)).split(b'\0', 1)[0]
    heap = 0x81000000
    nodes = {}
    lexical_nodes = {}
    def allocate(length):
        nonlocal heap
        address = heap
        heap += (length+31) & ~31
        if heap >= 0x81600000:
            raise ValueError('Mock node storage exhausted')
        return address
    def node(parent, name):
        address, lexical = allocate(32), allocate(32)
        put(address+0x10, lexical)
        nodes[address] = {'name': name, 'children': [], 'text': b''}
        lexical_nodes[lexical] = address
        if parent:
            nodes[parent]['children'].append(address)
        return address
    root = node(0, b'#document')
    parser, input_address, end_pointer = 0x80900000, 0x80F00000, 0x80910000
    put(parser+0x4328, root)
    cpu.mem_write(input_address, xml+b'\0')
    top = 0x817E0000
    for n, value in {1: top, 2: 0x8047A440, 13: 0x80478660,
                     3: parser, 4: input_address, 5: root, 6: end_pointer}.items():
        cpu.reg_write(UC_PPC_REG_0+n, value)
    cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
    state = {'stack_overflow': False, 'completed': False, 'max_stack_bytes': 0}
    def hook(cpu, address, size, data):
        if address == 0x800C3BD8:
            depth = top-reg(1)+0x1E0
            state['max_stack_bytes'] = max(depth, state['max_stack_bytes'])
            if depth > stack_bytes:
                state['stack_overflow'] = True
                cpu.emu_stop()
            return
        if address == 0x80004000:
            cpu.mem_write(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
        elif address == 0x80025B80:
            result(allocate(reg(3)))
        elif address in (0x80025BE8, 0x800FA2A0):
            result(0)
        elif address == 0x80102300:
            a = bytes(cpu.mem_read(reg(3), reg(5)))
            b = bytes(cpu.mem_read(reg(4), reg(5)))
            result(0 if a == b else 1)
        elif address == 0x800C4B30:
            result(node(reg(3), string(reg(5))))
        elif address == 0x800C491C:
            nodes[lexical_nodes[reg(3)]]['text'] = string(reg(4))
            result(1)
        elif address == 0x8002434C:
            value = string(reg(5)).decode('utf-8').encode('utf-16-be')+b'\0\0'
            if len(value) > reg(4):
                raise ValueError('Mock UTF16 conversion exceeds native buffer')
            cpu.mem_write(reg(3), value)
            result(0)
        elif address == 0x800243C4:
            raw = bytes(cpu.mem_read(reg(5), reg(6)))
            length = next((n for n in range(0, len(raw)-1, 2) if raw[n:n+2] == b'\0\0'), len(raw))
            value = raw[:length].decode('utf-16-be').encode('cp932')+b'\0'
            if len(value) > reg(4):
                raise ValueError('Mock CP932 conversion exceeds native buffer')
            cpu.mem_write(reg(3), value)
            result(0)
        elif address == 0x817FF000:
            state['completed'] = True
            state['return_value'] = reg(3)
            cpu.emu_stop()
            return
        else:
            return
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    # Only intercept the parser entry, mocked SDK functions and return sentinel.
    # Visiting Python for every PPC instruction makes nationwide sweeps costly.
    for address in (0x800C3BD8, 0x80004000, 0x80025B80, 0x80025BE8,
                    0x800FA2A0, 0x80102300, 0x800C4B30, 0x800C491C,
                    0x8002434C, 0x800243C4, 0x817FF000):
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    cpu.emu_start(0x800C3BD8, 0x817FF004, count=20_000_000)
    state['nodes'] = nodes
    state['root'] = root
    if not state['completed'] and not state['stack_overflow']:
        raise ValueError('Native parser did not finish within instruction budget')
    return state
