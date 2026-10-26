"""Execute stock HCHJ item consumption, model copying and variant stock predicate.

XML lookup/storage, status validation, allocation, codecs and selected libc are
synthetic adapters. The consumer, item/size setters, copies, linked insertion,
cleanup, price formatting and final raw-stock comparison execute unchanged.
Fixtures stay offline: no UI, provider, basket submission or availability claim.
"""
import hashlib
import re
import struct
from xml.etree import ElementTree as ET


SOURCE_SHA256 = '6b9002431aec265e34ba532aae2707ef74a5b8c491f81be624a54563eabc88c9'


def verify_item_flow(source, xml, *, fail_variant_node=None, fail_item_node=None, basket_codes=None):
    if (not isinstance(source, bytes) or not 0 < len(source) <= 4*1024*1024
            or hashlib.sha256(source).hexdigest() != SOURCE_SHA256):
        raise ValueError('Expected fingerprinted stock HCHJ v512 application')
    if (not isinstance(xml, bytes) or not 0 < len(xml) <= 65536
            or b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper()):
        raise ValueError('Expected bounded offline item XML without entity declarations')
    lexical = re.sub(br'<!\[CDATA\[.*?\]\]>', b'', xml, flags=re.S)
    if re.search(br'<[^>]*?/\s*>', lexical):
        raise ValueError('Offline native item fixtures require explicit closing tags')
    for value in (fail_variant_node, fail_item_node):
        if value is not None and (type(value) is not int or not 1 <= value <= 128):
            raise ValueError('Expected a bounded node-allocation failure index')
    basket_codes = [] if basket_codes is None else basket_codes
    if (not isinstance(basket_codes, list) or len(basket_codes) > 32
            or any(not isinstance(row, tuple) or len(row) != 2 or type(row[0]) is not int
                   or not 0 <= row[0] < 32 or not isinstance(row[1], str)
                   or not 0 < len(row[1]) <= 128 or '\0' in row[1] for row in basket_codes)):
        raise ValueError('Expected bounded explicit basket-code probes')
    try:
        for _, value in basket_codes:
            value.encode('cp932')
    except UnicodeError:
        raise ValueError('Basket-code probes must be representable in CP932') from None
    try:
        root = ET.fromstring(xml)
        elements = list(root.iter())
        if not 1 <= len(elements) <= 512:
            raise ValueError('Item fixture element count exceeds local bound')
        encoded = {}
        for node in elements:
            if (node.attrib or not re.fullmatch('[A-Za-z_][A-Za-z0-9_.-]*', node.tag)
                    or len(node.text or '') > 128 or '\0' in (node.text or '')):
                raise ValueError('Unsupported offline item element')
            encoded[id(node)] = (node.text or '').encode('cp932')+b'\0'
    except (ET.ParseError, UnicodeError):
        raise ValueError('Malformed or non-CP932 offline item XML') from None
    from tools.inspect_demae_references import sections
    from unicorn import Uc, UC_ARCH_PPC, UC_MODE_32, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
    from unicorn.ppc_const import UC_PPC_REG_0, UC_PPC_REG_PC, UC_PPC_REG_LR, UC_PPC_REG_MSR
    cpu = Uc(UC_ARCH_PPC, UC_MODE_32 | UC_MODE_BIG_ENDIAN)
    cpu.mem_map(0x80000000, 0x1800000)
    for _, offset, address, size in sections(source):
        cpu.mem_write(address, source[offset:offset+size])
    scene, model, document = 0x80900020, 0x80901020, 0x80902020
    pane_a, pane_b, stack, stop = 0x80903020, 0x80903220, 0x817e0000, 0x817ff000
    basket_line, match_context = 0x80904020, 0x80905020
    heap, heap_end = 0x81000000, 0x81600000
    allocations, freed, visits, stubs = [], set(), set(), {}
    xml_payloads, nodes, handles = {}, {}, {}
    failures = {'variant_node_attempts': 0, 'item_node_attempts': 0}

    def reg(index):
        return cpu.reg_read(UC_PPC_REG_0+index)

    def put(address, value):
        cpu.mem_write(address, struct.pack('>I', value & 0xffffffff))

    def word(address):
        return int.from_bytes(cpu.mem_read(address, 4), 'big')

    def allocate(size):
        nonlocal heap
        if not 0 < size <= 65536:
            raise ValueError('Synthetic item allocation exceeds local bound')
        address = heap+32
        heap += (size+95) & ~31
        if heap > heap_end:
            raise ValueError('Synthetic item heap exhausted')
        cpu.mem_write(address-32, b'!'*32)
        cpu.mem_write(address+size, b'!'*32)
        allocations.append((address, size))
        return address

    def store(address, value):
        length = len(value)
        if not ((stack-0x4000 <= address < address+length <= stack+0x100)
                or any(b <= address < address+length <= b+n for b, n in allocations)):
            raise ValueError('Synthetic codec/libc write outside allocated buffer')
        cpu.mem_write(address, value)

    def text(address, wide=False, *, owned=False):
        if not address:
            return None
        if owned and (address in freed or not any(b <= address < b+n for b, n in allocations)):
            raise ValueError('Native item retained freed or nonowned text')
        raw = bytes(cpu.mem_read(address, 2048))
        if wide:
            end = next((i for i in range(0, len(raw)-1, 2) if raw[i:i+2] == b'\0\0'), None)
        else:
            end = raw.find(b'\0')
            end = None if end < 0 else end
        if end is None:
            raise ValueError('Native item text exceeds local read bound')
        return raw[:end]

    for node in elements:
        handle = allocate(32)
        nodes[handle], handles[id(node)] = node, handle
        payload = allocate(len(encoded[id(node)]))
        cpu.mem_write(payload, encoded[id(node)])
        xml_payloads[handle] = (payload, len(encoded[id(node)]))
    guards = ((scene, 0x400), (model, 0x10), (document, 0x10),
              (pane_a, 0x100), (pane_b, 0x100), (basket_line, 0x40),
              (match_context, 0x200), (stack-0x4000, 0x4100))
    for address, size in guards:
        cpu.mem_write(address-16, b'!'*16)
        cpu.mem_write(address+size, b'!'*16)
    put(0x8038a210+0x26c, model)
    put(0x8038a210+0x230, document)

    def ret(value=0):
        cpu.reg_write(UC_PPC_REG_0+3, value & 0xffffffff)
        cpu.reg_write(UC_PPC_REG_PC, cpu.reg_read(UC_PPC_REG_LR))

    def instruction(_cpu, address, _size, _data):
        visits.add(address)
        if address == 0x800ee084:
            stubs[address] = stubs.get(address, 0)+1
            ret(0)
            return
        if address in (0x80022b28, 0x80022b70, 0x80022ae0, 0x80025b80):
            caller = cpu.reg_read(UC_PPC_REG_LR)
            fail = False
            if caller == 0x800273a4:
                failures['variant_node_attempts'] += 1
                fail = failures['variant_node_attempts'] == fail_variant_node
            if caller == 0x800260ac:
                failures['item_node_attempts'] += 1
                fail = failures['item_node_attempts'] == fail_item_node
            stubs[address] = stubs.get(address, 0)+1
            # Image-buffer copies can request new[0]. This synthetic allocator
            # returns distinct owned storage; actual heap behavior is not proved.
            ret(0 if fail else allocate(max(1, reg(3))))
            return
        if address in (0x80022b3c, 0x80022af4, 0x80025be8, 0x80022b84):
            if reg(3):
                if not any(reg(3) == b for b, _ in allocations):
                    raise ValueError('Native item free outside synthetic allocation')
                freed.add(reg(3))
            stubs[address] = stubs.get(address, 0)+1
            ret()
            return
        if address == 0x80004000:
            if reg(5) > 65536:
                raise ValueError('Native item memcpy exceeds bound')
            store(reg(3), bytes(cpu.mem_read(reg(4), reg(5))))
            stubs[address] = stubs.get(address, 0)+1
            ret(reg(3))
            return
        if address in (0x800fb34c, 0x801050d0):
            value = text(reg(3), address == 0x801050d0)
            stubs[address] = stubs.get(address, 0)+1
            ret(len(value)//(2 if address == 0x801050d0 else 1))
            return
        if address == 0x80102cd0:
            value = text(reg(3))
            match = re.match(br'\s*([+-]?[0-9]{1,10})', value)
            ret(int(match[1]) if match else 0)
            stubs[address] = stubs.get(address, 0)+1
            return
        if address == 0x80101e30:
            if text(reg(4)) != b'container%d' or reg(5) > 32:
                raise ValueError('Unexpected native item row format or index')
            value = ('container'+str(reg(5))).encode()
            store(reg(3), value+b'\0')
            stubs[address] = stubs.get(address, 0)+1
            ret(len(value))
            return
        if address == 0x801f5db0:
            value = text(reg(5)).decode('cp932').encode('utf-16-be')
            store(reg(3), value+b'\0\0')
            store(reg(4), struct.pack('>I', len(value)//2))
            stubs[address] = stubs.get(address, 0)+1
            ret()
            return
        if address == 0x800c43e0:
            name = text(reg(4)).decode('ascii')
            context = nodes.get(reg(5), root)
            found = next((n for n in context.iter() if n.tag == name), None)
            ret(handles[id(found)] if found is not None else 0)
            stubs[address] = stubs.get(address, 0)+1
            return
        if address == 0x800c4af4:
            ret(len(nodes[reg(3)]))
            return
        if address == 0x800c4afc:
            parent = nodes[reg(3)]
            ret(handles[id(parent[reg(4)])] if reg(4) < len(parent) else 0)
            return
        if address == 0x800c4b28:
            # Mock wrapper presence, including empty nodes, is not a native XML
            # payload-wrapper proof. Valid nonempty scalar cases avoid that gap.
            ret(reg(3))
            return
        if address == 0x800c4870:
            ret(xml_payloads[reg(3)][0])
            return
        allowed = ((0x80022d3c, 0x80022ed8), (0x80025f00, 0x80029bd0),
                   (0x8004f45c, 0x800502e4), (0x8005712c, 0x80057180),
                   (0x80012ec4, 0x80012ecc), (0x800b2428, 0x800b24a0),
                   (0x801021e4, 0x80102300))
        if not any(start <= address < end for start, end in allowed):
            raise ValueError(f'Unexpected native item-model control flow: {address:08x}')

    def write(_cpu, _access, address, size, _value, _data):
        ranges = ((scene, scene+0x400), (model, model+0x10),
                  (pane_a, pane_a+0x100), (pane_b, pane_b+0x100),
                  (match_context, match_context+0x200),
                  (stack-0x4000, stack+0x100))
        if not (any(start <= address < address+size <= end for start, end in ranges)
                or any(b <= address < address+size <= b+n for b, n in allocations)):
            raise ValueError('Native item model wrote outside synthetic buffers')

    def setup(**values):
        for index, value in {1: stack, 2: 0x8047a440, 13: 0x80478660,
                             **{int(k): v for k, v in values.items()}}.items():
            cpu.reg_write(UC_PPC_REG_0+index, value)
        cpu.reg_write(UC_PPC_REG_LR, stop)

    setup(**{'3': scene})
    cpu.reg_write(UC_PPC_REG_MSR, cpu.reg_read(UC_PPC_REG_MSR) | 0x2000)
    cpu.hook_add(UC_HOOK_CODE, instruction)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    cpu.emu_start(0x8004f45c, stop, count=3000000)
    if cpu.reg_read(UC_PPC_REG_PC) != stop:
        raise ValueError('Native item consumer did not return within instruction bound')
    accepted = reg(3) == 1

    def read_rows():
        count = word(model)
        if count > 32:
            raise ValueError('Native item count exceeds local output bound')
        result, item, seen = [], word(model+4), set()
        for _ in range(count):
            if not item or item in seen or not any(b == item and n == 0xa0 for b, n in allocations):
                raise ValueError('Invalid owned native item list')
            seen.add(item)
            row = {}
            for name, offset, wide in (('name', 4, True), ('menuCode', 8, False),
                    ('itemCode', 12, False), ('price', 16, True), ('info', 20, True),
                    ('size', 24, True), ('image', 28, False), ('isSoldout', 0x74, False)):
                value = text(word(item+offset), wide, owned=True)
                row[name] = None if value is None else value.decode('utf-16-be' if wide else 'cp932')
            number, variant = word(item+0x7c), word(item+0x80)
            if number > 32:
                raise ValueError('Native variant count exceeds local output bound')
            row['sizeList'], visited = [], set()
            for _ in range(number):
                if not variant or variant in visited or not any(b == variant and n == 0x24 for b, n in allocations):
                    raise ValueError('Invalid owned native variant list')
                visited.add(variant)
                entry = {}
                for name, offset, wide in (('itemCode', 4, False), ('size', 8, True),
                                           ('price', 12, True), ('isSoldout', 20, False)):
                    value = text(word(variant+offset), wide, owned=True)
                    entry[name] = None if value is None else value.decode('utf-16-be' if wide else 'cp932')
                entry['_native_address'] = variant
                row['sizeList'].append(entry)
                variant = word(variant+0x1c)
            if variant:
                raise ValueError('Native variant list extends past recorded count')
            result.append(row)
            item = word(item+0x84)
        if item:
            raise ValueError('Native item list extends past recorded count')
        return result

    rows = read_rows()
    for pointer, size in xml_payloads.values():
        cpu.mem_write(pointer, bytes(size))
    if read_rows() != rows:
        raise ValueError('Native item model borrowed XML payload storage')
    item_addresses, node = [], word(model+4)
    while node:
        item_addresses.append(node)
        node = word(node+0x84)
    selected_identity_checks = 0
    # Verify native indexed selection and variant-ID access on the owned model.
    for item_index, row in enumerate(rows):
        for index, variant in enumerate(row['sizeList']):
            setup(**{'3': item_addresses[item_index], '4': index})
            cpu.emu_start(0x8002757c, stop, count=10000)
            if cpu.reg_read(UC_PPC_REG_PC) != stop or reg(3) != variant['_native_address']:
                raise ValueError('Native variant index selection differs')
            setup(**{'3': reg(3)})
            cpu.emu_start(0x80029774, stop, count=10000)
            if cpu.reg_read(UC_PPC_REG_PC) != stop or text(reg(3), owned=True).decode('cp932') != variant['itemCode']:
                raise ValueError('Native selected variant identity differs')
            selected_identity_checks += 1
    for row in rows:
        for variant in row['sizeList']:
            setup(**{'15': variant.pop('_native_address'), '24': pane_a, '25': pane_b})
            cpu.emu_start(0x8005712c, 0x80057180, count=10000)
            if cpu.reg_read(UC_PPC_REG_PC) != 0x80057180:
                raise ValueError('Native variant stock predicate exceeded instruction bound')
            variant['native_soldout_flag'] = bool(reg(19))
    matches = []
    for item_index, code in basket_codes:
        if item_index >= len(item_addresses):
            raise ValueError('Basket-code probe references an absent native item')
        raw = code.encode('cp932')+b'\0'
        pointer = allocate(len(raw))
        cpu.mem_write(pointer, raw)
        put(basket_line+0x14, pointer)
        put(match_context+0x10, 0)
        put(match_context+0x1c4, 0xffffffff)
        setup(**{'24': match_context, '25': model, '29': item_addresses[item_index], '31': basket_line})
        cpu.emu_start(0x800b2428, 0x800b24a0, count=100000)
        if cpu.reg_read(UC_PPC_REG_PC) != 0x800b24a0:
            raise ValueError('Native basket variant matching exceeded instruction bound')
        index = word(match_context+0x1c4)
        matches.append({'item_index': item_index, 'basket_code': code,
                        'selected_variant_index': None if index == 0xffffffff else index,
                        'matched_count': word(match_context+0x10)})
    for address, size in (*guards, *allocations):
        length = 32 if (address, size) in allocations else 16
        if (bytes(cpu.mem_read(address-length, length)) != b'!'*length
                or bytes(cpu.mem_read(address+size, length)) != b'!'*length):
            raise ValueError('Native item synthetic buffer guard changed')
    if fail_variant_node is not None and failures['variant_node_attempts'] < fail_variant_node:
        raise ValueError('Requested variant node failure was not reached')
    if fail_item_node is not None and failures['item_node_attempts'] < fail_item_node:
        raise ValueError('Requested item node failure was not reached')
    return {'accepted': accepted, 'items': rows, 'native_model_mocked': False,
            'native_price_formatter_mocked': False, 'native_stock_comparison_mocked': False,
            'xml_lookup_storage_payload_wrappers_and_status_mocked': True,
            'xml_bytes_native_parsed': False,
            'allocation_libc_and_codecs_mocked': True,
            'zero_size_allocation_mock_returns_owned_byte': True,
            'xml_payload_overwrite_preserves_owned_model': True,
            'object_heap_stack_and_write_bounds_verified': True,
            'native_instruction_addresses_visited': len(visits), **failures,
            'native_indexed_variant_identity_checks': selected_identity_checks,
            'native_basket_code_matches': matches,
            'basket_record_parsed_or_submitted': False,
            'native_rendering_or_basket_integration_verified': False,
            'current_availability_or_orderability_verified': False}
