"""Add a default-hidden, system-font-bound directory information pane privately."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_demae_qr_modal_resource import blocks, named, SOURCE_SHA
from tools.asset_publication import publish_assets

CONTENT_SHA = 'e2d26e503f8308f51028005291457b4a7b8d605553ac113204ebe54d1fde55eb'
GROUP, BODY = 'JWC24_DIRECTORY', 'JWC24_DIR_BODY'


def patch_layout(data):
    parts = blocks(data)
    panes = {bytes(b[12:28]).split(b'\0')[0].decode(): b for b in parts if b[:4] in (b'pan1', b'pic1', b'txt1')}
    if GROUP in panes or BODY in panes:
        raise ValueError('Directory panes already exist')
    group = named(bytearray(panes['RootPane']), GROUP)
    group[8] &= 254
    group[9] = 4
    struct.pack_into('>3f', group, 36, 0, 0, 0)
    text = named(bytearray(panes['dic_T_msg00']), BODY)
    if struct.unpack_from('>I', text, 88)[0] != 116:
        raise ValueError('Unexpected native dialog text format')
    placeholder = '\u5e97\u8217\u60c5\u5831'.encode('utf-16-be')+b'\0\0'
    text = text[:116]+placeholder
    text.extend(bytes(-len(text)%4))
    text[8] |= 1
    text[9] = 4
    struct.pack_into('>I', text, 4, len(text))
    struct.pack_into('>3f', text, 36, 0, 0, 0)
    struct.pack_into('>3f', text, 48, 0, 0, 0)
    struct.pack_into('>2f', text, 60, 1, 1)
    struct.pack_into('>2f', text, 68, 500, 284)
    struct.pack_into('>HH', text, 76, len(placeholder), len(placeholder))
    struct.pack_into('>4f', text, 100, 18, 18, 0, 0)
    stack, last, insertion = [], '', None
    for i, part in enumerate(parts):
        if part[:4] in (b'pan1', b'pic1', b'txt1', b'wnd1'):
            last = bytes(part[12:28]).split(b'\0')[0].decode()
        elif part[:4] == b'pas1':
            stack.append(last)
        elif part[:4] == b'pae1':
            if not stack:
                raise ValueError('Unbalanced native pane hierarchy')
            if stack[-1] == 'dib_N_window_00':
                insertion = i
                break
            stack.pop()
    if insertion is None:
        raise ValueError('Animated modal parent missing')
    parts[insertion:insertion] = [group, bytearray(b'pas1'+struct.pack('>I', 8)), text,
                                   bytearray(b'pae1'+struct.pack('>I', 8))]
    groups = [b for b in parts if b[:4] == b'grp1' and bytes(b[8:24]).split(b'\0')[0] == b'txt_T']
    if len(groups) != 1 or len(groups[0]) != 108 or struct.unpack_from('>H', groups[0], 24)[0] != 5:
        raise ValueError('Unexpected native font group')
    groups[0].extend(BODY.encode().ljust(16, b'\0'))
    struct.pack_into('>H', groups[0], 24, 6)
    struct.pack_into('>I', groups[0], 4, len(groups[0]))
    result = bytearray(data[:16]+b''.join(parts))
    struct.pack_into('>I', result, 8, len(result))
    struct.pack_into('>H', result, 14, len(parts))
    blocks(result)
    return bytes(result)


def build_content(source):
    from libWiiPy.archive import U8Archive
    if hashlib.sha256(source).hexdigest() != CONTENT_SHA:
        raise ValueError('Directory source resource fingerprint mismatch')
    outer = U8Archive()
    outer.load(source)
    index = outer.file_name_list.index('DtestDialog.arc')
    original = outer.file_data_list[index]
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA:
        raise ValueError('Native modal fingerprint mismatch')
    inner = U8Archive()
    inner.load(original)
    layout = inner.file_name_list.index('dialogue_layout.brlyt')
    inner.file_data_list[layout] = patch_layout(inner.file_data_list[layout])
    inner.u8_node_list[layout].size = len(inner.file_data_list[layout])
    dialog = inner.dump()
    outer.file_data_list[index] = dialog
    outer.u8_node_list[index].size = len(dialog)
    result = outer.dump()
    # Reparse both levels and prove all unrelated resources unchanged.
    for before, after, allowed in ((source, result, 'DtestDialog.arc'), (original, dialog, 'dialogue_layout.brlyt')):
        a, b = U8Archive(), U8Archive()
        a.load(before)
        b.load(after)
        if a.file_name_list != b.file_name_list:
            raise ValueError('Directory resource inventory changed')
        for name, value, changed in zip(a.file_name_list, a.file_data_list, b.file_data_list):
            if name != allowed and value != changed:
                raise ValueError('Unrelated native resource changed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1]/'private'
    if not args.output.resolve().is_relative_to(private.resolve()) or args.output.exists():
        parser.error('Output must be a new private file')
    snapshot = args.source.read_bytes()
    result = build_content(snapshot)
    publish_assets([(args.output, result)], source_check=(args.source, snapshot))
    print('Built private default-hidden directory text resource; stock shared message pane preserved')


if __name__ == '__main__':
    main()
