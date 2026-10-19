"""Exercise native menu-category control flow with mocked XML/model/SDK calls.

This does not verify XML lexing, native model storage, rendering or ordering.
No executable bytes are distributed and no network calls are made.
"""
import hashlib
import struct
import xml.etree.ElementTree as ET

from tools.inspect_demae_references import sections


def verify(source, xml):
    if hashlib.sha256(source).hexdigest() != 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830':
        raise ValueError('Native menu consumer source fingerprint mismatch')
    if len(xml) > 65536:
        raise ValueError('Menu consumer test input exceeds inspection bound')
    root = ET.fromstring(xml)
    if any((n.text or '').strip() == '1' for n in root.iter('isLunchTimeMenu')):
        raise ValueError('Verifier covers non-lunch menu entries only')
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
    def word(address, value):
        cpu.mem_write(address, struct.pack('>I', value))
    def string(address):
        return bytes(cpu.mem_read(address, 4096)).split(b'\0', 1)[0]
    def wide_string(address):
        raw = bytes(cpu.mem_read(address, 4096))
        end = next(n for n in range(0, len(raw), 2) if raw[n:n+2] == b'\0\0')
        return raw[:end].decode('utf-16-be')
    heap = 0x81000000
    def allocate(data):
        nonlocal heap
        address = heap
        heap += (len(data)+31)//32*32
        cpu.mem_write(address, data)
        return address
    nodes, handles = {}, {}
    for node in root.iter():
        address = allocate(bytes(32))
        nodes[address] = node
        handles[id(node)] = address
    payloads = {address: allocate((node.text or '').encode('cp932')+b'\0')
                for address, node in nodes.items()}
    scene, model, document = 0x80900000, 0x80901000, 0x80902000
    word(0x8038A210+0x268, model)
    word(0x8038A210+0x230, document)
    captured, lookups = [], []
    current = {}
    setters = {0x8002A468: 'menuCode', 0x8002A524: 'linkTitle', 0x8002A5E8: 'enabledLink',
               0x8002A5FC: 'name', 0x8002A6C0: 'info', 0x8002A784: 'setNum'}
    noops = {0x80029F54, 0x8002A93C, 0x8002A95C, 0x80029FCC,
             0x8002A9D4, 0x8002ADAC, 0x80025BE8}
    def hook(cpu, address, size, data):
        nonlocal current
        if address == 0x817FF000:
            cpu.emu_stop()
            return
        if address == 0x800EE084:
            result(0)  # Shared transport/status validation is outside this check.
        elif address == 0x80029F28:
            current = {}
        elif address == 0x80029CB0:
            captured.clear()
        elif address == 0x800C43E0:
            name = string(reg(4)).decode('ascii')
            parent = nodes.get(reg(5))
            context = root if parent is None else parent
            found = next((n for n in context.iter() if n.tag == name), None)
            lookups.append(name)
            result(handles[id(found)] if found is not None else 0)
        elif address == 0x800C4AF4:
            result(len(nodes[reg(3)]))
        elif address == 0x800C4AFC:
            result(handles[id(nodes[reg(3)][reg(4)])])
        elif address == 0x800C4B28:
            result(reg(3))  # Mock payload wrapper exists for every XML element.
        elif address == 0x800C4870:
            result(payloads[reg(3)])
        elif address in setters:
            key = setters[address]
            current[key] = (reg(4) if key == 'enabledLink' else '' if not reg(4)
                            else wide_string(reg(4)) if key in {'linkTitle', 'name', 'info'}
                            else string(reg(4)).decode('cp932'))
        elif address == 0x8002A840:
            result(1)  # Mock lunch attachment and menu model insertion.
        elif address == 0x80029D08:
            captured.append(dict(current))
            result(1)
        elif address == 0x80029EDC:
            result(len(captured))
        elif address == 0x801021E4:
            result(0 if string(reg(3)) == string(reg(4)) else 1)
        elif address == 0x800FB34C:
            result(len(string(reg(3)).decode('cp932')))
        elif address == 0x80025B80:
            result(allocate(bytes(reg(3))))
        elif address == 0x801F5DB0:
            raw = string(reg(5)).decode('cp932').encode('utf-16-be')
            cpu.mem_write(reg(3), raw+b'\0\0')
            word(reg(4), len(raw)//2)
        elif address not in noops:
            raise ValueError(f'Unexpected native menu SDK call {address:08x}')
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))
    addresses = {0x817FF000, 0x800EE084, 0x80029F28, 0x80029CB0, 0x800C43E0,
        0x800C4AF4, 0x800C4AFC, 0x800C4B28, 0x800C4870, 0x8002A840, 0x80029D08,
        0x80029EDC, 0x801021E4, 0x800FB34C, 0x80025B80, 0x801F5DB0, *setters, *noops}
    for address in addresses:
        cpu.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)
    for n, value in {1: 0x817E0000, 2: 0x8047A440, 13: 0x80478660, 3: scene}.items():
        cpu.reg_write(UC_PPC_REG_0+n, value)
    cpu.reg_write(UC_PPC_REG_LR, 0x817FF000)
    cpu.emu_start(0x800499FC, 0x817FF004, count=1_000_000)
    if cpu.reg_read(UC_PPC_REG_PC) != 0x817FF000:
        raise ValueError('Native menu consumer did not return within instruction budget')
    return {'accepted': reg(3) == 1, 'inserted_rows': captured, 'lookups': lookups,
            'native_model_mocked': True, 'native_rendering_verified': False}
