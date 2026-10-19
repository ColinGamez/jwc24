"""Locate immediate address references to Demae protocol strings in a local DOL.

Reports are reverse-engineering leads, not proof of call order or XML schema.
Requires capstone; derived disassembly must be written beneath private/.
"""
import argparse
import json
from pathlib import Path
import struct
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN


def sections(data):
    if len(data) < 0x100:
        raise ValueError('Truncated DOL header')
    offsets = struct.unpack_from('>18I', data, 0)
    addresses = struct.unpack_from('>18I', data, 0x48)
    sizes = struct.unpack_from('>18I', data, 0x90)
    result = []
    for index, (offset, address, size) in enumerate(zip(offsets, addresses, sizes)):
        if size:
            if offset < 0x100 or offset + size > len(data):
                raise ValueError('DOL section outside file')
            result.append((index, offset, address, size))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dol', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--strings', nargs='+', default=['/startup?', 'webApi_area_list', 'areaList', 'apiStatus', 'nwapi.demae-can.com'])
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output.resolve().is_relative_to(private.resolve()):
        parser.error('Output must stay inside private/')
    data = args.dol.read_bytes()
    layout = sections(data)
    targets = {}
    for term in args.strings:
        needle = term.encode('ascii')
        start = 0
        while (offset := data.find(needle, start)) >= 0:
            start = offset + 1
            for _, file_offset, address, size in layout:
                if file_offset <= offset < file_offset + size:
                    targets[address + offset - file_offset] = term
    decoder = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    references = []
    for index, offset, base, size in layout:
        if index >= 7:
            continue
        for position in range(0, size - 4, 4):
            word = struct.unpack_from('>I', data, offset + position)[0]
            if word >> 26 != 15 or (word >> 16) & 31:
                continue
            register = (word >> 21) & 31
            upper = (word & 0xffff) << 16
            for distance in range(4, min(28, size - position), 4):
                following = struct.unpack_from('>I', data, offset + position + distance)[0]
                opcode = following >> 26
                immediate = following & 0xffff
                signed = immediate - 65536 if immediate >= 32768 else immediate
                address = None
                if opcode == 14 and (following >> 16) & 31 == register:
                    address = (upper + signed) & 0xffffffff
                elif opcode == 24 and (following >> 21) & 31 == register:
                    address = upper | immediate
                if address in targets:
                    begin = max(0, position - 24)
                    end = min(size, position + distance + 32)
                    context = [f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in decoder.disasm(data[offset+begin:offset+end], base+begin)]
                    references.append({'term': targets[address], 'target': f'0x{address:08x}',
                                       'reference': f'0x{base+position:08x}', 'context': context})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'targets': {f'0x{k:08x}': v for k, v in targets.items()},
                          'references': references}, indent=2), encoding='utf-8')
    print(f'Located {len(targets)} protocol strings and {len(references)} candidate references')


if __name__ == '__main__':
    main()
