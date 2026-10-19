"""Verify bounded static item-list trace anchors in the private HCHJ executable.

Reports disassembly-derived requirements, not native acceptance or rendering.
"""
import hashlib
import struct

from tools.inspect_demae_references import sections


def inspect(source):
    if hashlib.sha256(source).hexdigest() != 'da087f063dd9a7c54eb27ffda6b35f843cd0f1fbe67eca45aff216333133a830':
        raise ValueError('Native item contract source fingerprint mismatch')
    layout = sections(source)
    def read(address, size):
        for _, offset, base, length in layout:
            if base <= address and address+size <= base+length:
                return source[offset+address-base:offset+address-base+size]
        raise ValueError('Item trace anchor is outside DOL sections')
    def instruction(address, expected):
        if struct.unpack('>I', read(address, 4))[0] != expected:
            raise ValueError('Native item trace instruction mismatch')
    def branch(address, target):
        instruction(address, 0x48000001 | ((target-address) & 0x03fffffc))
    fields = [(0, 'Count', 0x8004F56C), (6, 'List', 0x8004F63C),
              (23, 'name', 0x8004F6D8), (28, 'item', 0x8004F7FC),
              (33, 'menuCode', 0x8004F838), (42, 'itemCode', 0x8004F914),
              (51, 'price', 0x8004F9FC), (57, 'info', 0x8004FB24),
              (62, 'size', 0x8004FC14), (71, 'image', 0x8004FD04),
              (79, 'isSoldout', 0x8004FDAC), (89, 'sizeList', 0x8004FE48)]
    for offset, name, address in fields:
        if read(0x802D6B9C+offset, len(name)+1) != name.encode()+b'\0':
            raise ValueError('Native item field name mismatch')
        branch(address, 0x800C43E0)
    if read(0x802D6BA7, 12) != b'container%d\0':
        raise ValueError('Native item container format mismatch')
    branch(0x8004F3E0, 0x8002C274)  # Action 10 request wrapper.
    instruction(0x8004F3CC, 0x3880000A)  # li r4, 10
    branch(0x8004F5FC, 0x80102CD0)  # Count -> integer.
    instruction(0x8004F600, 0x2C030000)  # cmpwi r3, 0
    instruction(0x8004F608, 0x41810024)  # bgt to list processing.
    branch(0x800501BC, 0x80027350)  # Item record's attached size-row count.
    instruction(0x80027350, 0x8063007C)  # lwz r3, 0x7c(r3)
    branch(0x80050154, 0x80027358)  # Attach one parsed size row.
    instruction(0x800501C0, 0x2C030000)
    instruction(0x800501C4, 0x41810024)  # bgt required before item insertion.
    branch(0x80050200, 0x80026060)
    return {'action': 'webApi_item_list', 'request_address': '0x8004f3e0',
            'consumer_address': '0x8004f45c', 'count_must_be_positive': True,
            'row_pattern': 'List/container%d',
            'fields': [{'name': name, 'lookup': f'0x{address:08x}'} for _, name, address in fields],
            'size_count_must_be_positive_before_insertion': True,
            'static_trace_only': True, 'native_rendering_verified': False}
