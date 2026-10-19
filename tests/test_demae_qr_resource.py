import struct
import unittest

from tools.build_demae_qr_resource import encode_i8, patch_layout, qr_pixels, build, TEXT_PANES


def layout():
    tx = bytearray(b'txl1' + bytes(4) + struct.pack('>HH', 7, 0) + bytes(56))
    for i in range(7):
        struct.pack_into('>I', tx, 12+i*8, len(tx)-12)
        tx.extend(f'texture{i}.tpl'.encode() + b'\0')
    tx.extend(bytes((-len(tx)) % 4))
    struct.pack_into('>I', tx, 4, len(tx))
    mat = bytearray(b'mat1' + bytes(4) + struct.pack('>HH', 21, 0) + bytes(84))
    for i in range(21):
        struct.pack_into('>I', mat, 12+i*4, len(mat))
        entry = bytearray(68)
        name = b'weP_dummy' if i == 20 else f'material{i}'.encode()
        entry[:len(name)] = name
        struct.pack_into('>I', entry, 60, 1)
        mat.extend(entry)
    struct.pack_into('>I', mat, 4, len(mat))
    pic = bytearray(112)
    pic[:4] = b'pic1'
    struct.pack_into('>I', pic, 4, len(pic))
    pic[12:21] = b'weP_dummy'
    struct.pack_into('>2f', pic, 68, 512, 244)
    struct.pack_into('>H', pic, 92, 20)
    text_sections = bytearray()
    for name in TEXT_PANES:
        text = bytearray(124)
        text[:4] = b'txt1'
        struct.pack_into('>I', text, 4, len(text))
        text[12:12+len(name)] = name.encode()
        struct.pack_into('>HH', text, 76, 1026, 8)
        struct.pack_into('>I', text, 88, 116)
        text_sections.extend(text)
    data = bytearray(b'RLYT\xfe\xff\x00\x08' + bytes(4) + struct.pack('>HH', 16, 6))
    data.extend(tx+mat+pic)
    data.extend(text_sections)
    struct.pack_into('>I', data, 8, len(data))
    return bytes(data)


class QRResourceTests(unittest.TestCase):
    def test_i8_tile_roundtrip(self):
        source = bytes(range(128))
        encoded = encode_i8(source, 16, 8)
        self.assertEqual(struct.unpack_from('>HHII', encoded, 20), (8, 16, 1, 64))
        pixels = bytearray(128)
        position = 64
        for by in range(0, 8, 4):
            for bx in range(0, 16, 8):
                for y in range(4):
                    pixels[(by+y)*16+bx:(by+y)*16+bx+8] = encoded[position:position+8]
                    position += 8
        self.assertEqual(bytes(pixels), source)

    def test_layout_unique_binding_preserves_materials(self):
        original = layout()
        changed = patch_layout(original)
        self.assertEqual(int.from_bytes(changed[8:12], 'big'), len(changed))
        self.assertIn(b'jwc24_phone_qr.tpl\0', changed)
        p = 16
        while p < len(changed):
            size = int.from_bytes(changed[p+4:p+8], 'big')
            block = changed[p:p+size]
            if block[:4] == b'mat1':
                last = int.from_bytes(block[92:96], 'big')
                self.assertEqual(int.from_bytes(block[last+64:last+66], 'big'), 7)
                first = int.from_bytes(block[12:16], 'big')
                self.assertEqual(block[first+64:first+68], bytes(4))
            if block[:4] == b'pic1':
                self.assertEqual(struct.unpack_from('>2f', block, 68), (224, 224))
                self.assertEqual(int.from_bytes(block[92:94], 'big'), 20)
                self.assertEqual(block[8] & 1, 1)
                self.assertEqual(struct.unpack_from('>2f', block, 36), (-130, 10))
            if block[:4] == b'txt1':
                name = block[12:28].split(b'\0')[0].decode()
                length = int.from_bytes(block[78:80], 'big')
                self.assertEqual(block[116:116+length-2].decode('utf-16-be'), TEXT_PANES[name][0])
            p += size

    def test_qr_integer_modules_and_quiet_zone(self):
        pixels, modules, scale = qr_pixels('http://192.168.1.2:18086/p/' + 'a'*22)
        self.assertGreaterEqual(scale, 3)
        self.assertEqual(set(pixels), {0, 255})
        origin = (224-modules*scale)//2
        for y in range(origin+4*scale):
            self.assertEqual(pixels[y*224:(y+1)*224], bytes([255])*224)

    def test_fingerprint_and_pane_guards(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            build(b'not a native archive', 'http://192.168.1.2/p/test')
        bad = bytearray(layout())
        bad[bad.index(b'weP_dummy', bad.index(b'pic1'))] = ord('x')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            patch_layout(bytes(bad))


if __name__ == '__main__':
    unittest.main()
