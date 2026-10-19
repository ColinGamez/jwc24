import struct
import unittest
from tools.build_demae_qr_modal_resource import patch_layout,blocks,GROUP,encode_rgb565


def pane(tag,name,size=76):
    b=bytearray(size);b[:4]=tag;struct.pack_into('>I',b,4,size);b[8]=1;b[12:28]=name.encode().ljust(16,b'\0')
    return b


def fixture():
    tx=bytearray(b'txl1'+bytes(4)+struct.pack('>HH',20,0)+bytes(160))
    for i in range(20):struct.pack_into('>I',tx,12+i*8,len(tx)-12);tx.extend(f'tex{i}.tpl'.encode()+b'\0')
    tx.extend(bytes(-len(tx)%4));struct.pack_into('>I',tx,4,len(tx))
    mt=bytearray(b'mat1'+bytes(4)+struct.pack('>HH',44,0)+bytes(176))
    for i in range(44):
        struct.pack_into('>I',mt,12+i*4,len(mt));z=bytearray(92);z[:20]=f'mat{i}'.encode().ljust(20,b'\0');struct.pack_into('>I',z,60,0x111);mt.extend(z)
    struct.pack_into('>I',mt,4,len(mt))
    txt=pane(b'txt1','dic_T_msg00',208);struct.pack_into('>I',txt,88,116);struct.pack_into('>H',txt,80,3)
    pic=pane(b'pic1','dic_P_iconH00_00',128);struct.pack_into('>H',pic,92,29)
    start=b'pas1'+struct.pack('>I',8);end=b'pae1'+struct.pack('>I',8)
    parts=[tx,mt,pane(b'pan1','RootPane'),start,pane(b'pan1','dib_N_window_00'),start,txt,pic,end,end]
    group=bytearray(b'grp1'+struct.pack('>I',108)+b'txt_T'.ljust(16,b'\0')+struct.pack('>HH',5,0))
    group.extend(b''.join(n.encode().ljust(16,b'\0') for n in ['dic_T_msg00','stockTxt1','stockTxt2','stockTxt3','stockTxt4']))
    parts.append(group)
    result=bytearray(b'RLYT'+b'\xfe\xff\x00\x08'+bytes(4)+struct.pack('>HH',16,len(parts))+b''.join(parts));struct.pack_into('>I',result,8,len(result));return bytes(result)


class ModalQRTests(unittest.TestCase):
    def test_opaque_texture_tile_order(self):
        pixels=bytes(255 if i % 7 else 0 for i in range(64))
        encoded=encode_rgb565(pixels,8,8)
        self.assertEqual(struct.unpack_from('>I',encoded,24)[0],4)
        decoded=bytearray(64);offset=64
        for y in range(0,8,4):
            for x in range(0,8,4):
                for dy in range(4):
                    for dx in range(4):
                        value=struct.unpack_from('>H',encoded,offset)[0];offset+=2
                        self.assertIn(value,(0,65535))
                        decoded[(y+dy)*8+x+dx]=255 if value else 0
        self.assertEqual(decoded,pixels)

    def test_centered_full_size_geometry(self):
        panes={bytes(b[12:28]).split(b'\0')[0]:b for b in blocks(patch_layout(fixture())) if b[:4] in (b'pic1',b'txt1')}
        pic=panes[b'JWC24_QR_pic']
        self.assertEqual(pic[9],4)
        self.assertEqual(struct.unpack_from('>2f',pic,60),(1,1))
        for i in range(3):
            txt=panes[f'JWC24_QR_txt{i}'.encode()]
            self.assertEqual(txt[9],4)
            self.assertEqual(struct.unpack_from('>2f',txt,108),(0,0))

    def test_hidden_group_parent_and_original_sections(self):
        before=blocks(fixture());after=blocks(patch_layout(fixture()));stack=[];last='';qr_parent=None;new=[]
        for b in after:
            if b[:4] in [b'pan1',b'pic1',b'txt1']:
                last=bytes(b[12:28]).split(b'\0')[0].decode()
                if last==GROUP:qr_parent=list(stack);self.assertEqual(b[8]&1,0)
                if last.startswith('JWC24_QR'):new.append(last)
            elif b[:4]==b'pas1':stack.append(last)
            elif b[:4]==b'pae1':stack.pop()
        self.assertEqual(qr_parent,['RootPane','dib_N_window_00']);self.assertEqual(len(new),5)
        self.assertFalse(stack)
        for b in before:
            if b[:4] not in [b'txl1',b'mat1',b'grp1']:self.assertIn(b,after)

    def test_qr_text_receives_existing_system_font_binding(self):
        before=next(b for b in blocks(fixture()) if b[:4]==b'grp1')
        after=next(b for b in blocks(patch_layout(fixture())) if b[:4]==b'grp1')
        self.assertEqual(after[28:108],before[28:108])
        self.assertEqual(struct.unpack_from('>H',after,24)[0],8)
        self.assertEqual([bytes(after[i:i+16]).split(b'\0')[0] for i in range(108,156,16)],
                         [b'JWC24_QR_txt0',b'JWC24_QR_txt1',b'JWC24_QR_txt2'])

    def test_existing_materials_preserved_and_new_binding(self):
        before=next(b for b in blocks(fixture()) if b[:4]==b'mat1')
        after=next(b for b in blocks(patch_layout(fixture())) if b[:4]==b'mat1')
        for i in range(44):
            old=int.from_bytes(before[12+i*4:16+i*4],'big');new=int.from_bytes(after[12+i*4:16+i*4],'big')
            self.assertEqual(before[old:old+92],after[new:new+92])
        new=int.from_bytes(after[188:192],'big');self.assertEqual(int.from_bytes(after[new+64:new+66],'big'),20)

    def test_source_shape_guards(self):
        d=bytearray(fixture());struct.pack_into('>H',d,24,19)
        with self.assertRaises(ValueError):patch_layout(d)
        with self.assertRaises(ValueError):patch_layout(patch_layout(fixture()))

if __name__=='__main__':unittest.main()
