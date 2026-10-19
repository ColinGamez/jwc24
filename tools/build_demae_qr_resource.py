"""Build a private welcome-layout QR resource; never installs or launches it."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import sys
from urllib.parse import urlsplit

SOURCE_SHA = '19c50df0bee2962a2ab7e70c28470883b2df0ec34698a7246a37eef0d69b62db'
TEXTURE = 'jwc24_phone_qr.tpl'
TEXT_PANES = {
    'weT_06_txt_00': ('\u30b9\u30de\u30fc\u30c8\u30d5\u30a9\u30f3\u3067\u6ce8\u6587', 0, 115, 500, 36, 24),
    'weT_06_txt_01': ('QR\u30b3\u30fc\u30c9\u3092\u8aad\u307f\u53d6\u3063\u3066\u3001\n\u51fa\u524d\u9928\u3067\u6ce8\u6587\u3057\u3066\u304f\u3060\u3055\u3044\u3002', 130, 45, 240, 90, 18),
    'weT_06_txt_02': ('\u6ce8\u6587\u5f8c\u306f\u30b9\u30de\u30fc\u30c8\u30d5\u30a9\u30f3\u3067\n\u300c\u6ce8\u6587\u3057\u307e\u3057\u305f\u300d\u3092\n\u62bc\u3057\u3066\u304f\u3060\u3055\u3044\u3002', 130, -50, 240, 100, 18),
}


def qr_pixels(url):
    import qrcode
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not re.fullmatch(r'/p/[A-Za-z0-9_-]{22}', parsed.path):
        raise ValueError('Expected a stable private phone entry URL')
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    scale = 224 // len(matrix)
    if scale < 3:
        raise ValueError('URL produces modules too small for this pane')
    pixels = bytearray([255] * (224 * 224))
    origin = (224 - len(matrix) * scale) // 2
    for y, row in enumerate(matrix):
        for x, black in enumerate(row):
            if black:
                for dy in range(scale):
                    p = (origin + y * scale + dy) * 224 + origin + x * scale
                    pixels[p:p+scale] = bytes(scale)
    return bytes(pixels), len(matrix), scale


def encode_i8(pixels, width=224, height=224):
    if width % 8 or height % 4 or len(pixels) != width * height:
        raise ValueError('Invalid I8 dimensions or pixels')
    tiled = bytearray()
    for by in range(0, height, 4):
        for bx in range(0, width, 8):
            for y in range(4):
                tiled.extend(pixels[(by+y)*width+bx:(by+y)*width+bx+8])
    header = struct.pack('>III', 0x20af30, 1, 12) + struct.pack('>II', 20, 0)
    header += struct.pack('>HHIIIIIIfBBBB', height, width, 1, 64, 0, 0, 0, 0, 0.0, 0, 0, 0, 0)
    return header.ljust(64, b'\0') + tiled


def patch_layout(data):
    if data[:4] != b'RLYT':
        raise ValueError('Expected RLYT layout')
    sections = []
    p = int.from_bytes(data[12:14], 'big')
    patched_pane = patched_material = False
    for _ in range(int.from_bytes(data[14:16], 'big')):
        size = int.from_bytes(data[p+4:p+8], 'big')
        block = bytearray(data[p:p+size])
        tag = block[:4]
        if tag == b'txl1':
            count = int.from_bytes(block[8:10], 'big')
            if count != 7:
                raise ValueError('Unexpected texture count')
            names = []
            for i in range(count):
                offset = int.from_bytes(block[12+i*8:16+i*8], 'big') + 12
                names.append(bytes(block[offset:block.index(0, offset)]))
            names.append(TEXTURE.encode())
            rebuilt = bytearray(b'txl1' + bytes(4) + struct.pack('>HH', len(names), 0) + bytes(len(names)*8))
            for i, name in enumerate(names):
                struct.pack_into('>I', rebuilt, 12+i*8, len(rebuilt)-12)
                rebuilt.extend(name + b'\0')
            rebuilt.extend(bytes((-len(rebuilt)) % 4))
            struct.pack_into('>I', rebuilt, 4, len(rebuilt))
            block = rebuilt
        elif tag == b'mat1':
            offset = int.from_bytes(block[92:96], 'big')  # material20 offset
            if block[offset:offset+20].split(b'\0')[0] != b'weP_dummy' or int.from_bytes(block[offset+60:offset+64], 'big') & 15 != 1:
                raise ValueError('Unexpected QR material')
            struct.pack_into('>H', block, offset+64, 7)
            patched_material = True
        elif tag == b'pic1' and block[12:28].split(b'\0')[0] == b'weP_dummy':
            if struct.unpack_from('>2f', block, 68) != (512.0, 244.0) or int.from_bytes(block[92:94], 'big') != 20:
                raise ValueError('Unexpected QR pane')
            struct.pack_into('>2f', block, 68, 224.0, 224.0)
            block[8] |= 1  # The stock dummy is hidden.
            block[9] = 5  # Center origins, integer positioning.
            struct.pack_into('>2f', block, 36, -130.0, 10.0)
            patched_pane = True
        elif tag == b'txt1' and block[12:28].split(b'\0')[0].decode() in TEXT_PANES:
            name = block[12:28].split(b'\0')[0].decode()
            text, x, y, width, height, font = TEXT_PANES[name]
            offset = int.from_bytes(block[88:92], 'big')
            if offset != 116:
                raise ValueError('Unexpected text pane format')
            encoded = text.encode('utf-16-be') + b'\0\0'
            if len(encoded) > int.from_bytes(block[76:78], 'big'):
                raise ValueError('Text exceeds native pane buffer')
            block = block[:offset] + encoded
            block.extend(bytes((-len(block)) % 4))
            struct.pack_into('>I', block, 4, len(block))
            struct.pack_into('>H', block, 78, len(encoded))
            struct.pack_into('>2f', block, 36, float(x), float(y))
            struct.pack_into('>2f', block, 68, float(width), float(height))
            struct.pack_into('>2f', block, 100, float(font), float(font))
        sections.append(bytes(block))
        p += size
    if p != len(data) or not patched_pane or not patched_material:
        raise ValueError('Incomplete layout patch')
    result = bytearray(data[:16] + b''.join(sections))
    struct.pack_into('>I', result, 8, len(result))
    return bytes(result)


def build(source, url):
    from libWiiPy.archive import U8Archive
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('Stock welcome archive fingerprint mismatch')
    archive = U8Archive()
    archive.load(source)
    pixels, modules, scale = qr_pixels(url)
    layout = archive.file_name_list.index('welcome_layout.brlyt')
    archive.file_data_list[layout] = patch_layout(archive.file_data_list[layout])
    archive.u8_node_list[layout].size = len(archive.file_data_list[layout])
    directory = archive.file_name_list.index('timg')
    insertion = archive.u8_node_list[directory].size
    node = copy.copy(archive.u8_node_list[-1])
    node.type, node.name_offset, node.data_offset = 0, 0, 0
    texture = encode_i8(pixels)
    node.size = len(texture)
    for entry in archive.u8_node_list:
        if entry.type:
            if entry.size >= insertion:
                entry.size += 1
            if entry.data_offset >= insertion:
                entry.data_offset += 1
    archive.u8_node_list.insert(insertion, node)
    archive.file_name_list.insert(insertion, TEXTURE)
    archive.file_data_list.insert(insertion, texture)
    result = archive.dump()
    check = U8Archive()
    check.load(result)
    if check.file_data_list[check.file_name_list.index(TEXTURE)] != texture:
        raise ValueError('Archive verification failed')
    return result, pixels, {'modules_with_border': modules, 'integer_scale': scale, 'width': 224, 'height': 224}


def main():
    from libWiiPy.archive import U8Archive
    from PIL import Image
    import zxingcpp
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.asset_publication import publish_assets
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content', type=Path, required=True)
    parser.add_argument('--url-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    private = Path(__file__).resolve().parents[1] / 'private'
    if not args.output.resolve().is_relative_to(private.resolve()):
        parser.error('Output must remain private')
    outer = U8Archive()
    outer.load(args.content.read_bytes())
    source = outer.file_data_list[outer.file_name_list.index('DtestWelcome.arc')]
    url_snapshot = args.url_file.read_bytes()
    url = url_snapshot.decode('utf-8').strip()
    result, pixels, report = build(source, url)
    preview = Image.frombytes('L', (224, 224), pixels)
    decoded = zxingcpp.read_barcode(preview)
    if not decoded or decoded.text != url:
        raise ValueError('Generated QR did not decode to the source URL')
    output_png = io.BytesIO()
    preview.save(output_png, format='PNG')
    report.update({'stock_sha256': SOURCE_SHA, 'output_sha256': hashlib.sha256(result).hexdigest(), 'qr_decode_verified': True, 'decoder': 'zxing-cpp', 'scope': 'private uninstalled native resource; route unverified'})
    publish_assets([(args.output, result), (args.output.with_suffix('.preview.png'), output_png.getvalue()),
                    (args.output.with_suffix('.metadata.json'), json.dumps(report, indent=2).encode())],
                   source_check=(args.url_file, url_snapshot))
    print('Built private QR resource and preview; no installation or launch')


if __name__ == '__main__':
    main()
